"""
Deterministic rules engine for breast cancer triage evaluation.

Evaluates encounter data against versioned rules and returns
a deterministic triage recommendation payload.
"""

from django.utils import timezone

from .models import (
    DecisionRule,
    DecisionSupportAssessment,
    Guideline,
    GuidelineVersion,
    RuleVersion,
)

PLACEHOLDER_WARNING = "[PLACEHOLDER/UNVALIDATED] Pending clinician review - Breast Cancer Triage Rule."


def determine_molecular_subtype(biomarkers) -> str:
    """
    Computes molecular subtype classification from BiomarkerResult objects:
    - Luminal A: ER+ and/or PR+, HER2-, low Ki-67 (<20%)
    - Luminal B: ER+ and/or PR+, HER2+ OR high Ki-67 (>=20%)
    - HER2-enriched: ER-, PR-, HER2+
    - Triple-negative: ER-, PR-, HER2-
    Returns 'Incomplete' if key biomarker fields are missing/pending.
    """
    if not biomarkers:
        return "Incomplete"

    bm = biomarkers[0] if isinstance(biomarkers, list) else biomarkers
    er = getattr(bm, "er_status", None)
    pr = getattr(bm, "pr_status", None)
    her2 = getattr(bm, "her2_status", None)
    ki67 = getattr(bm, "ki67_index", None)

    if not er or not pr or not her2 or er in ("pending", "") or pr in ("pending", "") or her2 in ("pending", ""):
        return "Incomplete"

    er_pos = er == "positive"
    pr_pos = pr == "positive"
    her2_pos = her2 in ("positive", "3+")
    her2_neg = her2 in ("negative", "0", "1+")

    if er_pos or pr_pos:
        if her2_pos:
            return "Luminal B"
        if her2_neg:
            if ki67 is not None and ki67 >= 20:
                return "Luminal B"
            return "Luminal A"
        return "Luminal B"

    if not er_pos and not pr_pos and er == "negative" and pr == "negative":
        if her2_pos:
            return "HER2-enriched"
        if her2_neg:
            return "Triple-negative"

    return "Unclassified"


def evaluate_encounter(encounter) -> dict:
    """
    Evaluates encounter data (symptoms, findings, imaging, biomarkers, staging)
    and returns a structured triage recommendation dictionary including molecular subtype,
    management plan, and referral recommendation.
    """
    matched_rule_versions = []
    triggers = []
    triage_level = DecisionSupportAssessment.TRIAGE_ROUTINE

    # Fetch active rule versions from DB if available
    active_rule_versions = RuleVersion.objects.filter(
        status="active",
        decision_rule__guideline_version__is_active=True,
    ).select_related("decision_rule")

    rule_map = {rv.decision_rule.rule_code: rv for rv in active_rule_versions}

    # 1. Collect clinical data from encounter
    assessments = list(encounter.assessments.all())
    symptoms = []
    findings = []
    for ass in assessments:
        symptoms.extend(ass.presenting_symptoms.all())
        findings.extend(ass.examination_findings.all())

    imaging_reports = list(encounter.imaging_reports.all())
    histo_reports = list(encounter.histopathology_reports.all())
    biomarkers = []
    for hr in histo_reports:
        biomarkers.extend(hr.biomarkers.all())
    staging_assessments = list(encounter.staging_assessments.all())

    # Molecular Subtype Classification
    molecular_subtype = determine_molecular_subtype(biomarkers) if biomarkers else "Incomplete"

    # Rule 1: Red Flag Clinical Features
    red_flag_symptoms = {"skin_changes", "nipple_retraction", "axillary_mass", "skin_tethering", "ulceration"}
    found_red_flags = []

    for sym in symptoms:
        if getattr(sym, "status", "recorded") == "recorded" and sym.symptom_type.lower() in red_flag_symptoms:
            found_red_flags.append(f"Symptom: {sym.symptom_type}")

    for find in findings:
        if getattr(find, "status", "recorded") == "recorded" and find.finding_type.lower() in red_flag_symptoms:
            found_red_flags.append(f"Finding: {find.finding_type}={find.finding_value}")

    if found_red_flags:
        triage_level = DecisionSupportAssessment.TRIAGE_URGENT
        triggers.append({
            "rule_code": "RULE_RED_FLAG_SYMPTOMS",
            "message": "Red flag clinical features identified",
            "details": found_red_flags,
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_RED_FLAG_SYMPTOMS" in rule_map:
            matched_rule_versions.append(rule_map["RULE_RED_FLAG_SYMPTOMS"])

    # Rule 2: BI-RADS 4, 5, or 6 Imaging Finding
    suspicious_birads = {"4", "4a", "4b", "4c", "5", "6"}
    found_birads = []
    has_confirmed_or_suspicious_malignancy = False

    for img in imaging_reports:
        if getattr(img, "status", "recorded") == "recorded" and img.birads_category in suspicious_birads:
            found_birads.append(f"{img.modality.upper()} BI-RADS {img.birads_category}")
            if img.birads_category in ("5", "6"):
                has_confirmed_or_suspicious_malignancy = True

    if histo_reports:
        has_confirmed_or_suspicious_malignancy = True

    if found_birads:
        triage_level = DecisionSupportAssessment.TRIAGE_URGENT
        triggers.append({
            "rule_code": "RULE_BIRADS_4_5_SUSPICIOUS",
            "message": "Suspicious imaging finding requiring urgent biopsy",
            "details": found_birads,
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_BIRADS_4_5_SUSPICIOUS" in rule_map:
            matched_rule_versions.append(rule_map["RULE_BIRADS_4_5_SUSPICIOUS"])

    # Rule 3: High-Risk Biomarker Phenotype / Subtype Rules
    if molecular_subtype in ("Triple-negative", "HER2-enriched", "Luminal B"):
        if molecular_subtype in ("Triple-negative", "HER2-enriched"):
            triage_level = DecisionSupportAssessment.TRIAGE_URGENT
        elif triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
            triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY

        triggers.append({
            "rule_code": "RULE_HIGH_RISK_BIOMARKER",
            "message": f"Molecular subtype identified: {molecular_subtype}",
            "details": [f"Molecular profile: {molecular_subtype}"],
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_HIGH_RISK_BIOMARKER" in rule_map:
            matched_rule_versions.append(rule_map["RULE_HIGH_RISK_BIOMARKER"])

    # Rule 4: Stage-Aware Escalation Rules
    for stg in staging_assessments:
        overall = getattr(stg, "overall_stage", "")
        m_stage = getattr(stg, "m_stage", "")
        t_stage = getattr(stg, "t_stage", "")
        n_stage = getattr(stg, "n_stage", "")

        if overall == "IV" or m_stage == "M1":
            triage_level = DecisionSupportAssessment.TRIAGE_URGENT
            triggers.append({
                "rule_code": "RULE_STAGE_IV_PALLIATIVE",
                "message": "Stage IV / Metastatic disease — urgent MDT review, palliative care & systemic therapy consultation.",
                "details": [f"Stage: {overall}, M-stage: {m_stage}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_STAGE_IV_PALLIATIVE" in rule_map:
                matched_rule_versions.append(rule_map["RULE_STAGE_IV_PALLIATIVE"])
        elif t_stage == "T4" or n_stage in ("N2", "N3") or overall in ("IIIA", "IIIB", "IIIC"):
            triage_level = DecisionSupportAssessment.TRIAGE_URGENT
            triggers.append({
                "rule_code": "RULE_LOCALLY_ADVANCED",
                "message": "Locally advanced breast cancer — urgent neoadjuvant MDT review & staging.",
                "details": [f"Stage: {overall}, T: {t_stage}, N: {n_stage}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_LOCALLY_ADVANCED" in rule_map:
                matched_rule_versions.append(rule_map["RULE_LOCALLY_ADVANCED"])
        elif overall in ("I", "IIA", "IIB") or t_stage in ("T1", "T2"):
            if triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
                triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY
            triggers.append({
                "rule_code": "RULE_EARLY_STAGE",
                "message": "Early-stage breast cancer — priority surgical review & curative intent pathway.",
                "details": [f"Stage: {overall}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_EARLY_STAGE" in rule_map:
                matched_rule_versions.append(rule_map["RULE_EARLY_STAGE"])

    # Rule 5: Missing-Data Safety Rule (Biomarker Incomplete)
    if has_confirmed_or_suspicious_malignancy and molecular_subtype in ("Incomplete", "Unclassified", ""):
        if triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
            triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY
        triggers.append({
            "rule_code": "RULE_INCOMPLETE_BIOMARKER",
            "message": "Biomarker assessment incomplete — order IHC (ER/PR/HER2/Ki67) or repeat biopsy",
            "details": ["Confirmed or highly suspicious malignancy with incomplete molecular biomarkers."],
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_INCOMPLETE_BIOMARKER" in rule_map:
            matched_rule_versions.append(rule_map["RULE_INCOMPLETE_BIOMARKER"])

    # Rule 6: Palpable Mass in Woman Age >= 40
    if triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
        has_lump = any(s.symptom_type.lower() == "breast_lump" and getattr(s, "status", "recorded") == "recorded" for s in symptoms) or \
                   any(f.finding_type.lower() == "mass" and getattr(f, "status", "recorded") == "recorded" for f in findings)
        patient = encounter.patient
        age_over_40 = patient.year_of_birth and (timezone.now().year - patient.year_of_birth >= 40)

        if has_lump and age_over_40:
            triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY
            triggers.append({
                "rule_code": "RULE_PALPABLE_MASS_AGE_40",
                "message": "Palpable breast mass in patient age 40 or older without acute red flags",
                "details": [f"Patient YOB: {patient.year_of_birth}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_PALPABLE_MASS_AGE_40" in rule_map:
                matched_rule_versions.append(rule_map["RULE_PALPABLE_MASS_AGE_40"])

    # Default Routine Rule if no triggers
    if not triggers:
        triggers.append({
            "rule_code": "RULE_DEFAULT_ROUTINE",
            "message": "No high-risk triggers detected. Routine clinical care.",
            "details": [],
            "notice": PLACEHOLDER_WARNING,
        })

    # Build Structured Management Plan & Referral Recommendation
    management_plan = []
    if triage_level == DecisionSupportAssessment.TRIAGE_URGENT:
        management_plan.extend([
            {"action": "Multidisciplinary Team (MDT) Case Review", "placeholder": True},
            {"action": "Referral to Port Moresby General Hospital Oncology Service", "placeholder": True},
            {"action": "Urgent surgical consultation at St. Mary Private Medical Center", "placeholder": True},
        ])
        if molecular_subtype == "Triple-negative" or molecular_subtype == "HER2-enriched":
            management_plan.append({"action": "Neoadjuvant chemotherapy consideration", "placeholder": True})
        if molecular_subtype in ("Luminal A", "Luminal B"):
            management_plan.append({"action": "Hormone therapy evaluation (Tamoxifen / Anastrozole)", "placeholder": True})
        referral_recommendation = "Urgent surgical and oncology referral to Port Moresby General Hospital / Specialist MDT."

    elif triage_level == DecisionSupportAssessment.TRIAGE_PRIORITY:
        management_plan.extend([
            {"action": "Priority surgical review at St. Mary Private Medical Center", "placeholder": True},
            {"action": "Complete diagnostic imaging & tissue biopsy", "placeholder": True},
        ])
        if molecular_subtype == "Incomplete":
            management_plan.append({"action": "Order IHC biomarker panel (ER/PR/HER2/Ki67)", "placeholder": True})
        referral_recommendation = "Priority surgical review at St. Mary Private Medical Center."

    else:
        management_plan.extend([
            {"action": "Local clinical follow-up & symptom re-evaluation", "placeholder": True},
            {"action": "Patient education & routine breast health monitoring", "placeholder": True},
        ])
        referral_recommendation = "Local follow-up at St. Mary Private Medical Center."

    # Summary recommendation string
    if triage_level == DecisionSupportAssessment.TRIAGE_URGENT:
        summary = (
            f"URGENT TRIAGE RECOMMENDED. Encounter demonstrates suspicious/red-flag clinical "
            f"or molecular features ({len(triggers)} trigger(s) activated). "
            f"Expedited diagnostic workup/biopsy/MDT review within 1-2 weeks recommended. "
            f"{PLACEHOLDER_WARNING}"
        )
    elif triage_level == DecisionSupportAssessment.TRIAGE_PRIORITY:
        summary = (
            f"PRIORITY TRIAGE RECOMMENDED. Priority criteria or incomplete biomarker assessment met. "
            f"Targeted diagnostic workup recommended within 2-4 weeks. "
            f"{PLACEHOLDER_WARNING}"
        )
    else:
        summary = (
            f"ROUTINE TRIAGE RECOMMENDED. No urgent or priority red flags identified. "
            f"Routine management and reassessment as indicated. "
            f"{PLACEHOLDER_WARNING}"
        )

    reasoning_payload = {
        "encounter_id": encounter.id,
        "patient_pseudonym_id": str(encounter.patient.pseudonym_id),
        "calculated_triage_level": triage_level,
        "molecular_subtype": molecular_subtype,
        "management_plan": management_plan,
        "referral_recommendation": referral_recommendation,
        "triggers": triggers,
        "disclaimer": PLACEHOLDER_WARNING,
        "evaluated_at": timezone.now().isoformat(),
    }

    return {
        "triage_level": triage_level,
        "summary_recommendation": summary,
        "molecular_subtype": molecular_subtype,
        "management_plan": management_plan,
        "referral_recommendation": referral_recommendation,
        "matched_rule_versions": matched_rule_versions,
        "reasoning_payload": reasoning_payload,
    }


def seed_example_rules(user=None):
    """
    Utility helper to seed breast-cancer triage rules,
    clearly marked as placeholder / unvalidated pending clinician review.
    """
    guideline, _ = Guideline.objects.get_or_create(
        code="PNG_BC_2025",
        defaults={
            "title": "PNG Breast Cancer Clinical Triage Guideline (Placeholder)",
            "description": "Placeholder guideline for early breast cancer triage and management.",
        },
    )

    # Deprecate old guideline versions
    GuidelineVersion.objects.filter(guideline=guideline, version_number="1.0.0-placeholder").update(is_active=False)

    gv, _ = GuidelineVersion.objects.get_or_create(
        guideline=guideline,
        version_number="1.1.0-placeholder",
        defaults={
            "source_citation": "PNG Ministry of Health Breast Cancer Guidelines (v1.1 Draft) [PLACEHOLDER]",
            "approved_by": user,
            "approved_at": timezone.now(),
            "is_active": True,
        },
    )

    # Deprecate old rule versions
    RuleVersion.objects.filter(version_number="1.0.0-placeholder").update(status="deprecated")

    seeded_rules = [
        ("RULE_RED_FLAG_SYMPTOMS", "Red Flag Clinical Features", "Skin tethering, ulceration, nipple retraction or lymphadenopathy.", "URGENT"),
        ("RULE_BIRADS_4_5_SUSPICIOUS", "Suspicious Imaging Findings", "Mammography/Ultrasound BI-RADS category 4, 5, or 6.", "URGENT"),
        ("RULE_HIGH_RISK_BIOMARKER", "Aggressive Biomarker Profile", "Triple-negative, HER2-positive, or Ki-67 >= 30%.", "URGENT"),
        ("RULE_STAGE_IV_PALLIATIVE", "Stage IV / Metastatic Disease", "Metastatic disease requiring urgent palliative MDT review.", "URGENT"),
        ("RULE_LOCALLY_ADVANCED", "Locally Advanced Disease", "T4 or N2+ disease requiring urgent neoadjuvant review.", "URGENT"),
        ("RULE_INCOMPLETE_BIOMARKER", "Incomplete Biomarker Assessment", "Confirmed malignancy missing biomarker profile.", "PRIORITY"),
        ("RULE_EARLY_STAGE", "Early-Stage Disease", "Early stage operable breast cancer.", "PRIORITY"),
        ("RULE_PALPABLE_MASS_AGE_40", "Palpable Breast Mass in Patient Age >= 40", "Isolated breast mass in patient aged 40 or older.", "PRIORITY"),
        ("RULE_CYCLICAL_PAIN_ROUTINE", "Isolated Breast Pain", "Breast pain without palpable lump or red flags.", "ROUTINE"),
    ]

    rule_versions = []
    for code, name, desc, triage in seeded_rules:
        drule, _ = DecisionRule.objects.get_or_create(
            guideline_version=gv,
            rule_code=code,
            defaults={"name": name, "description": desc},
        )
        rversion, _ = RuleVersion.objects.get_or_create(
            decision_rule=drule,
            version_number="1.1.0-placeholder",
            defaults={
                "logic_spec": {
                    "rule_code": code,
                    "target_triage": triage,
                    "unvalidated_notice": PLACEHOLDER_WARNING,
                },
                "source_citation": f"{PLACEHOLDER_WARNING} Source: Synthetic guideline rule {code}.",
                "approved_by": user,
                "approved_at": timezone.now(),
                "status": "active",
            },
        )
        rule_versions.append(rversion)

    return rule_versions

"""
Deterministic rules engine for breast cancer triage evaluation.

Evaluates encounter data against versioned rules and returns
a deterministic triage recommendation payload.
"""

from django.utils import timezone

from apps.ai.provider import get_ai_provider

from .models import (
    DecisionRule,
    DecisionSupportAssessment,
    Guideline,
    GuidelineVersion,
    MolecularSubtype,
    RuleVersion,
)

PLACEHOLDER_WARNING = "[PLACEHOLDER/UNVALIDATED] Pending clinician review - Breast Cancer Triage Rule."


def determine_molecular_subtype(biomarkers) -> tuple[str, bool]:
    """
    Classifies molecular subtype from BiomarkerResult objects:
    - TNBC (triple_negative): ER-, PR-, HER2 0/1+/negative
    - HER2-enriched (her2_enriched): HER2 3+/positive or amplified, ER-, PR-
    - Luminal B-like (luminal_b): ER+ or PR+, HER2+ OR Ki-67 >= 20%
    - Luminal A-like (luminal_a): ER+/PR+, HER2-, Ki-67 < 20%
    - unclassified + flag incomplete_data=True if ER/PR/HER2/ki67 status != "recorded" or missing.

    Returns tuple (subtype_key, incomplete_data_bool).
    """
    if not biomarkers:
        return "unclassified", True

    bm = biomarkers[0] if isinstance(biomarkers, list) else biomarkers

    bm_status = getattr(bm, "status", "recorded")
    if bm_status != "recorded":
        return "unclassified", True

    er = getattr(bm, "er_status", None)
    pr = getattr(bm, "pr_status", None)
    her2 = getattr(bm, "her2_status", None)
    ki67 = getattr(bm, "ki67_index", None)

    # If any biomarker is pending/missing/null, mark incomplete
    if not er or not pr or not her2 or er in ("pending", "") or pr in ("pending", "") or her2 in ("pending", ""):
        return "unclassified", True

    er_pos = er == "positive"
    pr_pos = pr == "positive"
    her2_pos = her2 in ("positive", "3+", "amplified")
    her2_neg = her2 in ("negative", "0", "1+")

    if er_pos or pr_pos:
        if her2_pos or (ki67 is not None and ki67 >= 20):
            return "luminal_b", False
        if her2_neg:
            return "luminal_a", False
        return "luminal_b", False

    if not er_pos and not pr_pos and er == "negative" and pr == "negative":
        if her2_pos:
            return "her2_enriched", False
        if her2_neg:
            return "triple_negative", False

    return "unclassified", False


def _evaluate_rule_vocabulary(spec: dict, context: dict) -> bool:
    """
    Evaluates a logic_spec rule condition dictionary against context data:
    - {"all": [...]}
    - {"any": [...]}
    - {"not": {...}}
    - {"biomarker": {"field": "ki67_index", "op": ">=", "value": 20}}
    - {"staging": {"field": "tnm_stage", "op": "in", "value": ["III", "IV"]}}
    - {"histopath": {"field": "grade", "op": ">=", "value": 3}}
    - {"patient": {"field": "age", "op": "<=", "value": 40}}
    - {"missing": {"field": "biomarker.her2_status"}}
    """
    if not spec or not isinstance(spec, dict):
        return False

    if "all" in spec:
        return all(_evaluate_rule_vocabulary(sub, context) for sub in spec["all"])

    if "any" in spec:
        return any(_evaluate_rule_vocabulary(sub, context) for sub in spec["any"])

    if "not" in spec:
        return not _evaluate_rule_vocabulary(spec["not"], context)

    if "missing" in spec:
        field_path = spec["missing"].get("field", "")
        domain, _, f_name = field_path.partition(".")
        obj = context.get(domain)
        if not obj:
            return True
        val = getattr(obj, f_name, None)
        return val is None or val in ("pending", "", "GX")

    for domain in ("biomarker", "staging", "histopath", "patient"):
        if domain in spec:
            f_info = spec[domain]
            f_name = f_info.get("field")
            op = f_info.get("op", "==")
            target = f_info.get("value")

            if domain == "patient":
                val = context.get("patient_age")
            else:
                obj = context.get(domain)
                if not obj:
                    return False
                if domain == "staging" and f_name == "tnm_stage":
                    val = getattr(obj, "overall_stage", "")
                else:
                    val = getattr(obj, f_name, None)

            if val is None:
                return False

            try:
                if op == "==":
                    return str(val).lower() == str(target).lower()
                if op == "!=":
                    return str(val).lower() != str(target).lower()
                if op == ">=":
                    return float(val) >= float(target)
                if op == "<=":
                    return float(val) <= float(target)
                if op == ">":
                    return float(val) > float(target)
                if op == "<":
                    return float(val) < float(target)
                if op == "in":
                    return str(val) in [str(x) for x in target]
                if op == "contains":
                    return str(target).lower() in str(val).lower()
            except (ValueError, TypeError):
                return False

    return False


def evaluate_encounter(encounter) -> dict:
    """
    Evaluates encounter data (symptoms, findings, imaging, biomarkers, staging)
    and returns a structured triage recommendation dictionary including molecular subtype,
    management plan, and referral recommendation.
    """
    matched_rule_versions = []
    fired_rules = []
    triggers = []
    triage_level = DecisionSupportAssessment.TRIAGE_ROUTINE

    # Fetch active rule versions from DB
    active_rule_versions = RuleVersion.objects.filter(
        status="active",
        decision_rule__guideline_version__is_active=True,
    ).select_related("decision_rule", "decision_rule__guideline_version__guideline")

    rule_map = {rv.decision_rule.rule_code: rv for rv in active_rule_versions}

    # 1. Collect clinical data
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

    bm_obj = biomarkers[0] if biomarkers else None
    stg_obj = staging_assessments[0] if staging_assessments else None
    histo_obj = histo_reports[0] if histo_reports else None

    patient = encounter.patient
    patient_age = (timezone.now().year - patient.year_of_birth) if patient.year_of_birth else None

    evaluation_context = {
        "biomarker": bm_obj,
        "staging": stg_obj,
        "histopath": histo_obj,
        "patient": patient,
        "patient_age": patient_age,
    }

    # Subtype Classification
    subtype_key, incomplete_data = determine_molecular_subtype(biomarkers)
    molecular_subtype_obj = MolecularSubtype.objects.filter(name=subtype_key).first()
    molecular_subtype_display = molecular_subtype_obj.display_name if molecular_subtype_obj else subtype_key.title().replace("_", " ")

    # Evaluate dynamic rule versions via logic_spec vocabulary
    for rv in active_rule_versions:
        if _evaluate_rule_vocabulary(rv.logic_spec, evaluation_context):
            matched_rule_versions.append(rv)
            target_triage = rv.logic_spec.get("target_triage", "PRIORITY")

            if target_triage == "URGENT":
                triage_level = DecisionSupportAssessment.TRIAGE_URGENT
            elif target_triage == "PRIORITY" and triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
                triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY

            fired_rules.append({
                "rule_code": rv.decision_rule.rule_code,
                "rule_name": rv.decision_rule.name,
                "version": rv.version_number,
                "target_triage": target_triage,
                "explanation": f"Matched logic_spec: {rv.decision_rule.description or rv.decision_rule.name}",
                "unvalidated_notice": PLACEHOLDER_WARNING,
            })

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
        if "RULE_RED_FLAG_SYMPTOMS" in rule_map and rule_map["RULE_RED_FLAG_SYMPTOMS"] not in matched_rule_versions:
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
        if "RULE_BIRADS_4_5_SUSPICIOUS" in rule_map and rule_map["RULE_BIRADS_4_5_SUSPICIOUS"] not in matched_rule_versions:
            matched_rule_versions.append(rule_map["RULE_BIRADS_4_5_SUSPICIOUS"])

    # Rule 3: Subtype / High-Risk Biomarker Rules
    if subtype_key in ("triple_negative", "her2_enriched", "luminal_b"):
        if subtype_key in ("triple_negative", "her2_enriched"):
            triage_level = DecisionSupportAssessment.TRIAGE_URGENT
        elif triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
            triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY

        triggers.append({
            "rule_code": "RULE_HIGH_RISK_BIOMARKER",
            "message": f"Molecular subtype identified: {molecular_subtype_display}",
            "details": [f"Molecular profile: {molecular_subtype_display}"],
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_HIGH_RISK_BIOMARKER" in rule_map and rule_map["RULE_HIGH_RISK_BIOMARKER"] not in matched_rule_versions:
            matched_rule_versions.append(rule_map["RULE_HIGH_RISK_BIOMARKER"])

    # Rule 4: Stage-Aware Escalation Rules
    for stg in staging_assessments:
        overall = getattr(stg, "overall_stage", "")
        m_stage = getattr(stg, "m_stage", "")
        t_stage = getattr(stg, "t_stage", "")
        n_stage = getattr(stg, "n_stage", "")

        if overall in ("IV", "4") or m_stage == "M1":
            triage_level = DecisionSupportAssessment.TRIAGE_URGENT
            triggers.append({
                "rule_code": "RULE_STAGE_IV_PALLIATIVE",
                "message": "Stage IV / Metastatic disease — urgent MDT review, palliative care & systemic therapy consultation.",
                "details": [f"Stage: {overall}, M-stage: {m_stage}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_STAGE_IV_PALLIATIVE" in rule_map and rule_map["RULE_STAGE_IV_PALLIATIVE"] not in matched_rule_versions:
                matched_rule_versions.append(rule_map["RULE_STAGE_IV_PALLIATIVE"])
        elif t_stage == "T4" or n_stage in ("N2", "N3") or overall in ("IIIA", "IIIB", "IIIC", "3"):
            triage_level = DecisionSupportAssessment.TRIAGE_URGENT
            triggers.append({
                "rule_code": "RULE_LOCALLY_ADVANCED",
                "message": "Locally advanced breast cancer — urgent neoadjuvant MDT review & staging.",
                "details": [f"Stage: {overall}, T: {t_stage}, N: {n_stage}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_LOCALLY_ADVANCED" in rule_map and rule_map["RULE_LOCALLY_ADVANCED"] not in matched_rule_versions:
                matched_rule_versions.append(rule_map["RULE_LOCALLY_ADVANCED"])
        elif overall in ("I", "1", "IIA", "IIB", "2") or t_stage in ("T1", "T2"):
            if triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
                triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY
            triggers.append({
                "rule_code": "RULE_EARLY_STAGE",
                "message": "Early-stage breast cancer — priority surgical review & curative intent pathway.",
                "details": [f"Stage: {overall}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_EARLY_STAGE" in rule_map and rule_map["RULE_EARLY_STAGE"] not in matched_rule_versions:
                matched_rule_versions.append(rule_map["RULE_EARLY_STAGE"])

    # Rule 5: Missing-Data Safety Rule (Biomarker Incomplete)
    if has_confirmed_or_suspicious_malignancy and incomplete_data:
        if triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
            triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY
        triggers.append({
            "rule_code": "RULE_INCOMPLETE_BIOMARKER",
            "message": "Biomarker assessment incomplete — order IHC (ER/PR/HER2/Ki67) or repeat biopsy",
            "details": ["Confirmed or highly suspicious malignancy with incomplete molecular biomarkers."],
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_INCOMPLETE_BIOMARKER" in rule_map and rule_map["RULE_INCOMPLETE_BIOMARKER"] not in matched_rule_versions:
            matched_rule_versions.append(rule_map["RULE_INCOMPLETE_BIOMARKER"])

    # Rule 6: Palpable Mass in Woman Age >= 40
    if triage_level == DecisionSupportAssessment.TRIAGE_ROUTINE:
        has_lump = any(s.symptom_type.lower() == "breast_lump" and getattr(s, "status", "recorded") == "recorded" for s in symptoms) or \
                   any(f.finding_type.lower() == "mass" and getattr(f, "status", "recorded") == "recorded" for f in findings)
        if has_lump and patient_age and patient_age >= 40:
            triage_level = DecisionSupportAssessment.TRIAGE_PRIORITY
            triggers.append({
                "rule_code": "RULE_PALPABLE_MASS_AGE_40",
                "message": "Palpable breast mass in patient age 40 or older without acute red flags",
                "details": [f"Patient Age: {patient_age}"],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_PALPABLE_MASS_AGE_40" in rule_map and rule_map["RULE_PALPABLE_MASS_AGE_40"] not in matched_rule_versions:
                matched_rule_versions.append(rule_map["RULE_PALPABLE_MASS_AGE_40"])

    # Default Routine Rule if no triggers
    if not triggers:
        triggers.append({
            "rule_code": "RULE_DEFAULT_ROUTINE",
            "message": "No high-risk triggers detected. Routine clinical care.",
            "details": [],
            "notice": PLACEHOLDER_WARNING,
        })

    # AI Abstraction Layer Call (OFF by default)
    ai_result = get_ai_provider().assess({
        "encounter_id": encounter.id,
        "triage_level": triage_level,
        "molecular_subtype": molecular_subtype_display,
    })
    ai_suggestion = ai_result.get("suggestion") or {}
    ai_provider_version = ai_result.get("provider_version", "null-v0.1.0")

    # Build Structured Management Plan & Referral Recommendation
    management_plan = []
    if triage_level == DecisionSupportAssessment.TRIAGE_URGENT:
        management_plan.extend([
            {
                "plan_type": "mdt_review",
                "recommendation_text": "Multidisciplinary Team (MDT) Case Review",
                "requires_referral": True,
                "referral_destination": "Port Moresby General Hospital Oncology Service",
                "timeframe_days": 14,
                "resource_level": "specialist_tertiary",
                "placeholder": True,
            },
            {
                "plan_type": "surgical_consult",
                "recommendation_text": "Urgent surgical consultation at St. Mary Private Medical Center",
                "requires_referral": True,
                "referral_destination": "St. Mary Private Medical Center Surgery",
                "timeframe_days": 7,
                "resource_level": "surgical_specialist",
                "placeholder": True,
            },
        ])
        if subtype_key in ("triple_negative", "her2_enriched"):
            management_plan.append({
                "plan_type": "neoadjuvant_chemo",
                "recommendation_text": "Neoadjuvant chemotherapy & HER2 targeted therapy evaluation",
                "requires_referral": True,
                "referral_destination": "Port Moresby General Hospital Medical Oncology",
                "timeframe_days": 14,
                "resource_level": "tertiary_oncology",
                "placeholder": True,
            })
        if subtype_key in ("luminal_a", "luminal_b"):
            management_plan.append({
                "plan_type": "endocrine_eval",
                "recommendation_text": "Hormone therapy evaluation (Tamoxifen / Anastrozole)",
                "requires_referral": False,
                "referral_destination": "St. Mary Medical Center",
                "timeframe_days": 14,
                "resource_level": "secondary_clinical",
                "placeholder": True,
            })
        referral_recommendation = "Urgent surgical and oncology referral to Port Moresby General Hospital / Specialist MDT."

    elif triage_level == DecisionSupportAssessment.TRIAGE_PRIORITY:
        management_plan.extend([
            {
                "plan_type": "surgical_review",
                "recommendation_text": "Priority surgical review at St. Mary Private Medical Center",
                "requires_referral": True,
                "referral_destination": "St. Mary Private Medical Center",
                "timeframe_days": 21,
                "resource_level": "surgical_specialist",
                "placeholder": True,
            },
            {
                "plan_type": "diagnostic_completion",
                "recommendation_text": "Complete diagnostic imaging & tissue biopsy",
                "requires_referral": False,
                "referral_destination": "St. Mary Diagnostics",
                "timeframe_days": 14,
                "resource_level": "diagnostic_center",
                "placeholder": True,
            },
        ])
        if incomplete_data:
            management_plan.append({
                "plan_type": "biomarker_order",
                "recommendation_text": "Order IHC biomarker panel (ER/PR/HER2/Ki67)",
                "requires_referral": False,
                "referral_destination": "Pathology Reference Lab",
                "timeframe_days": 7,
                "resource_level": "pathology",
                "placeholder": True,
            })
        referral_recommendation = "Priority surgical review at St. Mary Private Medical Center."

    else:
        management_plan.extend([
            {
                "plan_type": "local_followup",
                "recommendation_text": "Local clinical follow-up & symptom re-evaluation",
                "requires_referral": False,
                "referral_destination": "St. Mary Primary Care",
                "timeframe_days": 60,
                "resource_level": "primary_care",
                "placeholder": True,
            },
            {
                "plan_type": "patient_education",
                "recommendation_text": "Patient education & routine breast health monitoring",
                "requires_referral": False,
                "referral_destination": "St. Mary Outpatient",
                "timeframe_days": 90,
                "resource_level": "primary_care",
                "placeholder": True,
            },
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
        "molecular_subtype": molecular_subtype_display,
        "incomplete_data": incomplete_data,
        "management_plan": management_plan,
        "referral_recommendation": referral_recommendation,
        "fired_rules": fired_rules,
        "triggers": triggers,
        "ai_suggestion": ai_suggestion,
        "disclaimer": PLACEHOLDER_WARNING,
        "evaluated_at": timezone.now().isoformat(),
    }

    return {
        "triage_level": triage_level,
        "summary_recommendation": summary,
        "molecular_subtype": molecular_subtype_display,
        "molecular_subtype_fk": molecular_subtype_obj,
        "incomplete_data": incomplete_data,
        "management_plan": management_plan,
        "referral_recommendation": referral_recommendation,
        "ai_suggestion": ai_suggestion,
        "ai_provider_version": ai_provider_version,
        "fired_rules": fired_rules,
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

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


def evaluate_encounter(encounter) -> dict:
    """
    Evaluates encounter data (symptoms, findings, imaging, biomarkers, staging)
    and returns a structured triage recommendation dictionary:
    {
        'triage_level': 'URGENT' | 'PRIORITY' | 'ROUTINE',
        'summary_recommendation': str,
        'matched_rule_versions': list of RuleVersion objects,
        'reasoning_payload': dict,
    }
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
    list(encounter.staging_assessments.all())

    # Check Rule 1: Red Flag Clinical Features (Skin changes, ulceration, lymph nodes, nipple retraction)
    red_flag_symptoms = {"skin_changes", "nipple_retraction", "axillary_mass", "skin_tethering", "ulceration"}
    found_red_flags = []

    for sym in symptoms:
        if sym.status == "recorded" and sym.symptom_type.lower() in red_flag_symptoms:
            found_red_flags.append(f"Symptom: {sym.symptom_type}")

    for find in findings:
        if find.status == "recorded" and find.finding_type.lower() in red_flag_symptoms:
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

    # Check Rule 2: BI-RADS 4, 5, or 6 Imaging Finding
    suspicious_birads = {"4", "4a", "4b", "4c", "5", "6"}
    found_birads = []
    for img in imaging_reports:
        if img.status == "recorded" and img.birads_category in suspicious_birads:
            found_birads.append(f"{img.modality.upper()} BI-RADS {img.birads_category}")

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

    # Check Rule 3: High-Risk Biomarker Phenotype (Triple-Negative, HER2+, high Ki-67)
    found_biomarkers = []
    for bm in biomarkers:
        if bm.status == "recorded":
            is_tnbc = (
                bm.er_status == "negative"
                and bm.pr_status == "negative"
                and bm.her2_status in ("negative", "0", "1+")
            )
            is_her2_pos = bm.her2_status in ("positive", "3+")
            high_ki67 = bm.ki67_index is not None and bm.ki67_index >= 30

            if is_tnbc:
                found_biomarkers.append("Triple-Negative Breast Cancer phenotype")
            if is_her2_pos:
                found_biomarkers.append("HER2-positive phenotype")
            if high_ki67:
                found_biomarkers.append(f"High Ki-67 proliferation index ({bm.ki67_index}%)")

    if found_biomarkers:
        triage_level = DecisionSupportAssessment.TRIAGE_URGENT
        triggers.append({
            "rule_code": "RULE_HIGH_RISK_BIOMARKER",
            "message": "Aggressive molecular biomarker profile requiring urgent MDT review",
            "details": found_biomarkers,
            "notice": PLACEHOLDER_WARNING,
        })
        if "RULE_HIGH_RISK_BIOMARKER" in rule_map:
            matched_rule_versions.append(rule_map["RULE_HIGH_RISK_BIOMARKER"])

    # Check Rule 4: Palpable Mass in Woman Age >= 40
    if triage_level != DecisionSupportAssessment.TRIAGE_URGENT:
        has_lump = any(s.symptom_type.lower() == "breast_lump" and s.status == "recorded" for s in symptoms) or \
                   any(f.finding_type.lower() == "mass" and f.status == "recorded" for f in findings)
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

    # Check Rule 5: Cyclical Pain / Routine Follow-Up
    if not triggers:
        has_pain = any(s.symptom_type.lower() == "breast_pain" and s.status == "recorded" for s in symptoms)
        if has_pain:
            triggers.append({
                "rule_code": "RULE_CYCLICAL_PAIN_ROUTINE",
                "message": "Breast pain without suspicious mass or red flags",
                "details": ["Reassurance and conservative management advised."],
                "notice": PLACEHOLDER_WARNING,
            })
            if "RULE_CYCLICAL_PAIN_ROUTINE" in rule_map:
                matched_rule_versions.append(rule_map["RULE_CYCLICAL_PAIN_ROUTINE"])
        else:
            triggers.append({
                "rule_code": "RULE_DEFAULT_ROUTINE",
                "message": "No high-risk triggers detected. Routine clinical care.",
                "details": [],
                "notice": PLACEHOLDER_WARNING,
            })

    # Summary recommendation string
    if triage_level == DecisionSupportAssessment.TRIAGE_URGENT:
        summary = (
            f"URGENT TRIAGE RECOMMENDED. Encounter demonstrates suspicious/red-flag clinical "
            f"or diagnostic features ({len(triggers)} trigger(s) activated). "
            f"Expedited diagnostic workup/biopsy/MDT review within 1-2 weeks recommended. "
            f"{PLACEHOLDER_WARNING}"
        )
    elif triage_level == DecisionSupportAssessment.TRIAGE_PRIORITY:
        summary = (
            f"PRIORITY TRIAGE RECOMMENDED. Palpable mass or priority criteria met. "
            f"Targeted diagnostic imaging recommended within 2-4 weeks. "
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
        "triggers": triggers,
        "disclaimer": PLACEHOLDER_WARNING,
        "evaluated_at": timezone.now().isoformat(),
    }

    return {
        "triage_level": triage_level,
        "summary_recommendation": summary,
        "matched_rule_versions": matched_rule_versions,
        "reasoning_payload": reasoning_payload,
    }


def seed_example_rules(user=None):
    """
    Utility helper to seed 3-5 example breast-cancer triage rules,
    clearly marked as placeholder / unvalidated pending clinician review.
    """
    guideline, _ = Guideline.objects.get_or_create(
        code="PNG_BC_2025",
        defaults={
            "title": "PNG Breast Cancer Clinical Triage Guideline (Placeholder)",
            "description": "Placeholder guideline for early breast cancer triage and management.",
        },
    )

    gv, _ = GuidelineVersion.objects.get_or_create(
        guideline=guideline,
        version_number="1.0.0-placeholder",
        defaults={
            "source_citation": "PNG Ministry of Health Breast Cancer Guidelines (Draft) [PLACEHOLDER]",
            "approved_by": user,
            "approved_at": timezone.now(),
            "is_active": True,
        },
    )

    seeded_rules = [
        ("RULE_RED_FLAG_SYMPTOMS", "Red Flag Clinical Features", "Skin tethering, ulceration, nipple retraction or lymphadenopathy.", "URGENT"),
        ("RULE_BIRADS_4_5_SUSPICIOUS", "Suspicious Imaging Findings", "Mammography/Ultrasound BI-RADS category 4, 5, or 6.", "URGENT"),
        ("RULE_HIGH_RISK_BIOMARKER", "Aggressive Biomarker Profile", "Triple-negative, HER2-positive, or Ki-67 >= 30%.", "URGENT"),
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
            version_number="1.0.0-placeholder",
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

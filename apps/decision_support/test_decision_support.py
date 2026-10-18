import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clinical.models import (
    ClinicalAssessment,
    Encounter,
    PresentingSymptom,
)
from apps.decision_support.engine import evaluate_encounter, seed_example_rules
from apps.decision_support.models import DecisionSupportAssessment
from apps.investigations.models import (
    BiomarkerResult,
    HistopathologyReport,
    ImagingReport,
)
from apps.registry.models import Patient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def doctor(db):
    return User.objects.create_user(username="dr_decision", password="Password12345!")


@pytest.mark.django_db
def test_rules_engine_red_flag_triggers_urgent(doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1975, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    assessment = ClinicalAssessment.objects.create(encounter=encounter, recorded_by=doctor)
    PresentingSymptom.objects.create(
        assessment=assessment,
        symptom_type="nipple_retraction",
        status="recorded",
        recorded_by=doctor,
    )

    eval_result = evaluate_encounter(encounter)
    assert eval_result["triage_level"] == DecisionSupportAssessment.TRIAGE_URGENT
    assert "nipple_retraction" in str(eval_result["reasoning_payload"])
    assert len(eval_result["matched_rule_versions"]) >= 1


@pytest.mark.django_db
def test_rules_engine_birads_suspicious_triggers_urgent(doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1980, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    ImagingReport.objects.create(
        encounter=encounter,
        modality="ultrasound",
        birads_category="5",
        status="recorded",
        recorded_by=doctor,
    )

    eval_result = evaluate_encounter(encounter)
    assert eval_result["triage_level"] == DecisionSupportAssessment.TRIAGE_URGENT
    assert "BI-RADS 5" in str(eval_result["reasoning_payload"])


@pytest.mark.django_db
def test_rules_engine_triple_negative_triggers_urgent(doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1988, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    histo = HistopathologyReport.objects.create(encounter=encounter, recorded_by=doctor)
    BiomarkerResult.objects.create(
        histopathology_report=histo,
        er_status="negative",
        pr_status="negative",
        her2_status="0",
        status="recorded",
        recorded_by=doctor,
    )

    eval_result = evaluate_encounter(encounter)
    assert eval_result["triage_level"] == DecisionSupportAssessment.TRIAGE_URGENT
    assert "Triple-negative" in str(eval_result["reasoning_payload"])


@pytest.mark.django_db
def test_rules_engine_palpable_mass_age_over_40_triggers_priority(doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1970, sex="F")  # Age > 40
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    assessment = ClinicalAssessment.objects.create(encounter=encounter, recorded_by=doctor)
    PresentingSymptom.objects.create(
        assessment=assessment,
        symptom_type="breast_lump",
        status="recorded",
        recorded_by=doctor,
    )

    eval_result = evaluate_encounter(encounter)
    assert eval_result["triage_level"] == DecisionSupportAssessment.TRIAGE_PRIORITY


@pytest.mark.django_db
def test_rules_engine_isolated_pain_triggers_routine(doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1995, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    assessment = ClinicalAssessment.objects.create(encounter=encounter, recorded_by=doctor)
    PresentingSymptom.objects.create(
        assessment=assessment,
        symptom_type="breast_pain",
        status="recorded",
        recorded_by=doctor,
    )

    eval_result = evaluate_encounter(encounter)
    assert eval_result["triage_level"] == DecisionSupportAssessment.TRIAGE_ROUTINE


@pytest.mark.django_db
def test_decision_support_api_evaluate_endpoint(api_client, doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1975, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    assessment = ClinicalAssessment.objects.create(encounter=encounter, recorded_by=doctor)
    PresentingSymptom.objects.create(
        assessment=assessment,
        symptom_type="nipple_retraction",
        status="recorded",
        recorded_by=doctor,
    )

    api_client.force_authenticate(user=doctor)
    res = api_client.post(
        "/api/v1/decision-support/assessments/evaluate/",
        {"encounter_id": encounter.id},
        format="json",
    )
    assert res.status_code == 201
    data = res.json()
    assert data["triage_level"] == DecisionSupportAssessment.TRIAGE_URGENT
    assert "reasoning_payload" in data

    # Create clinician review on assessment
    review_res = api_client.post(
        "/api/v1/decision-support/reviews/",
        {
            "assessment": data["id"],
            "agree_with_recommendation": True,
            "clinician_action_taken": "Urgent biopsy ordered.",
            "notes": "Agreed with urgent triage recommendation.",
        },
        format="json",
    )
    assert review_res.status_code == 201


@pytest.mark.django_db
def test_molecular_subtype_classification(doctor):
    from apps.decision_support.engine import determine_molecular_subtype
    from apps.investigations.models import BiomarkerResult

    bm_lum_a = BiomarkerResult(er_status="positive", pr_status="positive", her2_status="0", ki67_index=10)
    assert determine_molecular_subtype([bm_lum_a]) == "Luminal A"

    bm_lum_b = BiomarkerResult(er_status="positive", pr_status="positive", her2_status="3+", ki67_index=35)
    assert determine_molecular_subtype([bm_lum_b]) == "Luminal B"

    bm_her2 = BiomarkerResult(er_status="negative", pr_status="negative", her2_status="3+", ki67_index=40)
    assert determine_molecular_subtype([bm_her2]) == "HER2-enriched"

    bm_tnbc = BiomarkerResult(er_status="negative", pr_status="negative", her2_status="0", ki67_index=60)
    assert determine_molecular_subtype([bm_tnbc]) == "Triple-negative"

    bm_inc = BiomarkerResult(er_status="pending", pr_status="pending", her2_status="pending")
    assert determine_molecular_subtype([bm_inc]) == "Incomplete"


@pytest.mark.django_db
def test_missing_biomarker_escalation(doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1980, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    # BI-RADS 5 imaging but no biomarkers
    ImagingReport.objects.create(
        encounter=encounter,
        modality="ultrasound",
        birads_category="5",
        status="recorded",
        recorded_by=doctor,
    )

    eval_result = evaluate_encounter(encounter)
    triggers = [t["rule_code"] for t in eval_result["reasoning_payload"]["triggers"]]
    assert "RULE_INCOMPLETE_BIOMARKER" in triggers
    assert eval_result["molecular_subtype"] == "Incomplete"


@pytest.mark.django_db
def test_stage_escalation_rules(doctor):
    from apps.investigations.models import StagingAssessment

    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    StagingAssessment.objects.create(encounter=encounter, overall_stage="IV", m_stage="M1")

    eval_result = evaluate_encounter(encounter)
    assert eval_result["triage_level"] == DecisionSupportAssessment.TRIAGE_URGENT
    triggers = [t["rule_code"] for t in eval_result["reasoning_payload"]["triggers"]]
    assert "RULE_STAGE_IV_PALLIATIVE" in triggers


@pytest.mark.django_db
def test_assessment_review_action_endpoint(api_client, doctor):
    seed_example_rules(user=doctor)
    patient = Patient.objects.create(year_of_birth=1975, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)
    eval_result = evaluate_encounter(encounter)
    assessment = DecisionSupportAssessment.objects.create(
        encounter=encounter,
        triage_level=eval_result["triage_level"],
        summary_recommendation=eval_result["summary_recommendation"],
    )

    api_client.force_authenticate(user=doctor)
    res = api_client.post(
        f"/api/v1/decision-support/assessments/{assessment.id}/review/",
        {
            "agree_with_recommendation": True,
            "clinician_action_taken": "Reviewed and confirmed.",
            "notes": "Looks appropriate.",
        },
        format="json",
    )
    assert res.status_code == 201
    assert res.json()["agree_with_recommendation"] is True
    assert assessment.is_reviewed is True

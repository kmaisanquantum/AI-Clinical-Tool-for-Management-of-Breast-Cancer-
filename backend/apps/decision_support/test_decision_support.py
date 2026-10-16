import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.clinical.models import ClinicalAssessment, Encounter, ExaminationFinding, PresentingSymptom
from apps.decision_support.engine import evaluate_encounter, seed_example_rules
from apps.decision_support.models import ClinicianReview, DecisionSupportAssessment
from apps.investigations.models import BiomarkerResult, HistopathologyReport, ImagingReport
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
    assert "Triple-Negative" in str(eval_result["reasoning_payload"])


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

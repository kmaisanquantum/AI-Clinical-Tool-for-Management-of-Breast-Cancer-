import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, RolePermission, User, UserRole
from apps.clinical.models import (
    ClinicalAssessment,
    Encounter,
    PresentingSymptom,
)
from apps.decision_support.engine import (
    _evaluate_rule_vocabulary,
    determine_molecular_subtype,
    evaluate_encounter,
    seed_example_rules,
)
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


@pytest.fixture
def clinical_admin(db):
    user = User.objects.create_user(username="admin_decision", password="Password12345!")
    role = Role.objects.create(name="Clinical Admin")
    RolePermission.objects.create(role=role, permission_code="manage_rules")
    UserRole.objects.create(user=user, role=role)
    return user


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
    assert "Triple" in str(eval_result["reasoning_payload"])


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
    bm_lum_a = BiomarkerResult(er_status="positive", pr_status="positive", her2_status="0", ki67_index=10, status="recorded")
    key, inc = determine_molecular_subtype([bm_lum_a])
    assert key == "luminal_a"
    assert inc is False

    bm_lum_b = BiomarkerResult(er_status="positive", pr_status="positive", her2_status="3+", ki67_index=35, status="recorded")
    key, inc = determine_molecular_subtype([bm_lum_b])
    assert key == "luminal_b"
    assert inc is False

    bm_her2 = BiomarkerResult(er_status="negative", pr_status="negative", her2_status="3+", ki67_index=40, status="recorded")
    key, inc = determine_molecular_subtype([bm_her2])
    assert key == "her2_enriched"
    assert inc is False

    bm_tnbc = BiomarkerResult(er_status="negative", pr_status="negative", her2_status="0", ki67_index=60, status="recorded")
    key, inc = determine_molecular_subtype([bm_tnbc])
    assert key == "triple_negative"
    assert inc is False

    bm_inc = BiomarkerResult(er_status="pending", pr_status="pending", her2_status="pending", status="recorded")
    key, inc = determine_molecular_subtype([bm_inc])
    assert key == "unclassified"
    assert inc is True


@pytest.mark.django_db
def test_rule_vocabulary_evaluator(doctor):
    bm = BiomarkerResult(er_status="positive", ki67_index=25, status="recorded")
    context = {"biomarker": bm, "patient_age": 45}

    spec_all = {
        "all": [
            {"biomarker": {"field": "ki67_index", "op": ">=", "value": 20}},
            {"patient": {"field": "age", "op": ">=", "value": 40}},
        ]
    }
    assert _evaluate_rule_vocabulary(spec_all, context) is True

    spec_missing = {"missing": {"field": "biomarker.her2_status"}}
    assert _evaluate_rule_vocabulary(spec_missing, context) is True


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
    assert eval_result["incomplete_data"] is True


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
def test_rule_crud_permissions(api_client, doctor, clinical_admin):
    rules = seed_example_rules(user=clinical_admin)
    rv = rules[0]

    # Non-admin user cannot activate/deactivate
    api_client.force_authenticate(user=doctor)
    res_denied = api_client.post(f"/api/v1/decision-support/rule-versions/{rv.id}/activate/")
    assert res_denied.status_code in (403, 401)

    # Clinical admin user can activate
    api_client.force_authenticate(user=clinical_admin)
    res_ok = api_client.post(f"/api/v1/decision-support/rule-versions/{rv.id}/activate/")
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "active"


@pytest.mark.django_db
def test_ai_layer_no_op_when_disabled(doctor):
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)

    eval_result = evaluate_encounter(encounter)
    assert eval_result["ai_suggestion"] == {}
    assert eval_result["ai_provider_version"] == "null-v0.1.0"

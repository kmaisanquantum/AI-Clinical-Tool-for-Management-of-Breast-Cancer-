import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clinical.models import (
    ClinicalAssessment,
    ClinicalNote,
    Encounter,
    ExaminationFinding,
    PresentingSymptom,
)
from apps.registry.models import Patient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def doctor(db):
    return User.objects.create_user(username="dr_kila", password="Password12345!")


@pytest.mark.django_db
def test_clinical_value_conventions_and_models(doctor):
    patient = Patient.objects.create(year_of_birth=1975, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor, source="clinic_visit")
    assessment = ClinicalAssessment.objects.create(encounter=encounter, recorded_by=doctor)
    symptom = PresentingSymptom.objects.create(
        assessment=assessment,
        symptom_type="breast_lump",
        duration_weeks=4,
        status="recorded",
        source="patient_report",
        recorded_by=doctor,
    )
    finding = ExaminationFinding.objects.create(
        assessment=assessment,
        finding_type="mass_size_cm",
        finding_value="3.5",
        status="recorded",
        recorded_by=doctor,
    )
    note = ClinicalNote.objects.create(
        encounter=encounter,
        content="Patient presents with palpable right breast mass.",
        recorded_by=doctor,
    )

    for record in (encounter, assessment, symptom, finding, note):
        assert record.status in dict(record.STATUS_CHOICES)
        assert record.source is not None
        assert record.recorded_by == doctor
        assert record.recorded_at is not None


@pytest.mark.django_db
def test_clinical_soft_delete_prohibits_hard_delete(api_client, doctor):
    patient = Patient.objects.create(year_of_birth=1978, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)

    api_client.force_authenticate(user=doctor)
    res = api_client.delete(f"/api/v1/clinical/encounters/{encounter.id}/")
    assert res.status_code == 200

    encounter.refresh_from_db()
    assert encounter.status == "unavailable"

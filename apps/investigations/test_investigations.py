import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clinical.models import Encounter
from apps.investigations.models import (
    BiomarkerResult,
    HistopathologyReport,
    ImagingReport,
    StagingAssessment,
)
from apps.registry.models import Patient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def doctor(db):
    return User.objects.create_user(username="dr_pathologist", password="Password12345!")


@pytest.mark.django_db
def test_investigations_models_and_molecular_subtyping(doctor):
    patient = Patient.objects.create(year_of_birth=1982, sex="F")
    encounter = Encounter.objects.create(patient=patient, recorded_by=doctor)

    img = ImagingReport.objects.create(
        encounter=encounter,
        modality="ultrasound",
        birads_category="4c",
        findings="Irregular hypoechoic mass.",
        recorded_by=doctor,
    )

    histo = HistopathologyReport.objects.create(
        encounter=encounter,
        specimen_type="core_needle_biopsy",
        histological_type="invasive_ductal_carcinoma",
        grade="3",
        recorded_by=doctor,
    )

    # Test Triple-Negative subtyping
    bm_tnbc = BiomarkerResult.objects.create(
        histopathology_report=histo,
        er_status="negative",
        pr_status="negative",
        her2_status="0",
        ki67_index=35.0,
        recorded_by=doctor,
    )
    assert bm_tnbc.molecular_subtype == "Triple-negative"

    # Test Luminal A subtyping
    bm_lum_a = BiomarkerResult.objects.create(
        histopathology_report=histo,
        er_status="positive",
        pr_status="positive",
        her2_status="0",
        ki67_index=10.0,
        recorded_by=doctor,
    )
    assert bm_lum_a.molecular_subtype == "Luminal A"

    staging = StagingAssessment.objects.create(
        encounter=encounter,
        t_stage="T2",
        n_stage="N1",
        m_stage="M0",
        overall_stage="IIB",
        recorded_by=doctor,
    )

    assert img.birads_category == "4c"
    assert str(staging) == "Staging(T2N1M0 - IIB)"


@pytest.mark.django_db
def test_investigations_api_soft_delete(api_client, doctor):
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    encounter = Encounter.objects.create(patient=patient)
    img = ImagingReport.objects.create(encounter=encounter, modality="mammogram", birads_category="5")

    api_client.force_authenticate(user=doctor)
    res = api_client.delete(f"/api/v1/investigations/imaging-reports/{img.id}/")
    assert res.status_code == 200

    img.refresh_from_db()
    assert img.status == "unavailable"

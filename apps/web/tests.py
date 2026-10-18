import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.models import Role, RolePermission, UserRole
from apps.clinical.models import ClinicalAssessment, Encounter, PresentingSymptom
from apps.investigations.models import ImagingReport, StagingAssessment
from apps.registry.models import Patient, PatientIdentity

User = get_user_model()

PAGES = ["dashboard", "patients", "encounters", "triage", "audit"]


@pytest.mark.django_db
@pytest.mark.parametrize("name", PAGES)
def test_pages_require_login(client, name):
    response = client.get(reverse(f"web:{name}"))
    assert response.status_code == 302
    assert "/login/" in response.headers["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize("name", PAGES)
def test_pages_render_for_signed_in_user(client, name):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    client.force_login(user)

    response = client.get(reverse(f"web:{name}"))

    assert response.status_code == 200
    assert "text/html" in response.headers["Content-Type"]


@pytest.mark.django_db
def test_patient_detail_page_renders(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    client.force_login(user)

    response = client.get(reverse("web:patient-detail", args=[patient.id]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_encounter_detail_page_renders(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    encounter = Encounter.objects.create(patient=patient)
    client.force_login(user)

    response = client.get(reverse("web:encounter-detail", args=[encounter.id]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("web:login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content


@pytest.mark.django_db
def test_dashboard_summary_requires_auth(client):
    assert client.get("/api/v1/dashboard/summary/").status_code in (403, 302)


@pytest.mark.django_db
def test_dashboard_summary_counts(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    encounter = Encounter.objects.create(patient=patient)
    assessment = ClinicalAssessment.objects.create(encounter=encounter)
    PresentingSymptom.objects.create(assessment=assessment, symptom_type="breast_lump")
    client.force_login(user)

    response = client.get("/api/v1/dashboard/summary/")
    body = response.json()

    assert response.status_code == 200
    assert body["counts"]["patients"] == 1
    assert body["counts"]["encounters"] == 1
    assert set(body["triage"]) == {"URGENT", "PRIORITY", "ROUTINE"}
    assert len(body["recent_encounters"]) == 1


@pytest.mark.django_db
def test_dashboard_summary_hides_identity_count_without_permission(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    client.force_login(user)

    body = client.get("/api/v1/dashboard/summary/").json()

    assert "patient_identities" not in body["counts"]


@pytest.mark.django_db
def test_dashboard_summary_shows_identity_count_with_permission(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    role = Role.objects.create(name="Clinical Viewer")
    RolePermission.objects.create(role=role, permission_code="view_patient_identity")
    UserRole.objects.create(user=user, role=role)
    client.force_login(user)

    body = client.get("/api/v1/dashboard/summary/").json()

    assert body["counts"]["patient_identities"] == 0


@pytest.mark.django_db
def test_current_user_endpoint_reports_roles_and_permissions(client):
    user = User.objects.create_user(
        username="clinician", password="test-pass-1234", first_name="Ana"
    )
    role = Role.objects.create(name="Oncologist")
    RolePermission.objects.create(role=role, permission_code="view_patient_identity")
    UserRole.objects.create(user=user, role=role)
    client.force_login(user)

    body = client.get("/api/v1/accounts/me/").json()

    assert body["username"] == "clinician"
    assert body["first_name"] == "Ana"
    assert body["roles"] == ["Oncologist"]
    assert body["permissions"] == ["view_patient_identity"]
    assert body["can_view_patient_identity"] is True


@pytest.mark.django_db
def test_current_user_requires_auth(client):
    assert client.get("/api/v1/accounts/me/").status_code in (403, 302)


@pytest.mark.django_db
def test_investigations_can_be_filtered_by_encounter(client):
    """The encounter detail page scopes imaging and staging to a single encounter."""
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    first = Encounter.objects.create(patient=Patient.objects.create(year_of_birth=1970, sex="F"))
    second = Encounter.objects.create(patient=Patient.objects.create(year_of_birth=1960, sex="F"))
    ImagingReport.objects.create(encounter=first, modality="mri", birads_category="5")
    ImagingReport.objects.create(encounter=second, modality="ultrasound", birads_category="2")
    StagingAssessment.objects.create(encounter=first, overall_stage="IIB")
    client.force_login(user)

    imaging = client.get(f"/api/v1/investigations/imaging-reports/?encounter={first.id}").json()
    staging = client.get(f"/api/v1/investigations/staging-assessments/?encounter={first.id}").json()

    assert len(imaging) == 1
    assert imaging[0]["modality"] == "mri"
    assert len(staging) == 1
    assert staging[0]["overall_stage"] == "IIB"


@pytest.mark.django_db
def test_encounters_can_be_filtered_by_patient(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    Encounter.objects.create(patient=patient)
    Encounter.objects.create(patient=Patient.objects.create(year_of_birth=1960, sex="F"))
    client.force_login(user)

    body = client.get(f"/api/v1/clinical/encounters/?patient={patient.id}").json()

    assert len(body) == 1
    assert body[0]["patient"] == patient.id


@pytest.mark.django_db
def test_patient_identities_can_be_filtered_by_patient(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    role = Role.objects.create(name="Oncologist")
    RolePermission.objects.create(role=role, permission_code="view_patient_identity")
    UserRole.objects.create(user=user, role=role)
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    PatientIdentity.objects.create(patient=patient, full_name="Demo One", national_id_or_mrn="MRN-1")
    other = Patient.objects.create(year_of_birth=1960, sex="F")
    PatientIdentity.objects.create(patient=other, full_name="Demo Two", national_id_or_mrn="MRN-2")
    client.force_login(user)

    body = client.get(f"/api/v1/registry/patient-identities/?patient={patient.id}").json()

    assert len(body) == 1
    assert body[0]["national_id_or_mrn"] == "MRN-1"


@pytest.mark.django_db
def test_triage_evaluation_endpoint_returns_assessment(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    encounter = Encounter.objects.create(patient=Patient.objects.create(year_of_birth=1970, sex="F"))
    client.force_login(user)

    response = client.post(
        "/api/v1/decision-support/assessments/evaluate/",
        data={"encounter_id": encounter.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["triage_level"] in {"URGENT", "PRIORITY", "ROUTINE"}
    assert body["encounter"] == encounter.id


@pytest.mark.django_db
def test_ui_pages_require_login(client):
    urls = [
        "/ui/patients/",
        "/ui/patients/1/",
        "/ui/assessments/",
        "/ui/assessments/1/",
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 302
        assert "/login/" in response.headers["Location"]


@pytest.mark.django_db
def test_ui_pages_render_for_authenticated_user(client):
    user = User.objects.create_user(username="clinician", password="test-pass-1234")
    patient = Patient.objects.create(year_of_birth=1970, sex="F")
    encounter = Encounter.objects.create(patient=patient)
    from apps.decision_support.models import DecisionSupportAssessment
    assessment = DecisionSupportAssessment.objects.create(
        encounter=encounter,
        triage_level="URGENT",
        summary_recommendation="Immediate oncology referral required.",
    )
    client.force_login(user)

    routes = [
        "/ui/patients/",
        f"/ui/patients/{patient.id}/",
        "/ui/assessments/",
        f"/ui/assessments/{assessment.id}/",
    ]
    for url in routes:
        response = client.get(url)
        assert response.status_code == 200
        assert "text/html" in response.headers["Content-Type"]

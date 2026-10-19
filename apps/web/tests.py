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


@pytest.mark.django_db
def test_patient_registration_form_permission_denial(client):
    user = User.objects.create_user(username="viewer_only", password="test-pass-1234")
    client.force_login(user)

    response = client.get("/ui/patients/new/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_patient_registration_form_happy_path(client):
    user = User.objects.create_user(username="clinician_recorder", password="test-pass-1234")
    role = Role.objects.create(name="Clinician Recorder")
    RolePermission.objects.create(role=role, permission_code="record_clinical")
    RolePermission.objects.create(role=role, permission_code="view_patient_identity")
    UserRole.objects.create(user=user, role=role)
    client.force_login(user)

    response = client.post(
        "/ui/patients/new/",
        {
            "year_of_birth": 1978,
            "sex": "F",
            "region": "Rabaul",
            "full_name": "Jane Doe",
            "national_id_or_mrn": "MRN-9999",
            "phone_number": "+675 7000 0000",
        },
    )
    assert response.status_code == 302
    patient = Patient.objects.filter(region="Rabaul").first()
    assert patient is not None
    assert patient.year_of_birth == 1978
    assert PatientIdentity.objects.filter(patient=patient, national_id_or_mrn="MRN-9999").exists()


@pytest.mark.django_db
def test_investigation_and_evaluation_workflow(client):
    user = User.objects.create_user(username="clinician_doc", password="test-pass-1234")
    role = Role.objects.create(name="Oncologist")
    RolePermission.objects.create(role=role, permission_code="record_clinical")
    UserRole.objects.create(user=user, role=role)
    client.force_login(user)

    patient = Patient.objects.create(year_of_birth=1965, sex="F", region="Goroka")
    encounter = Encounter.objects.create(patient=patient, recorded_by=user)

    # Post investigations
    inv_res = client.post(
        f"/ui/encounters/{encounter.id}/investigations/",
        {
            "specimen_type": "Core needle biopsy",
            "histological_type": "Invasive ductal carcinoma",
            "grade": "3",
            "er_status": "negative",
            "pr_status": "negative",
            "her2_status": "0",
            "ki67_index": "50.0",
            "t_stage": "T2",
            "n_stage": "N1",
            "m_stage": "M0",
            "overall_stage": "IIB",
        },
    )
    assert inv_res.status_code == 302

    # Trigger evaluation
    eval_res = client.post(f"/ui/encounters/{encounter.id}/evaluate/")
    assert eval_res.status_code == 302

    from apps.decision_support.models import DecisionSupportAssessment
    assessment = DecisionSupportAssessment.objects.filter(encounter=encounter).first()
    assert assessment is not None
    assert assessment.triage_level == "URGENT"
    assert assessment.molecular_subtype in ("Triple-negative", "Triple Negative")

    # Review assessment via form
    rev_res = client.post(
        f"/ui/assessments/{assessment.id}/review/",
        {
            "agree_with_recommendation": "true",
            "clinician_action_taken": "Urgent MDT referral confirmed.",
            "notes": "Agreed.",
        },
    )
    assert rev_res.status_code == 302
    assert assessment.is_reviewed is True


@pytest.mark.django_db
def test_settings_user_management_permissions_and_workflow(client):
    admin_user = User.objects.create_user(username="admin_user", password="test-pass-1234")
    admin_role = Role.objects.create(name="User Admin")
    RolePermission.objects.create(role=admin_role, permission_code="manage_users")
    UserRole.objects.create(user=admin_user, role=admin_role)

    unprivileged_user = User.objects.create_user(username="normal_user", password="test-pass-1234")
    superuser = User.objects.create_superuser(username="root_admin", password="test-pass-1234")

    # 1. Unprivileged user gets 403 on settings URLs
    client.force_login(unprivileged_user)
    assert client.get("/ui/settings/users/").status_code == 403
    assert client.get("/ui/settings/users/new/").status_code == 403
    assert client.get("/ui/settings/roles/").status_code == 403

    # 2. Admin user can view users list and roles
    client.force_login(admin_user)
    assert client.get("/ui/settings/users/").status_code == 200
    assert client.get("/ui/settings/roles/").status_code == 200

    # 3. Create user
    create_res = client.post(
        "/ui/settings/users/new/",
        {
            "username": "new_doctor",
            "first_name": "New",
            "last_name": "Doctor",
            "email": "doctor@example.test",
            "password": "Password12345!",
            "confirm_password": "Password12345!",
            "is_active": "on",
            "roles": [admin_role.id],
        },
    )
    assert create_res.status_code == 302
    created_user = User.objects.get(username="new_doctor")
    assert created_user.email == "doctor@example.test"
    from apps.audit.models import AuditEvent
    assert AuditEvent.objects.filter(resource_type="User", resource_id=str(created_user.id), action="CREATE").exists()

    # 4. Edit user
    edit_res = client.post(
        f"/ui/settings/users/{created_user.id}/edit/",
        {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@example.test",
            "is_active": "on",
            "roles": [],
        },
    )
    assert edit_res.status_code == 302
    created_user.refresh_from_db()
    assert created_user.first_name == "Updated"

    # 5. Reset password
    reset_res = client.post(
        f"/ui/settings/users/{created_user.id}/reset-password/",
        {
            "new_password": "NewSecretPassword1!",
            "confirm_password": "NewSecretPassword1!",
        },
    )
    assert reset_res.status_code == 302
    created_user.refresh_from_db()
    assert created_user.check_password("NewSecretPassword1!")

    # 6. Admin cannot deactivate self
    self_deactivate_res = client.post(f"/ui/settings/users/{admin_user.id}/toggle-active/")
    assert self_deactivate_res.status_code == 302
    admin_user.refresh_from_db()
    assert admin_user.is_active is True

    # 7. Non-superuser cannot edit, reset-password, or deactivate superuser
    assert client.get(f"/ui/settings/users/{superuser.id}/edit/").status_code == 403
    assert client.get(f"/ui/settings/users/{superuser.id}/reset-password/").status_code == 403
    assert client.post(f"/ui/settings/users/{superuser.id}/toggle-active/").status_code == 403

    # 8. Deactivate target user
    deactivate_res = client.post(f"/ui/settings/users/{created_user.id}/toggle-active/")
    assert deactivate_res.status_code == 302
    created_user.refresh_from_db()
    assert created_user.is_active is False


@pytest.mark.django_db
def test_change_own_password_view(client):
    user = User.objects.create_user(username="self_user", password="OldPassword123!")
    client.force_login(user)

    res = client.post(
        "/ui/settings/users/me/",
        {
            "new_password": "NewSecretPassword123!",
            "confirm_password": "NewSecretPassword123!",
        },
    )
    assert res.status_code == 302
    user.refresh_from_db()
    assert user.check_password("NewSecretPassword123!")

    from apps.audit.models import AuditEvent
    assert AuditEvent.objects.filter(resource_type="User", resource_id=str(user.id), details__action="change_own_password").exists()


@pytest.mark.django_db
def test_navbar_visibility_for_settings(client):
    normal_user = User.objects.create_user(username="regular_user", password="test-pass-1234")
    admin_user = User.objects.create_user(username="admin_user", password="test-pass-1234")
    admin_role = Role.objects.create(name="User Admin")
    RolePermission.objects.create(role=admin_role, permission_code="manage_users")
    UserRole.objects.create(user=admin_user, role=admin_role)
    superuser = User.objects.create_superuser(username="superuser", password="test-pass-1234")

    # Regular user does not see Settings in navbar
    client.force_login(normal_user)
    resp = client.get("/")
    assert b"Settings" not in resp.content

    # Admin user sees Settings link in navbar
    client.force_login(admin_user)
    resp = client.get("/")
    assert b"Settings" in resp.content

    # Superuser sees Settings link in navbar
    client.force_login(superuser)
    resp = client.get("/")
    assert b"Settings" in resp.content

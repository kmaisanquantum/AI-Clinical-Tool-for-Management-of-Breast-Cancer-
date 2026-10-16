import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, RolePermission, User, UserRole
from apps.registry.models import Patient, PatientIdentity


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def clinician_user(db):
    return User.objects.create_user(username="clinician1", password="Password12345!")


@pytest.fixture
def registrar_user(db):
    user = User.objects.create_user(username="registrar1", password="Password12345!")
    role = Role.objects.create(name="Registrar")
    UserRole.objects.create(user=user, role=role)
    RolePermission.objects.create(role=role, permission_code="view_patient_identity")
    return user


@pytest.mark.django_db
def test_patient_and_identity_models():
    patient = Patient.objects.create(year_of_birth=1980, sex="F", region="National Capital District")
    identity = PatientIdentity.objects.create(
        patient=patient,
        full_name="Synthetic Patient A",
        national_id_or_mrn="SYN-MRN-001",
        phone_number="+67570000000",
    )

    assert patient.pseudonym_id is not None
    assert str(patient).startswith("Patient(")
    assert str(identity).startswith("Identity(Synthetic Patient A")


@pytest.mark.django_db
def test_patient_identity_permission_restriction(api_client, clinician_user, registrar_user):
    patient = Patient.objects.create(year_of_birth=1985, sex="F")
    PatientIdentity.objects.create(
        patient=patient,
        full_name="Synthetic Patient B",
        national_id_or_mrn="SYN-MRN-002",
    )

    # Clinician without 'view_patient_identity' permission is forbidden
    api_client.force_authenticate(user=clinician_user)
    res_patients = api_client.get("/api/v1/registry/patients/")
    assert res_patients.status_code == 200

    res_identity = api_client.get("/api/v1/registry/patient-identities/")
    assert res_identity.status_code == 403

    # Registrar with 'view_patient_identity' permission is allowed
    api_client.force_authenticate(user=registrar_user)
    res_identity_allowed = api_client.get("/api/v1/registry/patient-identities/")
    assert res_identity_allowed.status_code == 200
    assert len(res_identity_allowed.json()) == 1


@pytest.mark.django_db
def test_patient_serializer_excludes_identity(api_client, clinician_user):
    patient = Patient.objects.create(year_of_birth=1990, sex="F", region="Morobe")
    PatientIdentity.objects.create(
        patient=patient,
        full_name="Identifiable Name Should Not Be In Patient Serializer",
        national_id_or_mrn="SYN-MRN-003",
    )

    api_client.force_authenticate(user=clinician_user)
    res = api_client.get(f"/api/v1/registry/patients/{patient.id}/")
    assert res.status_code == 200
    data = res.json()
    assert "full_name" not in data
    assert "national_id_or_mrn" not in data
    assert "pseudonym_id" in data

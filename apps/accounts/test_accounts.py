import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, RolePermission, User, UserRole
from apps.accounts.permissions import user_has_permission


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def normal_user(db):
    return User.objects.create_user(username="dr_smith", password="Password12345!")


@pytest.mark.django_db
def test_user_and_role_creation():
    user = User.objects.create_user(username="testuser", password="Password12345!")
    role = Role.objects.create(name="Oncologist", description="Breast Oncologist")
    user_role = UserRole.objects.create(user=user, role=role)
    perm = RolePermission.objects.create(role=role, permission_code="view_clinical")

    assert str(user_role) == "testuser -> Oncologist"
    assert str(perm) == "Oncologist : view_clinical"
    assert user_has_permission(user, "view_clinical")
    assert not user_has_permission(user, "view_patient_identity")


@pytest.mark.django_db
def test_superuser_has_all_permissions():
    admin = User.objects.create_superuser(username="admin", password="Password12345!")
    assert user_has_permission(admin, "any_random_permission")


@pytest.mark.django_db
def test_accounts_api_deny_anonymous(api_client):
    res = api_client.get("/api/v1/accounts/users/")
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_accounts_api_authenticated(api_client, normal_user):
    api_client.force_authenticate(user=normal_user)
    res = api_client.get("/api/v1/accounts/users/")
    assert res.status_code == 200
    assert len(res.json()) >= 1

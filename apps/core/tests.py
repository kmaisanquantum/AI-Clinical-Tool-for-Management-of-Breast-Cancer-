import pytest
from django.conf import settings


@pytest.mark.django_db
def test_health_ok(client):
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_schema_requires_no_secrets(client):
    assert client.get("/api/v1/schema/").status_code == 200


def test_secure_defaults():
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]
    assert settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    assert settings.DATABASES["default"]["PORT"] == "5432"

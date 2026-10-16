from unittest.mock import patch

import pytest
from django.conf import settings
from django.db import DatabaseError


@pytest.mark.django_db
def test_health_ok(client):
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


def test_health_db_failure(client):
    with patch("django.db.connection.cursor", side_effect=DatabaseError("DB unreachable")):
        r = client.get("/api/v1/health/")
        assert r.status_code == 200
        assert r.json() == {"status": "degraded", "database": "unavailable"}


def test_root_redirect(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/api/v1/docs/"


@pytest.mark.django_db
def test_schema_requires_no_secrets(client):
    assert client.get("/api/v1/schema/").status_code == 200


def test_secure_defaults():
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]
    assert settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    assert settings.DATABASES["default"]["PORT"] == "5432"

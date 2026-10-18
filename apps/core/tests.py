from unittest.mock import patch

import pytest
from django.conf import settings
from django.db import DatabaseError


@pytest.mark.django_db
def test_health_ok(client):
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_db_failure(client):
    with patch("django.db.connection.cursor", side_effect=DatabaseError("DB unreachable")):
        r = client.get("/api/v1/health/")
        assert r.status_code == 200
        assert r.json() == {"status": "degraded", "database": "unavailable"}


@pytest.mark.django_db
def test_root_redirect(client):
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login/?next=/"


@pytest.mark.django_db
def test_schema_requires_no_secrets(client):
    assert client.get("/api/v1/schema/").status_code == 200


def test_secure_defaults():
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]
    assert settings.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")
    assert settings.DATABASES["default"]["ENGINE"] in {
        "django.db.backends.sqlite3",
        "django.db.backends.postgresql",
    }


def test_missing_secret_key_does_not_crash_boot(tmp_path, monkeypatch):
    """A missing DJANGO_SECRET_KEY must not kill the WSGI worker (restart loop)."""
    import importlib

    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    monkeypatch.setenv("DJANGO_SECRET_KEY_FILE", str(tmp_path / "secret"))
    monkeypatch.setenv("USE_SQLITE", "1")
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.base")

    base = importlib.reload(importlib.import_module("config.settings.base"))

    assert base.SECRET_KEY
    assert (tmp_path / "secret").read_text().strip() == base.SECRET_KEY

    # Reloading must reuse the persisted key so sessions survive restarts.
    reloaded = importlib.reload(base)
    assert reloaded.SECRET_KEY == base.SECRET_KEY

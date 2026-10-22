from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.db import DatabaseError

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.decision_support.models import MolecularSubtype, RuleVersion
from apps.registry.models import Patient, PatientIdentity


@pytest.mark.django_db
def test_health_ok(client):
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_db_failure(client):
    with patch("apps.core.views.connection.cursor", side_effect=DatabaseError("DB unreachable")):
        r = client.get("/api/v1/health/")
        assert r.status_code == 200
        assert r.json() == {"status": "degraded", "database": "unavailable"}


@pytest.mark.django_db
def test_root_redirect(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/login/?next=/" in r.headers["Location"]


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


@pytest.mark.django_db
def test_seed_demo_data_without_patients_by_default():
    """Default seed_demo_data seeds system users, roles, rules, and subtypes but NO patients."""
    call_command("seed_demo_data")

    assert User.objects.filter(username="clinical_admin").exists()
    assert User.objects.filter(username="doctor").exists()
    assert Role.objects.filter(name="Clinical Admin").exists()
    assert MolecularSubtype.objects.count() >= 5
    assert RuleVersion.objects.count() >= 1

    assert Patient.objects.count() == 0
    assert PatientIdentity.objects.count() == 0


@pytest.mark.django_db
def test_seed_demo_data_with_patients_flag():
    """Passing --with-patients seeds the 5 synthetic demo patients."""
    call_command("seed_demo_data", with_patients=True)

    assert Patient.objects.count() == 5
    assert PatientIdentity.objects.filter(national_id_or_mrn__startswith="MRN-DEMO-").count() == 5


@pytest.mark.django_db
def test_purge_demo_data_requires_confirm():
    """purge_demo_data without --confirm must raise CommandError."""
    with pytest.raises(CommandError) as exc_info:
        call_command("purge_demo_data")
    assert "Refusing to purge demo data without confirmation" in str(exc_info.value)


@pytest.mark.django_db
def test_purge_demo_data_removes_patients_and_audit_events():
    """purge_demo_data --confirm removes synthetic demo patients and audit events, preserving system setup."""
    # First seed data with patients
    call_command("seed_demo_data", with_patients=True)

    assert Patient.objects.count() == 5
    assert AuditEvent.objects.filter(details__seeded=True).count() > 0

    # Purge demo data
    call_command("purge_demo_data", confirm=True)

    assert Patient.objects.count() == 0
    assert PatientIdentity.objects.filter(national_id_or_mrn__startswith="MRN-DEMO-").count() == 0
    assert AuditEvent.objects.filter(details__seeded=True).count() == 0

    # System setup preserved
    assert User.objects.filter(username="clinical_admin").exists()
    assert User.objects.filter(username="doctor").exists()
    assert MolecularSubtype.objects.count() >= 5
    assert RuleVersion.objects.count() >= 1


@pytest.mark.django_db
def test_purge_demo_data_idempotent():
    """purge_demo_data --confirm is safe to run when database has no demo patient records."""
    call_command("purge_demo_data", confirm=True)
    assert Patient.objects.count() == 0

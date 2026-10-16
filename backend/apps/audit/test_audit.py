import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.utils import log_audit_event


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="auditor", password="Password12345!")


@pytest.mark.django_db
def test_audit_event_append_only_enforcement(user):
    event = log_audit_event(
        action="READ",
        resource_type="Patient",
        resource_id="101",
        user=user,
        details={"query": "patient_list"},
    )
    assert event.id is not None
    assert event.username_snapshot == "auditor"

    # Modification of existing event must raise PermissionError
    event.action = "UPDATE"
    with pytest.raises(PermissionError, match="append-only"):
        event.save()

    # Deletion of existing event must raise PermissionError
    with pytest.raises(PermissionError, match="append-only"):
        event.delete()


@pytest.mark.django_db
def test_audit_api_no_update_or_delete_endpoints(api_client, user):
    event = log_audit_event(
        action="CREATE",
        resource_type="Encounter",
        resource_id="5",
        user=user,
    )

    api_client.force_authenticate(user=user)

    # List & Retrieve work
    res_list = api_client.get("/api/v1/audit/events/")
    assert res_list.status_code == 200

    res_get = api_client.get(f"/api/v1/audit/events/{event.id}/")
    assert res_get.status_code == 200

    # PUT/PATCH/DELETE endpoints do not exist (405 Method Not Allowed)
    res_put = api_client.put(f"/api/v1/audit/events/{event.id}/", {"action": "MODIFIED"})
    assert res_put.status_code == 405

    res_patch = api_client.patch(f"/api/v1/audit/events/{event.id}/", {"action": "MODIFIED"})
    assert res_patch.status_code == 405

    res_del = api_client.delete(f"/api/v1/audit/events/{event.id}/")
    assert res_del.status_code == 405

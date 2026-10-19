"""
Navigation and permission context processors for the web UI templates.
"""

from apps.accounts.permissions import user_has_permission


def nav_permissions(request) -> dict:
    """
    Exposes permission flags globally to template context:
    - can_manage_users: True if superuser or user has 'manage_users' permission code.
    - can_view_identity: True if superuser or user has 'view_patient_identity' permission code.
    - can_record_clinical: True if superuser or user has 'record_clinical' permission code.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "can_manage_users": False,
            "can_view_identity": False,
            "can_record_clinical": False,
        }

    return {
        "can_manage_users": user.is_superuser or user_has_permission(user, "manage_users"),
        "can_view_identity": user.is_superuser or user_has_permission(user, "view_patient_identity"),
        "can_record_clinical": user.is_superuser or user_has_permission(user, "record_clinical"),
    }

from rest_framework import permissions


def user_has_permission(user, permission_code: str) -> bool:
    """Check if user is authenticated and has the specified permission_code via assigned roles or superuser status."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from .models import RolePermission
    return RolePermission.objects.filter(
        role__user_roles__user=user,
        permission_code=permission_code,
    ).exists()


class HasRolePermission(permissions.BasePermission):
    """
    Custom permission checking if user has the permission_code configured on the view.
    Views using this should define `required_permission = 'permission_code'`.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        required_perm = getattr(view, "required_permission", None)
        if not required_perm:
            return True
        return user_has_permission(request.user, required_perm)


class HasPatientIdentityPermission(permissions.BasePermission):
    """
    Strict permission restriction for access to PATIENT_IDENTITY records.
    Only users with 'view_patient_identity' permission code (or superusers) are allowed.
    """
    def has_permission(self, request, view):
        return user_has_permission(request.user, "view_patient_identity")


class HasManageRulesPermission(permissions.BasePermission):
    """
    Permission check for decision rule administration and rule CRUD.
    Only users with 'manage_rules' permission code (or superusers/clinical_admin role) are allowed.
    """
    def has_permission(self, request, view):
        return user_has_permission(request.user, "manage_rules")

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Role, RolePermission, User, UserRole
from .permissions import user_has_permission
from .serializers import (
    RolePermissionSerializer,
    RoleSerializer,
    UserRoleSerializer,
    UserSerializer,
)


@extend_schema(tags=["Accounts"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def current_user(request):
    """Identity, roles and effective permission codes for the signed-in user."""
    user = request.user
    roles = list(
        Role.objects.filter(user_roles__user=user).values_list("name", flat=True).distinct()
    )
    permission_codes = sorted(
        RolePermission.objects.filter(role__user_roles__user=user)
        .values_list("permission_code", flat=True)
        .distinct()
    )
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "roles": roles,
            "permissions": permission_codes,
            "can_view_patient_identity": user_has_permission(user, "view_patient_identity"),
        }
    )


@extend_schema(tags=["Accounts"])
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Accounts"])
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all().order_by("id")
    serializer_class = RoleSerializer
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Accounts"])
class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all().order_by("id")
    serializer_class = UserRoleSerializer
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)


@extend_schema(tags=["Accounts"])
class RolePermissionViewSet(viewsets.ModelViewSet):
    queryset = RolePermission.objects.all().order_by("id")
    serializer_class = RolePermissionSerializer
    permission_classes = (IsAuthenticated,)

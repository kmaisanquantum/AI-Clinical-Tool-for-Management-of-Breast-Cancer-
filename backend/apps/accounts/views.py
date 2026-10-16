from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Role, RolePermission, User, UserRole
from .serializers import (
    RolePermissionSerializer,
    RoleSerializer,
    UserRoleSerializer,
    UserSerializer,
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

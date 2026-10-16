from rest_framework import serializers

from .models import Role, RolePermission, User, UserRole


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "is_active", "is_staff")
        read_only_fields = ("id", "is_staff")


class RolePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermission
        fields = ("id", "role", "permission_code")


class RoleSerializer(serializers.ModelSerializer):
    permissions = RolePermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ("id", "name", "description", "permissions", "created_at", "updated_at")


class UserRoleSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserRole
        fields = ("id", "user", "username", "role", "role_name", "assigned_at", "assigned_by")
        read_only_fields = ("id", "assigned_at")

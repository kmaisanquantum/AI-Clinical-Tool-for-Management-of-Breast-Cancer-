from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for decision-support platform."""
    pass


class Role(models.Model):
    """System role assigned to platform users (e.g. Clinician, Oncologist, Registrar, Admin)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """Mapping between users and roles."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="user_roles")
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_user_roles",
    )

    class Meta:
        unique_together = ("user", "role")

    def __str__(self):
        return f"{self.user.username} -> {self.role.name}"


class RolePermission(models.Model):
    """Specific permissions granted to roles (e.g. view_patient_identity, record_clinical)."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="permissions")
    permission_code = models.CharField(max_length=100)

    class Meta:
        unique_together = ("role", "permission_code")

    def __str__(self):
        return f"{self.role.name} : {self.permission_code}"

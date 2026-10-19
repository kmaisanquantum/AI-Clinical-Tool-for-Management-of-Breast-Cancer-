"""Management command to create or update demo user accounts with roles."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, RolePermission, UserRole
from apps.audit.models import AuditEvent

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update a demo user account with a designated role and optional admin access."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            required=True,
            help="Username for the demo user.",
        )
        parser.add_argument(
            "--password",
            required=True,
            help="Password for the demo user (bypasses validators for demo ease).",
        )
        parser.add_argument(
            "--role",
            default="Oncologist",
            help="Role assigned to the demo user (default: Oncologist).",
        )
        parser.add_argument(
            "--admin",
            action="store_true",
            help="Grant user-management admin permission (manage_users) via role assignment.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        role_name = options["role"]
        is_admin = options["admin"]

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@example.test", "first_name": username.title()},
        )
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"

        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": f"{role_name} role (demo account)"},
        )
        if is_admin:
            RolePermission.objects.get_or_create(role=role, permission_code="manage_users")

        UserRole.objects.get_or_create(user=user, role=role, defaults={"assigned_by": user})

        AuditEvent.objects.create(
            user=user,
            action="CREATE" if created else "UPDATE",
            resource_type="User",
            resource_id=str(user.id),
            details={"username": username, "role": role_name, "is_admin": is_admin},
        )

        admin_msg = " with manage_users admin access" if is_admin else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} demo user '{username}' with role '{role_name}'{admin_msg}."
            )
        )

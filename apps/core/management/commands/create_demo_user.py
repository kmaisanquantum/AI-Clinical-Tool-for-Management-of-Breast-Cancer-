"""Management command to create or update demo user accounts with roles."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role, UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update a demo user account with a designated role."

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

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        role_name = options["role"]

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
        UserRole.objects.get_or_create(user=user, role=role, defaults={"assigned_by": user})

        self.stdout.write(
            self.style.SUCCESS(
                f"{action} demo user '{username}' with role '{role_name}'."
            )
        )

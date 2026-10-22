"""Management command to purge synthetic demo patient data while preserving system setup."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.registry.models import Patient, PatientIdentity


class Command(BaseCommand):
    help = "Purge synthetic demo patient data (MRN-DEMO-*) from the database while preserving accounts, roles, and rules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirmation flag required to execute purging of synthetic patient data.",
        )

    def handle(self, *args, **options):
        confirm = options.get("confirm", False)
        if not confirm:
            raise CommandError("Refusing to purge demo data without confirmation. Pass --confirm to execute.")

        with transaction.atomic():
            demo_identities = PatientIdentity.objects.filter(national_id_or_mrn__startswith="MRN-DEMO-")
            demo_patient_ids = list(demo_identities.values_list("patient_id", flat=True))
            patients_qs = Patient.objects.filter(id__in=demo_patient_ids)

            patient_count = patients_qs.count()

            # Find seeded audit events
            seeded_audit_events = AuditEvent.objects.filter(details__seeded=True)
            audit_count = seeded_audit_events.count()

            # Delete Patients (Django cascades FK deletes to related records)
            patients_qs.delete()
            seeded_audit_events.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully purged synthetic demo data: {patient_count} patient(s) and {audit_count} audit event(s) removed."
                )
            )

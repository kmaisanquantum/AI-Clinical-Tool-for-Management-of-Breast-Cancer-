"""Seed synthetic demonstration data for local and preview environments.

Every record created here is fabricated. No real patient data is involved.
Command is idempotent and safe to execute multiple times.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, RolePermission, UserRole
from apps.audit.models import AuditEvent
from apps.clinical.models import (
    ClinicalAssessment,
    ClinicalNote,
    Encounter,
    PresentingSymptom,
)
from apps.decision_support.engine import evaluate_encounter, seed_example_rules
from apps.decision_support.models import DecisionSupportAssessment
from apps.investigations.models import (
    BiomarkerResult,
    HistopathologyReport,
    ImagingReport,
    StagingAssessment,
)
from apps.registry.models import Patient, PatientIdentity

User = get_user_model()

DEMO_USERS = [
    ("doctor", "Oncologist", ["view_patient_identity", "record_clinical"]),
    ("oncologist", "Oncologist", ["view_patient_identity", "record_clinical"]),
    ("registrar", "Registrar", ["record_clinical"]),
    ("analyst", "Analyst", []),
]

PATIENTS = [
    {
        "year_of_birth": 1968, "sex": "F", "region": "Port Moresby",
        "name": "Demo Patient One", "mrn": "MRN-DEMO-0001",
        "symptoms": [("breast_lump", 6), ("skin_tethering", 3)],
        "birads": "5",
        "biomarkers": {"er": "positive", "pr": "positive", "her2": "3+", "ki67": 35},
        "staging": ("T2", "N1", "M0", "IIB"),
    },
    {
        "year_of_birth": 1955, "sex": "F", "region": "Lae",
        "name": "Demo Patient Two", "mrn": "MRN-DEMO-0002",
        "symptoms": [("nipple_retraction", 8)],
        "birads": "4c",
        "biomarkers": {"er": "negative", "pr": "negative", "her2": "0", "ki67": 60},
        "staging": ("T3", "N2", "M0", "IIIA"),
    },
    {
        "year_of_birth": 1982, "sex": "F", "region": "Mount Hagen",
        "name": "Demo Patient Three", "mrn": "MRN-DEMO-0003",
        "symptoms": [("breast_lump", 4)],
        "birads": "3",
        "biomarkers": {"er": "positive", "pr": "positive", "her2": "1+", "ki67": 12},
        "staging": ("T1", "N0", "M0", "I"),
    },
    {
        "year_of_birth": 1975, "sex": "F", "region": "Madang",
        "name": "Demo Patient Four", "mrn": "MRN-DEMO-0004",
        "symptoms": [("breast_pain", 2)],
        "birads": "2",
        "biomarkers": None,
        "staging": ("T0", "N0", "M0", "0"),
    },
]


class Command(BaseCommand):
    help = "Seed synthetic demonstration data idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="DemoPass!2025",
            help="Password assigned to each seeded demo user.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]

        users = {}
        for username, role_name, permission_codes in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.test", "first_name": username.title()},
            )
            if created:
                user.set_password(password)
                user.save()

            role, _ = Role.objects.get_or_create(
                name=role_name,
                defaults={"description": f"{role_name} role (demo data)"},
            )
            for code in permission_codes:
                RolePermission.objects.get_or_create(role=role, permission_code=code)
            UserRole.objects.get_or_create(user=user, role=role, defaults={"assigned_by": user})
            users[username] = user

        author = users["oncologist"]
        seed_example_rules(user=author)

        for spec in PATIENTS:
            identity = PatientIdentity.objects.filter(national_id_or_mrn=spec["mrn"]).first()
            if identity:
                patient = identity.patient
            else:
                patient = Patient.objects.create(
                    year_of_birth=spec["year_of_birth"],
                    sex=spec["sex"],
                    region=spec["region"],
                )
                PatientIdentity.objects.create(
                    patient=patient,
                    full_name=spec["name"],
                    national_id_or_mrn=spec["mrn"],
                    phone_number="+675 000 0000",
                    address=f"{spec['region']}, Papua New Guinea",
                )

            encounter = Encounter.objects.filter(patient=patient).first()
            if not encounter:
                encounter = Encounter.objects.create(
                    patient=patient,
                    encounter_type="diagnostic",
                    recorded_by=author,
                    encounter_date=timezone.now(),
                )
                assessment = ClinicalAssessment.objects.create(
                    encounter=encounter,
                    assessment_type="initial_assessment",
                    summary_notes=f"Synthetic demonstration encounter for {spec['region']}.",
                    recorded_by=author,
                )
                for symptom_type, duration in spec["symptoms"]:
                    PresentingSymptom.objects.create(
                        assessment=assessment,
                        symptom_type=symptom_type,
                        duration_weeks=duration,
                        severity="moderate",
                        recorded_by=author,
                    )

                ClinicalNote.objects.create(
                    encounter=encounter,
                    note_type="progress_note",
                    content="Synthetic note. For interface demonstration only.",
                    recorded_by=author,
                )

                ImagingReport.objects.create(
                    encounter=encounter,
                    modality="ultrasound",
                    birads_category=spec["birads"],
                    impression="Synthetic imaging impression.",
                    recorded_by=author,
                )

                if spec["biomarkers"]:
                    bm = spec["biomarkers"]
                    report = HistopathologyReport.objects.create(
                        encounter=encounter,
                        specimen_type="core_needle_biopsy",
                        histological_type="Invasive ductal carcinoma",
                        grade="3",
                        recorded_by=author,
                    )
                    BiomarkerResult.objects.create(
                        histopathology_report=report,
                        er_status=bm["er"],
                        pr_status=bm["pr"],
                        her2_status=bm["her2"],
                        ki67_index=bm["ki67"],
                        recorded_by=author,
                    )

                t, n, m, overall = spec["staging"]
                StagingAssessment.objects.create(
                    encounter=encounter,
                    t_stage=t, n_stage=n, m_stage=m, overall_stage=overall,
                    recorded_by=author,
                )

                result = evaluate_encounter(encounter)
                triage = DecisionSupportAssessment.objects.create(
                    encounter=encounter,
                    triage_level=result["triage_level"],
                    summary_recommendation=result["summary_recommendation"],
                    reasoning_payload=result["reasoning_payload"],
                )
                if result["matched_rule_versions"]:
                    triage.rule_versions_applied.set(result["matched_rule_versions"])

                AuditEvent.objects.create(
                    user=author,
                    action="CREATE",
                    resource_type="Encounter",
                    resource_id=str(encounter.id),
                    details={"seeded": True},
                )

        self.stdout.write(self.style.SUCCESS("Synthetic demo data seeded successfully."))

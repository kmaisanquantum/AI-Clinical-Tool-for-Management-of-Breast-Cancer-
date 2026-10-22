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
from apps.decision_support.models import (
    DecisionSupportAssessment,
    ManagementPlan,
    MolecularSubtype,
)
from apps.investigations.models import (
    BiomarkerResult,
    HistopathologyReport,
    ImagingReport,
    StagingAssessment,
)
from apps.registry.models import Patient, PatientIdentity

User = get_user_model()

DEMO_USERS = [
    ("clinical_admin", "Clinical Admin", ["manage_users", "manage_rules", "view_patient_identity", "record_clinical"]),
    ("doctor", "Oncologist", ["manage_users", "view_patient_identity", "record_clinical"]),
    ("oncologist", "Oncologist", ["view_patient_identity", "record_clinical"]),
    ("registrar", "Registrar", ["record_clinical"]),
    ("analyst", "Analyst", []),
]

SUBTYPES = [
    ("luminal_a", "Luminal A-like", "ER+/PR+, HER2-negative, low Ki-67 (<20%)"),
    ("luminal_b", "Luminal B-like", "ER+/PR+, HER2-positive OR high Ki-67 (>=20%)"),
    ("her2_enriched", "HER2-enriched", "ER-negative, PR-negative, HER2-positive"),
    ("triple_negative", "Triple-negative", "ER-negative, PR-negative, HER2-negative"),
    ("unclassified", "Unclassified", "Incomplete or non-conclusive biomarker profile"),
]

PATIENTS = [
    {
        "year_of_birth": 1968, "sex": "F", "region": "Port Moresby",
        "name": "Demo Patient One (Luminal A)", "mrn": "MRN-DEMO-0001",
        "symptoms": [("breast_lump", 4)],
        "birads": "4a",
        "biomarkers": {"er": "positive", "pr": "positive", "her2": "0", "ki67": 10},
        "staging": ("T1", "N0", "M0", "I"),
    },
    {
        "year_of_birth": 1955, "sex": "F", "region": "Lae",
        "name": "Demo Patient Two (Luminal B)", "mrn": "MRN-DEMO-0002",
        "symptoms": [("breast_lump", 8), ("skin_tethering", 3)],
        "birads": "5",
        "biomarkers": {"er": "positive", "pr": "positive", "her2": "3+", "ki67": 35},
        "staging": ("T3", "N1", "M0", "IIIA"),
    },
    {
        "year_of_birth": 1982, "sex": "F", "region": "Mount Hagen",
        "name": "Demo Patient Three (HER2-Enriched)", "mrn": "MRN-DEMO-0003",
        "symptoms": [("nipple_retraction", 6)],
        "birads": "5",
        "biomarkers": {"er": "negative", "pr": "negative", "her2": "3+", "ki67": 45},
        "staging": ("T2", "N1", "M0", "IIB"),
    },
    {
        "year_of_birth": 1975, "sex": "F", "region": "Madang",
        "name": "Demo Patient Four (Triple Negative)", "mrn": "MRN-DEMO-0004",
        "symptoms": [("breast_lump", 6), ("axillary_mass", 2)],
        "birads": "5",
        "biomarkers": {"er": "negative", "pr": "negative", "her2": "0", "ki67": 65},
        "staging": ("T2", "N2", "M0", "IIIA"),
    },
    {
        "year_of_birth": 1970, "sex": "F", "region": "Goroka",
        "name": "Demo Patient Five (Incomplete Biomarkers)", "mrn": "MRN-DEMO-0005",
        "symptoms": [("breast_lump", 5)],
        "birads": "5",
        "biomarkers": None,  # Incomplete biomarker case
        "staging": ("T2", "N0", "M0", "IIA"),
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
        parser.add_argument(
            "--doctor-password",
            default="doctor",
            help="Password assigned specifically to the demo 'doctor' user.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "WARNING: Seeding demo accounts and synthetic clinical data for demonstration/testing purposes only."
            )
        )
        password = options["password"]
        doctor_password = options.get("doctor_password") or "doctor"

        # 1. Seed MolecularSubtype lookup table
        for name, display_name, desc in SUBTYPES:
            MolecularSubtype.objects.get_or_create(
                name=name,
                defaults={"display_name": display_name, "description": desc, "is_active": True},
            )

        # 2. Seed Users & Roles
        users = {}
        for username, role_name, permission_codes in DEMO_USERS:
            pwd = doctor_password if username == "doctor" else password
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@example.test", "first_name": username.title()},
            )
            user.set_password(pwd)
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

        # 3. Seed Patients & Encounters
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

                report = HistopathologyReport.objects.create(
                    encounter=encounter,
                    specimen_type="core_needle_biopsy",
                    histological_type="Invasive ductal carcinoma",
                    grade="3",
                    recorded_by=author,
                )

                if spec["biomarkers"]:
                    bm = spec["biomarkers"]
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
                    molecular_subtype=result.get("molecular_subtype", ""),
                    molecular_subtype_fk=result.get("molecular_subtype_fk"),
                    incomplete_data=result.get("incomplete_data", False),
                    management_plan=result.get("management_plan", []),
                    referral_recommendation=result.get("referral_recommendation", ""),
                    ai_suggestion=result.get("ai_suggestion", {}),
                    ai_provider_version=result.get("ai_provider_version", ""),
                    reasoning_payload=result["reasoning_payload"],
                )

                for item in result.get("management_plan", []):
                    ManagementPlan.objects.create(
                        assessment=triage,
                        plan_type=item.get("plan_type", "general"),
                        recommendation_text=item.get("recommendation_text", ""),
                        requires_referral=item.get("requires_referral", False),
                        referral_destination=item.get("referral_destination", ""),
                        timeframe_days=item.get("timeframe_days"),
                        resource_level=item.get("resource_level", ""),
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

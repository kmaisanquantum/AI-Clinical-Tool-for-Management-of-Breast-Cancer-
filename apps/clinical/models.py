from django.conf import settings
from django.db import models
from django.utils import timezone


class ClinicalValueBase(models.Model):
    """
    Abstract base model ensuring every clinical value entity carries:
    - status (recorded / pending / unavailable / not_indicated / not_recorded)
    - source
    - recorded_by
    - recorded_at
    """
    STATUS_RECORDED = "recorded"
    STATUS_PENDING = "pending"
    STATUS_UNAVAILABLE = "unavailable"
    STATUS_NOT_INDICATED = "not_indicated"
    STATUS_NOT_RECORDED = "not_recorded"

    STATUS_CHOICES = (
        (STATUS_RECORDED, "Recorded"),
        (STATUS_PENDING, "Pending"),
        (STATUS_UNAVAILABLE, "Unavailable"),
        (STATUS_NOT_INDICATED, "Not Indicated"),
        (STATUS_NOT_RECORDED, "Not Recorded"),
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_RECORDED)
    source = models.CharField(max_length=100, default="clinician_entry")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_recorded",
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True


class Encounter(ClinicalValueBase):
    """Clinical encounter representing a patient interaction."""
    ENCOUNTER_TYPE_CHOICES = (
        ("screening", "Screening"),
        ("diagnostic", "Diagnostic"),
        ("follow_up", "Follow-up"),
        ("mdt_review", "MDT Review"),
    )

    patient = models.ForeignKey(
        "registry.Patient",
        on_delete=models.CASCADE,
        related_name="encounters",
    )
    encounter_type = models.CharField(
        max_length=50,
        choices=ENCOUNTER_TYPE_CHOICES,
        default="screening",
    )
    encounter_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Encounter({self.id} - Patient {self.patient_id} - {self.encounter_type})"


class ClinicalAssessment(ClinicalValueBase):
    """Assessment recorded during an encounter."""
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.CASCADE,
        related_name="assessments",
    )
    assessment_type = models.CharField(max_length=50, default="initial_assessment")
    summary_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Assessment({self.id} - Encounter {self.encounter_id})"


class PresentingSymptom(ClinicalValueBase):
    """Presenting symptom observed or reported during assessment."""
    assessment = models.ForeignKey(
        ClinicalAssessment,
        on_delete=models.CASCADE,
        related_name="presenting_symptoms",
    )
    symptom_type = models.CharField(max_length=100)
    duration_weeks = models.PositiveIntegerField(null=True, blank=True)
    severity = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Symptom({self.symptom_type} - {self.status})"


class ExaminationFinding(ClinicalValueBase):
    """Physical examination finding."""
    assessment = models.ForeignKey(
        ClinicalAssessment,
        on_delete=models.CASCADE,
        related_name="examination_findings",
    )
    finding_type = models.CharField(max_length=100)
    finding_value = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"Finding({self.finding_type}={self.finding_value})"


class ClinicalNote(ClinicalValueBase):
    """Clinical progress or consultation note."""
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    note_type = models.CharField(max_length=50, default="progress_note")
    content = models.TextField()

    def __str__(self):
        return f"ClinicalNote({self.id} - {self.note_type})"

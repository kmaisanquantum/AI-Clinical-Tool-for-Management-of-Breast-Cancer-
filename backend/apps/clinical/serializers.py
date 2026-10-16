from rest_framework import serializers
from .models import (
    ClinicalAssessment,
    ClinicalNote,
    Encounter,
    ExaminationFinding,
    PresentingSymptom,
)


class PresentingSymptomSerializer(serializers.ModelSerializer):
    class Meta:
        model = PresentingSymptom
        fields = (
            "id",
            "assessment",
            "symptom_type",
            "duration_weeks",
            "severity",
            "notes",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
        )
        read_only_fields = ("id",)


class ExaminationFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExaminationFinding
        fields = (
            "id",
            "assessment",
            "finding_type",
            "finding_value",
            "description",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
        )
        read_only_fields = ("id",)


class ClinicalAssessmentSerializer(serializers.ModelSerializer):
    presenting_symptoms = PresentingSymptomSerializer(many=True, read_only=True)
    examination_findings = ExaminationFindingSerializer(many=True, read_only=True)

    class Meta:
        model = ClinicalAssessment
        fields = (
            "id",
            "encounter",
            "assessment_type",
            "summary_notes",
            "presenting_symptoms",
            "examination_findings",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ClinicalNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalNote
        fields = (
            "id",
            "encounter",
            "note_type",
            "content",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
        )
        read_only_fields = ("id",)


class EncounterSerializer(serializers.ModelSerializer):
    assessments = ClinicalAssessmentSerializer(many=True, read_only=True)
    notes = ClinicalNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Encounter
        fields = (
            "id",
            "patient",
            "encounter_type",
            "encounter_date",
            "assessments",
            "notes",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

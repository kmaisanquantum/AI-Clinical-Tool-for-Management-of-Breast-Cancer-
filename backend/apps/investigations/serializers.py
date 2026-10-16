from rest_framework import serializers
from .models import BiomarkerResult, HistopathologyReport, ImagingReport, StagingAssessment


class BiomarkerResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BiomarkerResult
        fields = (
            "id",
            "histopathology_report",
            "er_status",
            "pr_status",
            "her2_status",
            "ki67_index",
            "molecular_subtype",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class HistopathologyReportSerializer(serializers.ModelSerializer):
    biomarkers = BiomarkerResultSerializer(many=True, read_only=True)

    class Meta:
        model = HistopathologyReport
        fields = (
            "id",
            "encounter",
            "specimen_type",
            "histological_type",
            "grade",
            "margin_status",
            "description",
            "biomarkers",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ImagingReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagingReport
        fields = (
            "id",
            "encounter",
            "modality",
            "birads_category",
            "findings",
            "impression",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class StagingAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StagingAssessment
        fields = (
            "id",
            "encounter",
            "t_stage",
            "n_stage",
            "m_stage",
            "overall_stage",
            "status",
            "source",
            "recorded_by",
            "recorded_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

from rest_framework import serializers

from .models import (
    ClinicianReview,
    DecisionRule,
    DecisionSupportAssessment,
    Guideline,
    GuidelineVersion,
    ManagementPlan,
    MolecularSubtype,
    RuleVersion,
)


class MolecularSubtypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MolecularSubtype
        fields = ("id", "name", "display_name", "description", "is_active")


class GuidelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guideline
        fields = ("id", "code", "title", "description", "created_at", "updated_at")


class GuidelineVersionSerializer(serializers.ModelSerializer):
    guideline_code = serializers.CharField(source="guideline.code", read_only=True)

    class Meta:
        model = GuidelineVersion
        fields = (
            "id",
            "guideline",
            "guideline_code",
            "version_number",
            "source_citation",
            "approved_by",
            "approved_at",
            "is_active",
            "created_at",
            "updated_at",
        )


class DecisionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DecisionRule
        fields = ("id", "guideline_version", "rule_code", "name", "description")


class RuleVersionSerializer(serializers.ModelSerializer):
    rule_code = serializers.CharField(source="decision_rule.rule_code", read_only=True)

    class Meta:
        model = RuleVersion
        fields = (
            "id",
            "decision_rule",
            "rule_code",
            "version_number",
            "logic_spec",
            "source_citation",
            "approved_by",
            "approved_at",
            "status",
            "created_at",
            "updated_at",
        )


class ManagementPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManagementPlan
        fields = (
            "id",
            "plan_type",
            "recommendation_text",
            "requires_referral",
            "referral_destination",
            "timeframe_days",
            "resource_level",
            "created_at",
        )


class ClinicianReviewSerializer(serializers.ModelSerializer):
    reviewer_username = serializers.CharField(source="reviewer.username", read_only=True)

    class Meta:
        model = ClinicianReview
        fields = (
            "id",
            "assessment",
            "reviewer",
            "reviewer_username",
            "agree_with_recommendation",
            "clinician_action_taken",
            "notes",
            "reviewed_at",
        )
        read_only_fields = ("id", "reviewer", "reviewed_at")


class ClinicianReviewCreateSerializer(serializers.Serializer):
    agree_with_recommendation = serializers.BooleanField(required=True)
    clinician_action_taken = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class DecisionSupportAssessmentSerializer(serializers.ModelSerializer):
    clinician_reviews = ClinicianReviewSerializer(many=True, read_only=True)
    management_plans = ManagementPlanSerializer(many=True, read_only=True)
    is_reviewed = serializers.BooleanField(read_only=True)

    class Meta:
        model = DecisionSupportAssessment
        fields = (
            "id",
            "encounter",
            "rule_versions_applied",
            "triage_level",
            "summary_recommendation",
            "molecular_subtype",
            "molecular_subtype_fk",
            "incomplete_data",
            "management_plan",
            "management_plans",
            "referral_recommendation",
            "ai_suggestion",
            "ai_provider_version",
            "reasoning_payload",
            "calculated_at",
            "is_reviewed",
            "clinician_reviews",
        )
        read_only_fields = ("id", "calculated_at", "is_reviewed")


class EncounterEvaluationRequestSerializer(serializers.Serializer):
    encounter_id = serializers.IntegerField(required=True)

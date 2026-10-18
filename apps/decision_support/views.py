from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clinical.models import Encounter

from .engine import evaluate_encounter
from .models import (
    ClinicianReview,
    DecisionRule,
    DecisionSupportAssessment,
    Guideline,
    GuidelineVersion,
    RuleVersion,
)
from .serializers import (
    ClinicianReviewCreateSerializer,
    ClinicianReviewSerializer,
    DecisionRuleSerializer,
    DecisionSupportAssessmentSerializer,
    EncounterEvaluationRequestSerializer,
    GuidelineSerializer,
    GuidelineVersionSerializer,
    RuleVersionSerializer,
)


@extend_schema(tags=["Decision Support"])
class GuidelineViewSet(viewsets.ModelViewSet):
    queryset = Guideline.objects.all().order_by("code")
    serializer_class = GuidelineSerializer
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Decision Support"])
class GuidelineVersionViewSet(viewsets.ModelViewSet):
    queryset = GuidelineVersion.objects.all().order_by("-created_at")
    serializer_class = GuidelineVersionSerializer
    filterset_fields = ("guideline", "is_active")
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Decision Support"])
class DecisionRuleViewSet(viewsets.ModelViewSet):
    queryset = DecisionRule.objects.all().order_by("rule_code")
    serializer_class = DecisionRuleSerializer
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Decision Support"])
class RuleVersionViewSet(viewsets.ModelViewSet):
    queryset = RuleVersion.objects.all().order_by("-created_at")
    serializer_class = RuleVersionSerializer
    filterset_fields = ("decision_rule", "status")
    permission_classes = (IsAuthenticated,)


@extend_schema(tags=["Decision Support"])
class DecisionSupportAssessmentViewSet(viewsets.ModelViewSet):
    queryset = DecisionSupportAssessment.objects.all().order_by("-calculated_at")
    serializer_class = DecisionSupportAssessmentSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("encounter", "triage_level")

    @extend_schema(
        request=EncounterEvaluationRequestSerializer,
        responses={201: DecisionSupportAssessmentSerializer},
        description="Run deterministic rules engine evaluation against an encounter and store decision support assessment.",
    )
    @action(detail=False, methods=["post"], url_path="evaluate")
    def evaluate(self, request):
        serializer = EncounterEvaluationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        encounter_id = serializer.validated_data["encounter_id"]

        try:
            encounter = Encounter.objects.get(id=encounter_id)
        except Encounter.DoesNotExist:
            return Response(
                {"detail": f"Encounter with ID {encounter_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        eval_result = evaluate_encounter(encounter)

        assessment = DecisionSupportAssessment.objects.create(
            encounter=encounter,
            triage_level=eval_result["triage_level"],
            summary_recommendation=eval_result["summary_recommendation"],
            molecular_subtype=eval_result.get("molecular_subtype", ""),
            management_plan=eval_result.get("management_plan", []),
            referral_recommendation=eval_result.get("referral_recommendation", ""),
            reasoning_payload=eval_result["reasoning_payload"],
        )

        matched_rule_versions = eval_result.get("matched_rule_versions", [])
        if matched_rule_versions:
            assessment.rule_versions_applied.set(matched_rule_versions)

        out_serializer = DecisionSupportAssessmentSerializer(assessment)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ClinicianReviewCreateSerializer,
        responses={201: ClinicianReviewSerializer},
        description="Record human clinician review / confirmation / override of decision support assessment.",
    )
    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        assessment = self.get_object()
        serializer = ClinicianReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review_record = ClinicianReview.objects.create(
            assessment=assessment,
            reviewer=request.user,
            agree_with_recommendation=serializer.validated_data["agree_with_recommendation"],
            clinician_action_taken=serializer.validated_data.get("clinician_action_taken", ""),
            notes=serializer.validated_data.get("notes", ""),
        )

        out_serializer = ClinicianReviewSerializer(review_record)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Decision Support"])
class ClinicianReviewViewSet(viewsets.ModelViewSet):
    queryset = ClinicianReview.objects.all().order_by("-reviewed_at")
    serializer_class = ClinicianReviewSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("assessment", "agree_with_recommendation")

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)

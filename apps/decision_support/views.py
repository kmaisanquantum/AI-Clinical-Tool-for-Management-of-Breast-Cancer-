from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasManageRulesPermission
from apps.audit.models import AuditEvent
from apps.clinical.models import Encounter

from .engine import evaluate_encounter
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
from .serializers import (
    ClinicianReviewCreateSerializer,
    ClinicianReviewSerializer,
    DecisionRuleSerializer,
    DecisionSupportAssessmentSerializer,
    EncounterEvaluationRequestSerializer,
    GuidelineSerializer,
    GuidelineVersionSerializer,
    MolecularSubtypeSerializer,
    RuleVersionSerializer,
)


@extend_schema(tags=["Decision Support"])
class MolecularSubtypeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MolecularSubtype.objects.all().order_by("name")
    serializer_class = MolecularSubtypeSerializer
    permission_classes = (IsAuthenticated,)


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

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "activate", "deactivate"):
            return [IsAuthenticated(), HasManageRulesPermission()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        rv = serializer.save()
        AuditEvent.objects.create(
            user=self.request.user,
            action="CREATE",
            resource_type="RuleVersion",
            resource_id=str(rv.id),
            details={"status": rv.status, "version_number": rv.version_number},
        )

    def perform_update(self, serializer):
        rv = serializer.save()
        AuditEvent.objects.create(
            user=self.request.user,
            action="UPDATE",
            resource_type="RuleVersion",
            resource_id=str(rv.id),
            details={"status": rv.status, "version_number": rv.version_number},
        )

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        rule_version = self.get_object()
        rule_version.status = "active"
        rule_version.approved_by = request.user
        rule_version.approved_at = timezone.now()
        rule_version.save()

        AuditEvent.objects.create(
            user=request.user,
            action="UPDATE",
            resource_type="RuleVersion",
            resource_id=str(rule_version.id),
            details={"action": "activate", "status": "active", "version_number": rule_version.version_number},
        )

        serializer = self.get_serializer(rule_version)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        rule_version = self.get_object()
        rule_version.status = "deprecated"
        rule_version.save()

        AuditEvent.objects.create(
            user=request.user,
            action="UPDATE",
            resource_type="RuleVersion",
            resource_id=str(rule_version.id),
            details={"action": "deactivate", "status": "deprecated", "version_number": rule_version.version_number},
        )

        serializer = self.get_serializer(rule_version)
        return Response(serializer.data)


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
            molecular_subtype_fk=eval_result.get("molecular_subtype_fk"),
            incomplete_data=eval_result.get("incomplete_data", False),
            management_plan=eval_result.get("management_plan", []),
            referral_recommendation=eval_result.get("referral_recommendation", ""),
            ai_suggestion=eval_result.get("ai_suggestion", {}),
            ai_provider_version=eval_result.get("ai_provider_version", ""),
            reasoning_payload=eval_result["reasoning_payload"],
        )

        # Create ManagementPlan records
        plans = eval_result.get("management_plan", [])
        for item in plans:
            ManagementPlan.objects.create(
                assessment=assessment,
                plan_type=item.get("plan_type", "general"),
                recommendation_text=item.get("recommendation_text", ""),
                requires_referral=item.get("requires_referral", False),
                referral_destination=item.get("referral_destination", ""),
                timeframe_days=item.get("timeframe_days"),
                resource_level=item.get("resource_level", ""),
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

        AuditEvent.objects.create(
            user=request.user,
            action="CREATE",
            resource_type="ClinicianReview",
            resource_id=str(review_record.id),
            details={
                "assessment_id": assessment.id,
                "agree": review_record.agree_with_recommendation,
            },
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
        rev = serializer.save(reviewer=self.request.user)
        AuditEvent.objects.create(
            user=self.request.user,
            action="CREATE",
            resource_type="ClinicianReview",
            resource_id=str(rev.id),
            details={
                "assessment_id": rev.assessment_id,
                "agree": rev.agree_with_recommendation,
            },
        )

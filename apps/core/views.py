from django.db import connection
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import user_has_permission
from apps.audit.models import AuditEvent
from apps.clinical.models import Encounter
from apps.decision_support.models import (
    DecisionSupportAssessment,
    Guideline,
    RuleVersion,
)
from apps.investigations.models import BiomarkerResult, ImagingReport, StagingAssessment
from apps.registry.models import Patient, PatientIdentity


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class HealthView(APIView):
    """Liveness/readiness probe. Exposes no patient data or version details."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            return Response({"status": "ok", "database": "ok"})
        except Exception:  # noqa: BLE001
            return Response({"status": "degraded", "database": "unavailable"}, status=200)


@extend_schema(tags=["Core"])
class DashboardSummaryView(APIView):
    """
    Aggregate counts and recent activity for the clinical dashboard.

    The identity count is omitted for users without the view_patient_identity
    permission so the endpoint never reveals the existence of identifiable records.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        triage_counts = {
            row["triage_level"]: row["count"]
            for row in DecisionSupportAssessment.objects.values("triage_level").annotate(count=Count("id"))
        }

        recent_encounters = [
            {
                "id": enc.id,
                "patient": enc.patient_id,
                "encounter_type": enc.encounter_type,
                "encounter_date": enc.encounter_date,
                "status": enc.status,
            }
            for enc in Encounter.objects.select_related("patient").order_by("-encounter_date")[:5]
        ]

        recent_assessments = [
            {
                "id": a.id,
                "encounter": a.encounter_id,
                "triage_level": a.triage_level,
                "calculated_at": a.calculated_at,
            }
            for a in DecisionSupportAssessment.objects.order_by("-calculated_at")[:5]
        ]

        payload = {
            "counts": {
                "patients": Patient.objects.count(),
                "encounters": Encounter.objects.count(),
                "imaging_reports": ImagingReport.objects.count(),
                "biomarker_results": BiomarkerResult.objects.count(),
                "staging_assessments": StagingAssessment.objects.count(),
                "decision_assessments": DecisionSupportAssessment.objects.count(),
                "guidelines": Guideline.objects.count(),
                "active_rule_versions": RuleVersion.objects.filter(status="active").count(),
                "audit_events": AuditEvent.objects.count(),
            },
            "triage": {
                "URGENT": triage_counts.get("URGENT", 0),
                "PRIORITY": triage_counts.get("PRIORITY", 0),
                "ROUTINE": triage_counts.get("ROUTINE", 0),
            },
            "recent_encounters": recent_encounters,
            "recent_assessments": recent_assessments,
        }

        if user_has_permission(request.user, "view_patient_identity"):
            payload["counts"]["patient_identities"] = PatientIdentity.objects.count()

        return Response(payload)

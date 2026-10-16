from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import BiomarkerResult, HistopathologyReport, ImagingReport, StagingAssessment
from .serializers import (
    BiomarkerResultSerializer,
    HistopathologyReportSerializer,
    ImagingReportSerializer,
    StagingAssessmentSerializer,
)


class BaseInvestigationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        if not serializer.validated_data.get("recorded_by") and self.request.user.is_authenticated:
            serializer.save(recorded_by=self.request.user)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.status = "unavailable"
        instance.save()
        return Response(
            {"detail": "Hard deletion of investigation data is prohibited. Status updated to unavailable."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Investigations"])
class ImagingReportViewSet(BaseInvestigationViewSet):
    queryset = ImagingReport.objects.all().order_by("-created_at")
    serializer_class = ImagingReportSerializer


@extend_schema(tags=["Investigations"])
class HistopathologyReportViewSet(BaseInvestigationViewSet):
    queryset = HistopathologyReport.objects.all().order_by("-created_at")
    serializer_class = HistopathologyReportSerializer


@extend_schema(tags=["Investigations"])
class BiomarkerResultViewSet(BaseInvestigationViewSet):
    queryset = BiomarkerResult.objects.all().order_by("-created_at")
    serializer_class = BiomarkerResultSerializer


@extend_schema(tags=["Investigations"])
class StagingAssessmentViewSet(BaseInvestigationViewSet):
    queryset = StagingAssessment.objects.all().order_by("-created_at")
    serializer_class = StagingAssessmentSerializer

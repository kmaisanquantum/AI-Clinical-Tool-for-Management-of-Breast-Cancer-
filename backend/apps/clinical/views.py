from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ClinicalAssessment,
    ClinicalNote,
    Encounter,
    ExaminationFinding,
    PresentingSymptom,
)
from .serializers import (
    ClinicalAssessmentSerializer,
    ClinicalNoteSerializer,
    EncounterSerializer,
    ExaminationFindingSerializer,
    PresentingSymptomSerializer,
)


class BaseClinicalViewSet(viewsets.ModelViewSet):
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
            {"detail": "Hard deletion of clinical data is prohibited. Status updated to unavailable."},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Clinical"])
class EncounterViewSet(BaseClinicalViewSet):
    queryset = Encounter.objects.all().order_by("-created_at")
    serializer_class = EncounterSerializer


@extend_schema(tags=["Clinical"])
class ClinicalAssessmentViewSet(BaseClinicalViewSet):
    queryset = ClinicalAssessment.objects.all().order_by("-created_at")
    serializer_class = ClinicalAssessmentSerializer


@extend_schema(tags=["Clinical"])
class PresentingSymptomViewSet(BaseClinicalViewSet):
    queryset = PresentingSymptom.objects.all().order_by("-id")
    serializer_class = PresentingSymptomSerializer


@extend_schema(tags=["Clinical"])
class ExaminationFindingViewSet(BaseClinicalViewSet):
    queryset = ExaminationFinding.objects.all().order_by("-id")
    serializer_class = ExaminationFindingSerializer


@extend_schema(tags=["Clinical"])
class ClinicalNoteViewSet(BaseClinicalViewSet):
    queryset = ClinicalNote.objects.all().order_by("-id")
    serializer_class = ClinicalNoteSerializer

from rest_framework.routers import DefaultRouter

from .views import (
    ClinicalAssessmentViewSet,
    ClinicalNoteViewSet,
    EncounterViewSet,
    ExaminationFindingViewSet,
    PresentingSymptomViewSet,
)

router = DefaultRouter()
router.register(r"encounters", EncounterViewSet, basename="encounter")
router.register(r"assessments", ClinicalAssessmentViewSet, basename="assessment")
router.register(r"symptoms", PresentingSymptomViewSet, basename="symptom")
router.register(r"findings", ExaminationFindingViewSet, basename="finding")
router.register(r"notes", ClinicalNoteViewSet, basename="note")

urlpatterns = router.urls

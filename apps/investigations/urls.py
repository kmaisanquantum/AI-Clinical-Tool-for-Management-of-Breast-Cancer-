from rest_framework.routers import DefaultRouter

from .views import (
    BiomarkerResultViewSet,
    HistopathologyReportViewSet,
    ImagingReportViewSet,
    StagingAssessmentViewSet,
)

router = DefaultRouter()
router.register(r"imaging-reports", ImagingReportViewSet, basename="imaging-report")
router.register(r"histopathology-reports", HistopathologyReportViewSet, basename="histopathology-report")
router.register(r"biomarkers", BiomarkerResultViewSet, basename="biomarker")
router.register(r"staging-assessments", StagingAssessmentViewSet, basename="staging-assessment")

urlpatterns = router.urls

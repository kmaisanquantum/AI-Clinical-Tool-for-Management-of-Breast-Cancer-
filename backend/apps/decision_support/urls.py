from rest_framework.routers import DefaultRouter
from .views import (
    ClinicianReviewViewSet,
    DecisionRuleViewSet,
    DecisionSupportAssessmentViewSet,
    GuidelineVersionViewSet,
    GuidelineViewSet,
    RuleVersionViewSet,
)

router = DefaultRouter()
router.register(r"guidelines", GuidelineViewSet, basename="guideline")
router.register(r"guideline-versions", GuidelineVersionViewSet, basename="guideline-version")
router.register(r"rules", DecisionRuleViewSet, basename="rule")
router.register(r"rule-versions", RuleVersionViewSet, basename="rule-version")
router.register(r"assessments", DecisionSupportAssessmentViewSet, basename="assessment")
router.register(r"reviews", ClinicianReviewViewSet, basename="review")

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter

from .views import PatientIdentityViewSet, PatientViewSet

router = DefaultRouter()
router.register(r"patients", PatientViewSet, basename="patient")
router.register(r"patient-identities", PatientIdentityViewSet, basename="patient-identity")

urlpatterns = router.urls

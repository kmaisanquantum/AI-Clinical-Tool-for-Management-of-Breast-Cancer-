from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import HasPatientIdentityPermission

from .models import Patient, PatientIdentity
from .serializers import PatientIdentitySerializer, PatientSerializer


@extend_schema(tags=["Registry"])
class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all().order_by("-created_at")
    serializer_class = PatientSerializer
    permission_classes = (IsAuthenticated,)
    filterset_fields = ("sex", "region")
    search_fields = ("pseudonym_id", "region")


@extend_schema(tags=["Registry"])
class PatientIdentityViewSet(viewsets.ModelViewSet):
    queryset = PatientIdentity.objects.all().order_by("-created_at")
    serializer_class = PatientIdentitySerializer
    permission_classes = (IsAuthenticated, HasPatientIdentityPermission)
    filterset_fields = ("patient",)
    search_fields = ("full_name", "national_id_or_mrn")

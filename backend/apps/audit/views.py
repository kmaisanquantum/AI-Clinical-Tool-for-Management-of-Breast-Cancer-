from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import AuditEvent
from .serializers import AuditEventSerializer


@extend_schema(tags=["Audit"])
class AuditEventViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Append-only viewset for AuditEvent.
    Provides list, retrieve, and create actions only.
    Update (PUT/PATCH) and Destroy (DELETE) endpoints do NOT exist.
    """
    queryset = AuditEvent.objects.all().order_by("-timestamp")
    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        if not serializer.validated_data.get("user") and self.request.user.is_authenticated:
            serializer.save(user=self.request.user, username_snapshot=self.request.user.username)
        else:
            serializer.save()

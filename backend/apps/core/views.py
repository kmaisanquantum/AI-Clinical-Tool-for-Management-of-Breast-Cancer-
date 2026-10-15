from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness/readiness probe. Exposes no patient data or version details."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            return Response({"status": "ok", "database": "ok"})
        except Exception:
            return Response({"status": "degraded", "database": "unavailable"}, status=503)

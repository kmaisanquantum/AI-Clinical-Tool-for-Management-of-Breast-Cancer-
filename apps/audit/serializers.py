from rest_framework import serializers

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "timestamp",
            "user",
            "username_snapshot",
            "action",
            "resource_type",
            "resource_id",
            "ip_address",
            "user_agent",
            "details",
        )
        read_only_fields = ("id", "timestamp")

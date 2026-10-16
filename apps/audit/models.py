from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """
    Append-only audit event log recording who/what/when for all clinical reads/writes.
    Deletion or modification of audit records is strictly prevented.
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    username_snapshot = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=50)  # e.g., READ, CREATE, UPDATE, DELETE, ACCESS_DENIED
    resource_type = models.CharField(max_length=100)  # e.g., Patient, Encounter, BiomarkerResult
    resource_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError("AuditEvent records are append-only and cannot be updated.")
        if self.user and not self.username_snapshot:
            self.username_snapshot = getattr(self.user, "username", "")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("AuditEvent records are append-only and cannot be deleted.")

    def __str__(self):
        return f"AuditEvent({self.timestamp} | {self.username_snapshot or 'System'} | {self.action} {self.resource_type}:{self.resource_id})"

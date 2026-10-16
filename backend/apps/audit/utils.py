from .models import AuditEvent


def log_audit_event(
    action: str,
    resource_type: str,
    resource_id: str = "",
    user=None,
    request=None,
    details: dict | None = None,
) -> AuditEvent:
    """
    Utility function to log an audit event for clinical reads and writes.
    """
    if details is None:
        details = {}

    ip_address = None
    user_agent = ""

    if request:
        if not user and hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]

    return AuditEvent.objects.create(
        user=user if (user and user.is_authenticated) else None,
        username_snapshot=getattr(user, "username", "") if user else "",
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )

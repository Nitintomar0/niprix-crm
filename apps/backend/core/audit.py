from core.models import AuditLog


def log_action(*, actor, company, action, target, metadata=None, reason=""):
    """Record safe, non-secret metadata for sensitive business actions."""
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        company=company,
        action=action,
        target_type=target._meta.label,
        target_id=str(target.pk),
        metadata=metadata or {},
        reason=reason,
    )

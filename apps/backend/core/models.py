from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="audit_logs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_actions")
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=120)
    target_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["company", "created_at"]), models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"{self.action} {self.target_type}:{self.target_id}"


class Notification(models.Model):
    """A durable, tenant-scoped in-app notification.

    Notifications intentionally belong to a user rather than a role.  This
    keeps delivery decisions in the service layer, makes unread state private,
    and prevents a later role change from exposing historic company events.
    """

    class Type(models.TextChoices):
        LEAD_ASSIGNED = "LEAD_ASSIGNED", "Lead assigned"
        FOLLOW_UP_ASSIGNED = "FOLLOW_UP_ASSIGNED", "Follow-up assigned"
        FOLLOW_UP_REMINDER = "FOLLOW_UP_REMINDER", "Follow-up reminder"
        TASK_ASSIGNED = "TASK_ASSIGNED", "Task assigned"
        ATTENDANCE = "ATTENDANCE", "Attendance"
        LEAVE_REQUEST = "LEAVE_REQUEST", "Leave request"
        INVENTORY = "INVENTORY", "Inventory"
        RAW_DATA = "RAW_DATA", "Raw data"
        SYSTEM = "SYSTEM", "System"

    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=32, choices=Type.choices)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    href = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["company", "recipient", "is_read", "created_at"]),
            models.Index(fields=["recipient", "created_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type} for {self.recipient_id}"

# Create your models here.

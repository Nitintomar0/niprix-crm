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

# Create your models here.

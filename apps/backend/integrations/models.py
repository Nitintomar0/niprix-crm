from django.db import models
from django.db.models import Q


class IntegrationConfiguration(models.Model):
    class Provider(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        FACEBOOK = "FACEBOOK", "Facebook Lead Ads"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        WEBSITE = "WEBSITE", "Website"

    class Status(models.TextChoices):
        NOT_CONNECTED = "NOT_CONNECTED", "Not connected"
        CONFIGURED = "CONFIGURED", "Configured"
        ERROR = "ERROR", "Error"

    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="integration_configurations")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="integration_configurations")
    provider = models.CharField(max_length=20, choices=Provider.choices)
    # A provider account/page/phone-number identifier maps inbound events to a tenant.
    # It is configuration data, never accepted as a company identifier from a browser.
    external_account_id = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_CONNECTED)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    last_failure_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["provider", "external_account_id"], name="unique_integration_provider_account"),
        ]
        indexes = [models.Index(fields=["company", "provider", "is_enabled"])]


class IntegrationEvent(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        PROCESSING = "PROCESSING", "Processing"
        PROCESSED = "PROCESSED", "Processed"
        FAILED = "FAILED", "Failed"
        IGNORED = "IGNORED", "Ignored"

    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="integration_events")
    configuration = models.ForeignKey(IntegrationConfiguration, on_delete=models.PROTECT, related_name="events")
    lead = models.ForeignKey("leads.Lead", null=True, blank=True, on_delete=models.SET_NULL, related_name="integration_events")
    provider = models.CharField(max_length=20, choices=IntegrationConfiguration.Provider.choices)
    event_type = models.CharField(max_length=100, blank=True)
    external_event_id = models.CharField(max_length=255, blank=True)
    external_lead_id = models.CharField(max_length=255, blank=True)
    idempotency_key = models.CharField(max_length=128)
    raw_payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "provider", "idempotency_key"], name="unique_integration_event_idempotency"),
            models.UniqueConstraint(
                fields=["company", "provider", "external_event_id"],
                condition=~Q(external_event_id=""),
                name="unique_integration_external_event",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "provider", "status", "received_at"]),
            models.Index(fields=["configuration", "received_at"]),
        ]
        ordering = ["-received_at", "-id"]

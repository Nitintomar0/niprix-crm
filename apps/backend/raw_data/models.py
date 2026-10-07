from django.conf import settings
from django.db import models
from django.db.models import Q
from leads.models import Lead


class RawLead(models.Model):
    """A tenant-scoped, pre-assignment lead waiting in the CEO's intake pool."""

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="raw_leads")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="raw_leads_created")
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32)
    normalized_phone = models.CharField(max_length=32)
    alternate_phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    property_type = models.CharField(max_length=100, blank=True)
    preferred_location = models.CharField(max_length=255, blank=True)
    budget_minimum = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_maximum = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bhk = models.CharField(max_length=30, blank=True)
    purpose = models.CharField(max_length=100, blank=True)
    requirement_notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=Lead.Source.choices, default=Lead.Source.MANUAL)
    source_details = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "created_at"]),
            models.Index(fields=["company", "normalized_phone"]),
            models.Index(fields=["company", "preferred_location", "created_at"]),
            models.Index(fields=["company", "source", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "normalized_phone"],
                condition=~Q(normalized_phone=""),
                name="unique_raw_lead_phone_per_company",
            ),
            models.CheckConstraint(
                condition=Q(budget_minimum__isnull=True) | Q(budget_maximum__isnull=True) | Q(budget_minimum__lte=models.F("budget_maximum")),
                name="raw_lead_budget_range_valid",
            ),
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.name or self.phone or f"Raw lead {self.pk}"

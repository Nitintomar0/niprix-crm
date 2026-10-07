from django.conf import settings
from django.db import models


class InventoryItem(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        HOLD = "HOLD", "Hold"
        BOOKED = "BOOKED", "Booked"
        SOLD = "SOLD", "Sold"
        BLOCKED = "BLOCKED", "Blocked"
        RESERVED = "RESERVED", "Reserved"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="inventory_items")
    project = models.CharField(max_length=255)
    unit_number = models.CharField(max_length=100)
    property_type = models.CharField(max_length=100)
    size_sqft = models.DecimalField(max_digits=12, decimal_places=2)
    floor = models.CharField(max_length=100)
    basic_price = models.DecimalField(max_digits=14, decimal_places=2)
    landing = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    booking_date = models.DateField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_inventory_items")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "project", "unit_number"], name="unique_inventory_unit_per_project_company")]
        indexes = [models.Index(fields=["company", "status", "created_at"]), models.Index(fields=["company", "project", "unit_number"])]
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.project} — {self.unit_number}"

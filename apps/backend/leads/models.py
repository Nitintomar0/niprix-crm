from django.conf import settings
from django.db import models
from django.db.models import Q


class Lead(models.Model):
    class Source(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        FACEBOOK = "FACEBOOK", "Facebook"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        META_LEAD_AD = "META_LEAD_AD", "Meta lead ad"
        WEBSITE = "WEBSITE", "Website"
        MANUAL = "MANUAL", "Manual"
        REFERRAL = "REFERRAL", "Referral"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        SITE_VISIT_REQUESTED = "SITE_VISIT_REQUESTED", "Site visit requested"
        SITE_VISIT_DONE = "SITE_VISIT_DONE", "Site visit done"
        FOLLOW_UP_NEEDED = "FOLLOW_UP_NEEDED", "Follow-up needed"
        FOLLOW_UP_DONE = "FOLLOW_UP_DONE", "Follow-up done"
        POSTPONED = "POSTPONED", "Postponed"
        DIFFERENT_REQUIREMENT = "DIFFERENT_REQUIREMENT", "Different requirement"
        NOT_INTERESTED = "NOT_INTERESTED", "Not interested"
        CLOSED = "CLOSED", "Closed"
        INVALID_PHONE = "INVALID_PHONE", "Invalid phone"
        NOT_LOOKING_PROPERTY = "NOT_LOOKING_PROPERTY", "Not looking for property"
        USER_IS_AGENT = "USER_IS_AGENT", "User is agent"

    class Temperature(models.TextChoices):
        HOT = "HOT", "Hot"
        WARM = "WARM", "Warm"
        COLD = "COLD", "Cold"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="leads")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="leads")
    assigned_to = models.ForeignKey("organizations.EmployeeProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_leads")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="created_leads")
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32)
    normalized_phone = models.CharField(max_length=32, blank=True)
    alternate_phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    property_type = models.CharField(max_length=100, blank=True)
    preferred_location = models.CharField(max_length=255, blank=True)
    budget_minimum = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_maximum = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bhk = models.CharField(max_length=30, blank=True)
    purpose = models.CharField(max_length=100, blank=True)
    requirement_notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    source_details = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEW)
    temperature = models.CharField(max_length=10, choices=Temperature.choices, default=Temperature.WARM)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "normalized_phone"]),
            models.Index(fields=["company", "status", "created_at"]),
            models.Index(fields=["company", "assigned_to", "created_at"]),
            models.Index(fields=["company", "source", "created_at"]),
            models.Index(fields=["company", "branch", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "normalized_phone"],
                condition=~Q(normalized_phone=""),
                name="unique_lead_phone_per_company",
            ),
            models.CheckConstraint(
                condition=Q(budget_minimum__isnull=True) | Q(budget_maximum__isnull=True) | Q(budget_minimum__lte=models.F("budget_maximum")),
                name="lead_budget_range_valid",
            ),
        ]

    def __str__(self):
        return self.name or self.phone or f"Lead {self.pk}"


class LeadSource(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="sources")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="lead_sources")
    source = models.CharField(max_length=20, choices=Lead.Source.choices)
    external_lead_id = models.CharField(max_length=255, blank=True)
    external_contact_id = models.CharField(max_length=255, blank=True)
    external_conversation_id = models.CharField(max_length=255, blank=True)
    source_details = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    received_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["company", "lead", "received_at"]), models.Index(fields=["company", "source", "external_lead_id"])]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "source", "external_lead_id"],
                condition=~Q(external_lead_id=""),
                name="unique_external_lead_per_company_source",
            )
        ]
        ordering = ["-received_at", "-id"]


class LeadAssignment(models.Model):
    class Type(models.TextChoices):
        AUTO_ASSIGNED = "AUTO_ASSIGNED", "Auto assigned"
        ASSIGNED = "ASSIGNED", "Assigned"
        REASSIGNED = "REASSIGNED", "Reassigned"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="lead_assignments")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="assignment_history")
    previous_assignee = models.ForeignKey("organizations.EmployeeProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="previous_lead_assignments")
    assigned_to = models.ForeignKey("organizations.EmployeeProfile", on_delete=models.PROTECT, related_name="lead_assignment_history")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="lead_assignments_made")
    assignment_type = models.CharField(max_length=20, choices=Type.choices)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["company", "lead", "created_at"])]
        ordering = ["-created_at", "-id"]


class LeadActivity(models.Model):
    class Type(models.TextChoices):
        CREATED = "CREATED", "Lead created"
        SOURCE_RECEIVED = "SOURCE_RECEIVED", "Source received"
        ASSIGNED = "ASSIGNED", "Assigned"
        REASSIGNED = "REASSIGNED", "Reassigned"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        TEMPERATURE_CHANGED = "TEMPERATURE_CHANGED", "Temperature changed"
        FIELD_CHANGED = "FIELD_CHANGED", "Field changed"
        NOTE_ADDED = "NOTE_ADDED", "Note added"
        FOLLOW_UP_CREATED = "FOLLOW_UP_CREATED", "Follow-up created"
        TASK_CREATED = "TASK_CREATED", "Task created"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="lead_activities")
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="lead_activities")
    activity_type = models.CharField(max_length=24, choices=Type.choices)
    field_name = models.CharField(max_length=64, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["company", "lead", "created_at"])]
        ordering = ["-created_at", "-id"]


class LeadAssignmentCursor(models.Model):
    """A locked per-company cursor used by deterministic round-robin assignment."""

    company = models.OneToOneField("organizations.Company", on_delete=models.CASCADE, related_name="lead_assignment_cursor")
    last_assignee = models.ForeignKey("organizations.EmployeeProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="lead_assignment_cursors")
    updated_at = models.DateTimeField(auto_now=True)

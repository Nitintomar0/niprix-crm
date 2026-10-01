from django.conf import settings
from django.db import models
from django.db.models import Q


class WorkPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    URGENT = "URGENT", "Urgent"


class FollowUp(models.Model):
    class Type(models.TextChoices):
        CALL = "CALL", "Call"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        EMAIL = "EMAIL", "Email"
        SITE_VISIT = "SITE_VISIT", "Site visit"
        MEETING = "MEETING", "Meeting"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        SITE_VISIT_REQUESTED = "SITE_VISIT_REQUESTED", "Site Visit Requested"
        SITE_VISIT_DONE = "SITE_VISIT_DONE", "Site Visit Done"
        FOLLOW_UP_NEEDED = "FOLLOW_UP_NEEDED", "Follow Up Needed"
        FOLLOW_UP_DONE = "FOLLOW_UP_DONE", "Follow Up Done"
        POSTPONED = "POSTPONED", "Postponed"
        DIFFERENT_REQUIREMENT = "DIFFERENT_REQUIREMENT", "Different Requirement"
        NOT_INTERESTED = "NOT_INTERESTED", "Not Interested"
        CLOSED = "CLOSED", "Closed"
        INVALID_PHONE = "INVALID_PHONE", "Invalid Phone"
        NOT_LOOKING_PROPERTY = "NOT_LOOKING_PROPERTY", "Not Looking Property"
        USER_IS_AGENT = "USER_IS_AGENT", "User Is Agent"

        # Legacy statuses — kept for existing records/API compatibility
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        MISSED = "MISSED", "Missed"

    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="follow_ups",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="follow_ups",
    )
    assigned_to = models.ForeignKey(
        "organizations.EmployeeProfile",
        on_delete=models.PROTECT,
        related_name="assigned_follow_ups",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_follow_ups",
    )
    lead = models.ForeignKey(
        "leads.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="follow_ups",
    )
    follow_up_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.CALL,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    scheduled_at = models.DateTimeField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NEW,
    )
    priority = models.CharField(
        max_length=10,
        choices=WorkPriority.choices,
        default=WorkPriority.MEDIUM,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "assigned_to", "scheduled_at"]),
            models.Index(fields=["company", "status", "scheduled_at"]),
            models.Index(fields=["company", "priority"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="COMPLETED", completed_at__isnull=False)
                    | (
                        ~Q(status="COMPLETED")
                        & Q(completed_at__isnull=True)
                    )
                ),
                name="followup_completion_timestamp_consistent",
            )
        ]

    def __str__(self):
        return self.title


class FollowUpActivity(models.Model):
    class Type(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        POSTPONED = "POSTPONED", "Postponed"
        REASSIGNED = "REASSIGNED", "Reassigned"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NOTE_ADDED = "NOTE_ADDED", "Note added"

    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="follow_up_activities",
    )
    follow_up = models.ForeignKey(
        FollowUp,
        on_delete=models.PROTECT,
        related_name="activities",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="follow_up_activities",
    )
    previous_status = models.CharField(
        max_length=32,
        choices=FollowUp.Status.choices,
        blank=True,
    )
    new_status = models.CharField(
        max_length=32,
        choices=FollowUp.Status.choices,
        blank=True,
    )
    previous_scheduled_at = models.DateTimeField(null=True, blank=True)
    new_scheduled_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    activity_type = models.CharField(
        max_length=20,
        choices=Type.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["company", "follow_up", "created_at"]
            )
        ]
        ordering = ["-created_at"]


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "To do"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        BLOCKED = "BLOCKED", "Blocked"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        "organizations.EmployeeProfile",
        on_delete=models.PROTECT,
        related_name="assigned_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
    )
    lead = models.ForeignKey(
        "leads.Lead",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tasks",
    )
    related_follow_up = models.ForeignKey(
        FollowUp,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    due_date = models.DateField()
    due_time = models.TimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=10,
        choices=WorkPriority.choices,
        default=WorkPriority.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "assigned_to", "due_date"]),
            models.Index(fields=["company", "status", "due_date"]),
            models.Index(fields=["company", "priority"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="COMPLETED", completed_at__isnull=False)
                    | (
                        ~Q(status="COMPLETED")
                        & Q(completed_at__isnull=True)
                    )
                ),
                name="task_completion_timestamp_consistent",
            )
        ]

    def __str__(self):
        return self.title


class ReminderPreference(models.Model):
    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="reminder_preferences",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reminder_preferences",
    )
    upcoming_follow_up_reminders_enabled = models.BooleanField(default=True)
    overdue_task_reminders_enabled = models.BooleanField(default=True)
    reminder_lead_minutes = models.PositiveIntegerField(default=30)
    daily_summary_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user"],
                name="unique_reminder_preference_per_user_company",
            )
        ]


class ReminderEvent(models.Model):
    """Prepared in-app reminder event. Delivery is deliberately a separate concern."""

    class Kind(models.TextChoices):
        UPCOMING_FOLLOW_UP = "UPCOMING_FOLLOW_UP", "Upcoming follow-up"
        OVERDUE_TASK = "OVERDUE_TASK", "Overdue task"

    company = models.ForeignKey(
        "organizations.Company",
        on_delete=models.PROTECT,
        related_name="reminder_events",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reminder_events",
    )
    follow_up = models.ForeignKey(
        FollowUp,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reminder_events",
    )
    task = models.ForeignKey(
        Task,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reminder_events",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    source_key = models.CharField(max_length=160)
    scheduled_for = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "user", "source_key"],
                name="unique_prepared_reminder_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(follow_up__isnull=False, task__isnull=True)
                    | Q(follow_up__isnull=True, task__isnull=False)
                ),
                name="reminder_event_has_exactly_one_source",
            ),
        ]
        indexes = [
            models.Index(
                fields=["company", "user", "scheduled_for"]
            )
        ]
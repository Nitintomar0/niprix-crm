from django.conf import settings
from django.db import models
from django.db.models import Q


class LeaveType(models.Model):
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="leave_types")
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    annual_allocation = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    allows_negative_balance = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unique_leave_type_per_company"), models.CheckConstraint(condition=Q(annual_allocation__gte=0), name="leave_type_nonnegative_allocation")]
        indexes = [models.Index(fields=["company", "is_active"])]


class LeaveBalance(models.Model):
    employee = models.ForeignKey("organizations.EmployeeProfile", on_delete=models.PROTECT, related_name="leave_balances")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="balances")
    available_days = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    used_days = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "leave_type"], name="unique_employee_leave_balance"), models.CheckConstraint(condition=Q(available_days__gte=0) & Q(used_days__gte=0), name="leave_balance_nonnegative")]
        indexes = [models.Index(fields=["employee", "leave_type"])]


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="leave_requests")
    employee = models.ForeignKey("organizations.EmployeeProfile", on_delete=models.PROTECT, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="requests")
    start_date = models.DateField()
    end_date = models.DateField()
    number_of_days = models.DecimalField(max_digits=5, decimal_places=1)
    reason = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_leave_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(end_date__gte=models.F("start_date")), name="leave_request_valid_dates"), models.CheckConstraint(condition=Q(number_of_days__gt=0), name="leave_request_positive_days")]
        indexes = [models.Index(fields=["company", "employee", "status", "start_date"]), models.Index(fields=["company", "status", "created_at"])]
        ordering = ["-created_at"]


class Holiday(models.Model):
    company = models.ForeignKey("organizations.Company", on_delete=models.CASCADE, related_name="holidays")
    branch = models.ForeignKey("organizations.Branch", null=True, blank=True, on_delete=models.CASCADE, related_name="holidays")
    name = models.CharField(max_length=160)
    holiday_date = models.DateField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "branch", "holiday_date", "name"], name="unique_holiday_per_scope")]
        indexes = [models.Index(fields=["company", "holiday_date", "is_active"])]


class EmployeeDocument(models.Model):
    class Kind(models.TextChoices):
        JOINING = "JOINING", "Joining document"
        IDENTITY = "IDENTITY", "Identity document"
        EMPLOYMENT = "EMPLOYMENT", "Employment document"
        RELIEVING = "RELIEVING", "Relieving document"
        OTHER = "OTHER", "Other"

    employee = models.ForeignKey("organizations.EmployeeProfile", on_delete=models.PROTECT, related_name="documents")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=160)
    file = models.FileField(upload_to="employee-documents/%Y/%m/")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_employee_documents")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["employee", "kind", "created_at"])]

from datetime import time

from django.conf import settings
from django.db import models
from django.db.models import Q


class AttendancePolicy(models.Model):
    company = models.OneToOneField("organizations.Company", on_delete=models.CASCADE, related_name="attendance_policy")
    workday_start = models.TimeField(default=time(9, 0))
    workday_end = models.TimeField(default=time(18, 0))
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    minimum_work_minutes = models.PositiveSmallIntegerField(default=480)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        LATE = "LATE", "Late"

    employee = models.ForeignKey("organizations.EmployeeProfile", on_delete=models.PROTECT, related_name="attendance_records")
    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="attendance_records")
    branch = models.ForeignKey("organizations.Branch", on_delete=models.PROTECT, related_name="attendance_records")
    attendance_date = models.DateField()
    check_in_at = models.DateTimeField(null=True, blank=True)
    check_out_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PRESENT)
    late_minutes = models.PositiveIntegerField(default=0)
    total_work_minutes = models.PositiveIntegerField(default=0)
    early_checkout = models.BooleanField(default=False)
    corrected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["employee", "attendance_date"], name="unique_employee_attendance_date"),
            models.CheckConstraint(condition=Q(total_work_minutes__gte=0), name="attendance_nonnegative_duration"),
        ]
        indexes = [models.Index(fields=["company", "attendance_date"]), models.Index(fields=["employee", "attendance_date"])]

    @property
    def is_active_session(self):
        return self.check_in_at is not None and self.check_out_at is None


class AttendanceCorrection(models.Model):
    record = models.ForeignKey(AttendanceRecord, on_delete=models.PROTECT, related_name="corrections")
    corrected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_corrections")
    reason = models.TextField()
    original_values = models.JSONField()
    updated_values = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["record", "created_at"])]

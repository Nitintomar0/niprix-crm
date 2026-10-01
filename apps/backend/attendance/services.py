"""Tenant-safe attendance policy resolution and time calculations."""

from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import AttendancePolicy, AttendanceRecord


def attendance_workspace_summary(*, user, attendance_date):
    """Build a date-specific, tenant-safe attendance board including absences.

    Absence and approved leave are derived from active employee profiles rather
    than stored as synthetic attendance records, preserving the existing model.
    """
    from hrms.models import LeaveRequest
    from organizations.services import visible_employee_profiles

    profiles = visible_employee_profiles(user).select_related("user", "branch").filter(is_active=True, user__is_active=True)
    profile_ids = list(profiles.values_list("pk", flat=True))
    records = AttendanceRecord.objects.filter(company=user.company, employee_id__in=profile_ids, attendance_date=attendance_date).select_related("employee__user", "branch")
    record_by_employee = {record.employee_id: record for record in records}
    leave_ids = set(LeaveRequest.objects.filter(
        company=user.company, employee_id__in=profile_ids, status=LeaveRequest.Status.APPROVED,
        start_date__lte=attendance_date, end_date__gte=attendance_date,
    ).values_list("employee_id", flat=True))
    rows, counts = [], {"present": 0, "late": 0, "absent": 0, "on_leave": 0, "working_now": 0}
    for profile in profiles.order_by("employee_code"):
        record = record_by_employee.get(profile.pk)
        if profile.pk in leave_ids:
            state = "ON_LEAVE"; counts["on_leave"] += 1
        elif not record:
            state = "ABSENT"; counts["absent"] += 1
        elif not record.check_out_at:
            state = "WORKING_NOW"; counts["present"] += 1; counts["working_now"] += 1
        elif record.status == AttendanceRecord.Status.LATE:
            state = "LATE"; counts["present"] += 1; counts["late"] += 1
        else:
            state = "PRESENT"; counts["present"] += 1
        rows.append({
            "id": record.pk if record else None, "employee": profile.pk,
            "employee_name": profile.user.get_full_name() or profile.user.username,
            "employee_code": profile.employee_code, "branch": profile.branch_id,
            "check_in_at": record.check_in_at if record else None,
            "check_out_at": record.check_out_at if record else None,
            "total_work_minutes": record.total_work_minutes if record else 0,
            "early_checkout": record.early_checkout if record else False,
            "status": state,
        })
    return {"date": attendance_date, "scope": "company" if user.role == "CEO" or user.is_superuser else "team" if user.role == "MANAGER" else "personal", "counts": counts, "total_active": len(profile_ids), "records": rows}


DEFAULT_POLICY = {
    "workday_start": datetime.strptime("09:00", "%H:%M").time(),
    "workday_end": datetime.strptime("18:00", "%H:%M").time(),
    "grace_minutes": 15,
    "minimum_work_minutes": 480,
}


def get_policy(company):
    """Return a persisted policy, provisioning the documented safe default once."""
    try:
        policy, _ = AttendancePolicy.objects.get_or_create(company=company, defaults=DEFAULT_POLICY)
    except IntegrityError:
        policy = AttendancePolicy.objects.get(company=company)
    return policy


def validate_profile_tenant(profile):
    company = profile.branch.company
    if profile.department.branch_id != profile.branch_id:
        raise ValidationError({"detail": "Employee department does not belong to their branch."})
    if profile.user.company_id and profile.user.company_id != company.id:
        raise ValidationError({"detail": "Employee user and branch belong to different companies."})
    return company


def _ensure_not_future(value, field_name):
    if value and value > timezone.now():
        raise ValidationError({field_name: "Future timestamps are not allowed."})


def calculate_arrival(check_in_at, policy):
    """Return late minutes and status for a timezone-aware arrival timestamp."""
    _ensure_not_future(check_in_at, "check_in_at")
    local_check_in = timezone.localtime(check_in_at)
    scheduled_start = timezone.make_aware(
        datetime.combine(local_check_in.date(), policy.workday_start),
        timezone.get_current_timezone(),
    )
    late_minutes = max(0, int((local_check_in - scheduled_start).total_seconds() // 60) - policy.grace_minutes)
    status = AttendanceRecord.Status.LATE if late_minutes else AttendanceRecord.Status.PRESENT
    return late_minutes, status


def calculate_total_work_minutes(check_in_at, check_out_at):
    if not check_in_at or not check_out_at:
        return 0
    _ensure_not_future(check_in_at, "check_in_at")
    _ensure_not_future(check_out_at, "check_out_at")
    if check_out_at < check_in_at:
        raise ValidationError({"check_out_at": "Check-out cannot be before check-in."})
    return int((check_out_at - check_in_at).total_seconds() // 60)


def calculate_early_checkout(total_work_minutes, policy):
    if total_work_minutes < 0:
        raise ValidationError({"total_work_minutes": "Working duration cannot be negative."})
    return total_work_minutes < policy.minimum_work_minutes


def recalculate_record(record, policy=None):
    """Recalculate all fields derived from timestamps, including after corrections."""
    policy = policy or get_policy(record.company)
    if record.check_in_at:
        record.late_minutes, record.status = calculate_arrival(record.check_in_at, policy)
    else:
        record.late_minutes = 0
        record.status = AttendanceRecord.Status.PRESENT
    record.total_work_minutes = calculate_total_work_minutes(record.check_in_at, record.check_out_at)
    record.early_checkout = bool(record.check_out_at) and calculate_early_checkout(record.total_work_minutes, policy)
    return record


def check_in(profile):
    if not profile.is_active or not profile.user.is_active:
        raise ValidationError({"detail": "Inactive employees cannot check in."})
    company = validate_profile_tenant(profile)
    now = timezone.now()
    policy = get_policy(company)
    late_minutes, status = calculate_arrival(now, policy)
    try:
        with transaction.atomic():
            record, created = AttendanceRecord.objects.select_for_update().get_or_create(
                employee=profile,
                attendance_date=timezone.localdate(now),
                defaults={"company": company, "branch": profile.branch, "check_in_at": now, "status": status, "late_minutes": late_minutes},
            )
    except IntegrityError:
        raise ValidationError({"detail": "An attendance record already exists; retry the request."})
    if not created:
        if record.is_active_session:
            raise ValidationError({"detail": "You are already checked in."})
        raise ValidationError({"detail": "Today's attendance is already completed."})
    return record


def check_out(profile):
    if not profile.is_active or not profile.user.is_active:
        raise ValidationError({"detail": "Inactive employees cannot check out."})
    company = validate_profile_tenant(profile)
    now = timezone.now()
    with transaction.atomic():
        record = AttendanceRecord.objects.select_for_update().filter(employee=profile, company=company, attendance_date=timezone.localdate(now)).first()
        if not record or not record.check_in_at:
            raise ValidationError({"detail": "No active check-in exists for today."})
        if record.branch_id != profile.branch_id:
            raise ValidationError({"detail": "Attendance branch does not match the employee branch."})
        if record.check_out_at:
            raise ValidationError({"detail": "You have already checked out."})
        record.check_out_at = now
        recalculate_record(record, get_policy(company))
        record.save(update_fields=["check_out_at", "total_work_minutes", "early_checkout", "late_minutes", "status", "updated_at"])
    return record

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.audit import log_action
from core.notifications import notify_company_roles
from organizations.services import visible_employee_profiles

from .models import LeaveBalance, LeaveRequest


def employee_in_scope(user, employee):
    if not visible_employee_profiles(user).filter(pk=employee.pk).exists():
        raise PermissionDenied("You do not have access to this employee.")


def leave_days(start_date, end_date):
    return Decimal((end_date - start_date).days + 1)


def create_leave_request(*, actor, employee, leave_type, start_date, end_date, reason):
    employee_in_scope(actor, employee)
    if employee.user_id != actor.id and actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
        raise PermissionDenied("You can only request leave for yourself.")
    if leave_type.company_id != employee.branch.company_id or not leave_type.is_active:
        raise ValidationError({"leave_type": "Choose an active leave type in your company."})
    if end_date < start_date:
        raise ValidationError({"end_date": "End date cannot precede start date."})
    if LeaveRequest.objects.filter(employee=employee, status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED], start_date__lte=end_date, end_date__gte=start_date).exists():
        raise ValidationError({"detail": "This request overlaps an existing leave request."})
    request = LeaveRequest.objects.create(company=employee.branch.company, employee=employee, leave_type=leave_type, start_date=start_date, end_date=end_date, number_of_days=leave_days(start_date, end_date), reason=reason)
    log_action(actor=actor, company=request.company, action="leave.requested", target=request)
    notify_company_roles(
        company=request.company,
        roles=["CEO"],
        notification_type="LEAVE_REQUEST",
        title="New leave request",
        body=f"{employee.user.get_full_name() or employee.user.username} requested {leave_type.name}.",
        href="/leave-requests",
        metadata={"leave_request_id": request.pk, "employee_id": employee.pk},
        exclude_user_id=actor.pk,
    )
    return request


def review_leave_request(*, actor, request, approved, comment=""):
    employee_in_scope(actor, request.employee)
    if actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
        raise PermissionDenied("Only managers can review leave requests.")
    if request.employee.user_id == actor.id:
        raise PermissionDenied("You cannot review your own leave request.")
    with transaction.atomic():
        locked = LeaveRequest.objects.select_for_update().select_related("employee__branch", "leave_type").get(pk=request.pk)
        if locked.status != LeaveRequest.Status.PENDING:
            raise ValidationError({"detail": "Only pending leave requests can be reviewed."})
        if approved:
            balance, _ = LeaveBalance.objects.select_for_update().get_or_create(employee=locked.employee, leave_type=locked.leave_type, defaults={"available_days": locked.leave_type.annual_allocation})
            if not locked.leave_type.allows_negative_balance and balance.available_days < locked.number_of_days:
                raise ValidationError({"detail": "Insufficient leave balance."})
            balance.available_days -= locked.number_of_days
            balance.used_days += locked.number_of_days
            balance.save(update_fields=["available_days", "used_days", "updated_at"])
            locked.status = LeaveRequest.Status.APPROVED
        else:
            locked.status = LeaveRequest.Status.REJECTED
        locked.reviewed_by, locked.reviewed_at, locked.review_comment = actor, timezone.now(), comment
        locked.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_comment", "updated_at"])
    log_action(actor=actor, company=locked.company, action="leave.approved" if approved else "leave.rejected", target=locked)
    return locked


def cancel_leave_request(*, actor, request):
    if request.employee.user_id != actor.id:
        raise PermissionDenied("You can only cancel your own leave request.")
    if request.status != LeaveRequest.Status.PENDING:
        raise ValidationError({"detail": "Only pending leave requests can be cancelled."})
    request.status = LeaveRequest.Status.CANCELLED
    request.save(update_fields=["status", "updated_at"])
    log_action(actor=actor, company=request.company, action="leave.cancelled", target=request)
    return request


def hr_dashboard(*, actor):
    """Return real, tenant-scoped HR operational data in one API response."""
    from attendance.models import AttendanceRecord
    from core.models import AuditLog
    from leads.models import Lead
    from .models import EmployeeDocument, Holiday

    if actor.role == "EMPLOYEE" and not actor.is_superuser:
        raise PermissionDenied("HR dashboard access is limited to managers and CEO users.")
    profiles = visible_employee_profiles(actor).select_related("branch", "department", "user")
    company = actor.company
    today = timezone.localdate()
    active_profiles = profiles.filter(is_active=True, user__is_active=True)
    active_ids = list(active_profiles.values_list("pk", flat=True))
    attendance = AttendanceRecord.objects.filter(company=company, employee_id__in=active_ids, attendance_date=today)
    approved_leave = LeaveRequest.objects.filter(
        company=company, employee_id__in=active_ids, status=LeaveRequest.Status.APPROVED,
        start_date__lte=today, end_date__gte=today,
    )
    on_leave_ids = set(approved_leave.values_list("employee_id", flat=True))
    attendance_ids = set(attendance.values_list("employee_id", flat=True))
    present = attendance.filter(status=AttendanceRecord.Status.PRESENT).count()
    late = attendance.filter(status=AttendanceRecord.Status.LATE).count()
    working_now = attendance.filter(check_in_at__isnull=False, check_out_at__isnull=True).count()
    total_active = len(active_ids)
    scope_branches = profiles.values_list("branch_id", flat=True)
    holidays = Holiday.objects.filter(company=company, is_active=True).filter(
        Q(branch__isnull=True) | Q(branch_id__in=scope_branches)
    )
    documents = EmployeeDocument.objects.filter(employee_id__in=active_ids).select_related("employee__user")
    requests = LeaveRequest.objects.filter(company=company, employee_id__in=active_ids)
    month_start = today.replace(day=1)
    activity_actions = ["employee.created", "employee.deactivated", "leave.requested", "leave.approved", "leave.rejected", "leave.cancelled", "attendance.corrected", "employee_document.uploaded", "employee_document.deleted"]
    activity_filters = Q(company=company, action__in=activity_actions)
    if actor.role != "CEO" and not actor.is_superuser:
        leave_ids = requests.values_list("pk", flat=True)
        document_ids = documents.values_list("pk", flat=True)
        attendance_ids_for_scope = AttendanceRecord.objects.filter(company=company, employee_id__in=active_ids).values_list("pk", flat=True)
        activity_filters &= (
            Q(target_type="organizations.EmployeeProfile", target_id__in=[str(pk) for pk in active_ids])
            | Q(target_type="hrms.LeaveRequest", target_id__in=[str(pk) for pk in leave_ids])
            | Q(target_type="hrms.EmployeeDocument", target_id__in=[str(pk) for pk in document_ids])
            | Q(target_type="attendance.AttendanceRecord", target_id__in=[str(pk) for pk in attendance_ids_for_scope])
        )
    activity = AuditLog.objects.filter(activity_filters).select_related("actor").order_by("-created_at")[:12]
    distributions = {
        "departments": list(active_profiles.values("department__name").order_by("department__name").annotate(count=Count("pk")).values("department__name", "count")),
        "branches": list(active_profiles.values("branch__name").order_by("branch__name").annotate(count=Count("pk")).values("branch__name", "count")),
        "teams": list(active_profiles.exclude(team="").values("team").order_by("team").annotate(count=Count("pk")).values("team", "count")),
    }
    trend_start = today - timedelta(days=6)
    trend_counts = {str(trend_start + timedelta(days=index)): {"present": 0, "late": 0, "on_leave": 0} for index in range(7)}
    for item in AttendanceRecord.objects.filter(company=company, employee_id__in=active_ids, attendance_date__gte=trend_start, attendance_date__lte=today).values("attendance_date", "status").annotate(count=Count("pk")):
        bucket = trend_counts[str(item["attendance_date"])]
        bucket["present"] += item["count"]
        if item["status"] == AttendanceRecord.Status.LATE:
            bucket["late"] += item["count"]
    approved_trend = LeaveRequest.objects.filter(company=company, employee_id__in=active_ids, status=LeaveRequest.Status.APPROVED, start_date__lte=today, end_date__gte=trend_start)
    for request in approved_trend:
        for index in range(7):
            day = trend_start + timedelta(days=index)
            if request.start_date <= day <= request.end_date:
                trend_counts[str(day)]["on_leave"] += 1
    trend = [{"date": day, **values, "absent": max(0, total_active - values["present"] - values["on_leave"])} for day, values in trend_counts.items()]
    attendance_by_employee = {
        item["employee_id"]: item
        for item in attendance.values("employee_id", "check_in_at", "check_out_at", "status")
    }
    workforce_activity = []
    for profile in active_profiles.order_by("user__username")[:12]:
        record = attendance_by_employee.get(profile.pk)
        workforce_activity.append({
            "employee_id": profile.pk,
            "employee_name": profile.user.get_full_name() or profile.user.username,
            "status": "CHECKED_IN" if record and record["check_in_at"] and not record["check_out_at"] else "CHECKED_OUT" if record and record["check_out_at"] else "NOT_CHECKED_IN",
            "check_in_at": record["check_in_at"] if record else None,
            "attendance_status": record["status"] if record else None,
        })
    contacted_statuses = [
        Lead.Status.CONTACTED,
        Lead.Status.SITE_VISIT_REQUESTED,
        Lead.Status.SITE_VISIT_DONE,
        Lead.Status.FOLLOW_UP_NEEDED,
        Lead.Status.FOLLOW_UP_DONE,
        Lead.Status.POSTPONED,
        Lead.Status.DIFFERENT_REQUIREMENT,
        Lead.Status.CLOSED,
    ]
    leaderboard = []
    for profile in active_profiles.annotate(
        leads_assigned=Count("assigned_leads", filter=Q(assigned_leads__company=company), distinct=True),
        leads_contacted=Count("assigned_leads", filter=Q(assigned_leads__company=company, assigned_leads__status__in=contacted_statuses), distinct=True),
        site_visits=Count("assigned_leads", filter=Q(assigned_leads__company=company, assigned_leads__status=Lead.Status.SITE_VISIT_DONE), distinct=True),
        closings=Count("assigned_leads", filter=Q(assigned_leads__company=company, assigned_leads__status=Lead.Status.CLOSED), distinct=True),
        follow_ups_completed=Count("assigned_follow_ups", filter=Q(assigned_follow_ups__company=company, assigned_follow_ups__status="COMPLETED"), distinct=True),
    ).order_by("-closings", "-site_visits", "-leads_assigned", "user__username")[:12]:
        conversion = round(profile.closings / profile.leads_assigned * 100, 1) if profile.leads_assigned else 0
        leaderboard.append({
            "employee_id": profile.pk,
            "employee_name": profile.user.get_full_name() or profile.user.username,
            "leads_assigned": profile.leads_assigned,
            "leads_contacted": profile.leads_contacted,
            "site_visits": profile.site_visits,
            "closings": profile.closings,
            "follow_ups_completed": profile.follow_ups_completed,
            "conversion_rate": conversion,
        })
    return {
        "scope": "company" if actor.role == "CEO" or actor.is_superuser else "team",
        "kpis": {
            "total_employees": profiles.count(), "active_employees": total_active,
            "inactive_employees": profiles.exclude(is_active=True, user__is_active=True).count(),
            "new_employees": profiles.filter(created_at__date__gte=month_start).count(),
            "present_today": present, "absent_today": max(0, total_active - len(attendance_ids | on_leave_ids)),
            "on_leave_today": len(on_leave_ids), "late_today": late, "working_now": working_now, "pending_leave_requests": requests.filter(status=LeaveRequest.Status.PENDING).count(),
        },
        "attendance": {"present": present, "late": late, "on_leave": len(on_leave_ids), "absent": max(0, total_active - len(attendance_ids | on_leave_ids)), "working_now": working_now, "percentage": round((len(attendance_ids) / total_active * 100) if total_active else 0, 1), "trend": trend},
        "leave": {"pending": requests.filter(status=LeaveRequest.Status.PENDING).count(), "approved": requests.filter(status=LeaveRequest.Status.APPROVED).count(), "rejected": requests.filter(status=LeaveRequest.Status.REJECTED).count(), "on_leave_today": len(on_leave_ids), "upcoming": list(requests.filter(status=LeaveRequest.Status.APPROVED, start_date__gt=today).select_related("employee__user", "leave_type").order_by("start_date")[:5].values("id", "employee__user__username", "leave_type__name", "start_date", "end_date"))},
        "distribution": distributions,
        "holidays": list(holidays.filter(holiday_date__gte=today).order_by("holiday_date")[:5].values("id", "name", "holiday_date", "description")),
        "documents": {"total": documents.count(), "recent": list(documents.order_by("-created_at")[:5].values("id", "title", "kind", "created_at", "employee__user__username", "employee__employee_code"))},
        "activity": [{"id": item.pk, "action": item.action, "actor": item.actor.username if item.actor else "System", "created_at": item.created_at, "reason": item.reason} for item in activity],
        "workforce_activity": workforce_activity,
        "performance": {"leaderboard": leaderboard},
    }

"""Small, query-efficient aggregations for the employee 360 dashboard."""

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone


def employee_performance(profile):
    """Return only metrics supported by first-party CRM records.

    Revenue and targets are intentionally absent: this project has no source
    model for them, and the dashboard must never invent them.
    """
    from attendance.models import AttendanceRecord
    from leads.models import Lead
    from workspace.models import FollowUp, Task

    today = timezone.localdate()
    start = today.replace(day=1)
    company = profile.branch.company
    leads = Lead.objects.filter(company=company, assigned_to=profile)
    tasks = Task.objects.filter(company=company, assigned_to=profile)
    followups = FollowUp.objects.filter(company=company, assigned_to=profile)
    month_leads = leads.filter(created_at__date__gte=start)
    month_tasks = tasks.filter(created_at__date__gte=start)
    month_followups = followups.filter(created_at__date__gte=start)
    attendance = AttendanceRecord.objects.filter(company=company, employee=profile, attendance_date__gte=start)

    total_leads = month_leads.count()
    closed = month_leads.filter(status="CLOSED").count()
    site_visit_total = month_leads.filter(status__in=["SITE_VISIT_REQUESTED", "SITE_VISIT_DONE"]).count()
    completed_visits = month_leads.filter(status="SITE_VISIT_DONE").count()

    months = [start]
    while len(months) < 6:
        months.append((months[-1] - timedelta(days=1)).replace(day=1))
    months.reverse()
    labels = {month.strftime("%Y-%m"): month.strftime("%b") for month in months}

    def series(queryset):
        rows = queryset.filter(created_at__date__gte=months[0]).annotate(month=TruncMonth("created_at")).values("month").annotate(total=Count("id"))
        values = {row["month"].strftime("%Y-%m"): row["total"] for row in rows}
        return [{"month": key, "label": label, "value": values.get(key, 0)} for key, label in labels.items()]

    temperature_rows = leads.values("temperature").annotate(value=Count("id")).order_by("temperature")
    task_total = month_tasks.count()
    followup_total = month_followups.count()
    return {
        "period": {"start": start, "end": today},
        "leads": {"assigned": total_leads, "new": month_leads.filter(status="NEW").count(), "contacted": month_leads.filter(status="CONTACTED").count(), "site_visits": site_visit_total, "closed": closed, "conversion_rate": round(closed / total_leads * 100, 1) if total_leads else 0},
        "tasks": {"assigned": task_total, "completed": month_tasks.filter(status="COMPLETED").count(), "overdue": month_tasks.exclude(status__in=["COMPLETED", "CANCELLED"]).filter(due_date__lt=today).count(), "completion_rate": round(month_tasks.filter(status="COMPLETED").count() / task_total * 100, 1) if task_total else 0},
        "follow_ups": {"assigned": followup_total, "completed": month_followups.filter(status="COMPLETED").count(), "upcoming": month_followups.filter(status__in=["PENDING", "IN_PROGRESS", "POSTPONED"], scheduled_at__gte=timezone.now()).count(), "completion_rate": round(month_followups.filter(status="COMPLETED").count() / followup_total * 100, 1) if followup_total else 0},
        "attendance": {"present": attendance.filter(status="PRESENT").count(), "late": attendance.filter(status="LATE").count()},
        "site_visits": {"requested": month_leads.filter(status="SITE_VISIT_REQUESTED").count(), "completed": completed_visits, "conversion_rate": round(closed / site_visit_total * 100, 1) if site_visit_total else 0},
        "communication": {"calls": month_followups.filter(follow_up_type="CALL").count(), "whatsapp": month_followups.filter(follow_up_type="WHATSAPP").count(), "emails": month_followups.filter(follow_up_type="EMAIL").count(), "completed": month_followups.filter(status="COMPLETED", follow_up_type__in=["CALL", "WHATSAPP", "EMAIL"]).count()},
        "lead_distribution": [{"label": row["temperature"].title(), "value": row["value"]} for row in temperature_rows],
        "monthly": {"leads": series(leads), "follow_ups": series(followups), "closings": series(leads.filter(status="CLOSED"))},
    }

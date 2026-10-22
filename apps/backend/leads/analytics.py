"""Permission-scoped, aggregate-only data for the Overview dashboard."""

from datetime import datetime, time, timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Lead
from .services import lead_queryset


def overview_analytics(user, *, days=14):
    """Return real pipeline data without serializing individual customer records.

    ``lead_queryset`` is the authorization boundary used by every Lead API, so
    a manager or employee cannot infer data outside their permitted scope from
    dashboard aggregates.
    """
    today = timezone.localdate()
    first_day = today - timedelta(days=days - 1)
    leads = lead_queryset(user).filter(recovery_category__isnull=True)

    daily_rows = (
        leads.filter(created_at__gte=timezone.make_aware(datetime.combine(first_day, time.min)))
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(value=Count("id"))
        .order_by("day")
    )
    by_day = {row["day"]: row["value"] for row in daily_rows}
    growth = [
        {
            "date": (first_day + timedelta(days=offset)).isoformat(),
            "label": (first_day + timedelta(days=offset)).strftime("%-d %b"),
            "value": by_day.get(first_day + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]

    status_counts = {
        row["status"]: row["value"]
        for row in leads.values("status").annotate(value=Count("id"))
    }
    source_counts = {
        row["source"]: row["value"]
        for row in leads.values("source").annotate(value=Count("id"))
    }

    pipeline_keys = (
        Lead.Status.NEW,
        Lead.Status.CONTACTED,
        Lead.Status.FOLLOW_UP_NEEDED,
        Lead.Status.SITE_VISIT_REQUESTED,
        Lead.Status.SITE_VISIT_DONE,
        Lead.Status.CLOSED,
    )
    pipeline = [
        {"key": key, "label": Lead.Status(key).label, "value": status_counts.get(key, 0)}
        for key in pipeline_keys
    ]
    sources = [
        {"key": key, "label": label, "value": source_counts.get(key, 0)}
        for key, label in Lead.Source.choices
    ]
    engaged_statuses = (
        Lead.Status.CONTACTED,
        Lead.Status.FOLLOW_UP_NEEDED,
        Lead.Status.FOLLOW_UP_DONE,
        Lead.Status.POSTPONED,
        Lead.Status.DIFFERENT_REQUIREMENT,
        Lead.Status.SITE_VISIT_REQUESTED,
        Lead.Status.SITE_VISIT_DONE,
        Lead.Status.NOT_INTERESTED,
        Lead.Status.CLOSED,
    )
    total = sum(status_counts.values())
    funnel = [
        {"key": "received", "label": "Visible leads", "value": total},
        {"key": "engaged", "label": "Currently engaged", "value": sum(status_counts.get(status, 0) for status in engaged_statuses)},
        {
            "key": "visited",
            "label": "Site visit status",
            "value": status_counts.get(Lead.Status.SITE_VISIT_REQUESTED, 0) + status_counts.get(Lead.Status.SITE_VISIT_DONE, 0),
        },
        {"key": "closed", "label": "Closed", "value": status_counts.get(Lead.Status.CLOSED, 0)},
    ]
    scope = "company" if user.role == "CEO" or user.is_superuser else "team" if user.role == "MANAGER" else "personal"
    return {
        "scope": scope,
        "period": {"start": first_day.isoformat(), "end": today.isoformat(), "days": days},
        "growth": growth,
        "pipeline": pipeline,
        "sources": sources,
        "funnel": funnel,
    }

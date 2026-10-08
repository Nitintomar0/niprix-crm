"""Tenant-safe workspace business operations and reminder preparation."""

from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.audit import log_action
from core.notifications import create_notification
from organizations.models import EmployeeProfile

from .models import FollowUp, FollowUpActivity, ReminderEvent, ReminderPreference, Task


FOLLOW_UP_WORKFLOW_STATUSES = frozenset({
    FollowUp.Status.PENDING,
    FollowUp.Status.IN_PROGRESS,
    FollowUp.Status.POSTPONED,
    FollowUp.Status.COMPLETED,
    FollowUp.Status.CANCELLED,
    FollowUp.Status.MISSED,
})
LEGACY_ACTIVE_FOLLOW_UP_STATUSES = frozenset({
    FollowUp.Status.NEW,
    FollowUp.Status.CONTACTED,
    FollowUp.Status.SITE_VISIT_REQUESTED,
    FollowUp.Status.SITE_VISIT_DONE,
    FollowUp.Status.FOLLOW_UP_NEEDED,
    FollowUp.Status.DIFFERENT_REQUIREMENT,
})
ACTIVE_FOLLOW_UP_STATUSES = frozenset({
    FollowUp.Status.PENDING,
    FollowUp.Status.IN_PROGRESS,
    FollowUp.Status.POSTPONED,
    FollowUp.Status.MISSED,
}) | LEGACY_ACTIVE_FOLLOW_UP_STATUSES

FOLLOW_UP_TRANSITIONS = {
    FollowUp.Status.PENDING: {FollowUp.Status.IN_PROGRESS, FollowUp.Status.POSTPONED, FollowUp.Status.MISSED, FollowUp.Status.COMPLETED, FollowUp.Status.CANCELLED},
    FollowUp.Status.IN_PROGRESS: {FollowUp.Status.PENDING, FollowUp.Status.POSTPONED, FollowUp.Status.MISSED, FollowUp.Status.COMPLETED, FollowUp.Status.CANCELLED},
    FollowUp.Status.POSTPONED: {FollowUp.Status.PENDING, FollowUp.Status.IN_PROGRESS, FollowUp.Status.MISSED, FollowUp.Status.COMPLETED, FollowUp.Status.CANCELLED},
    FollowUp.Status.MISSED: {FollowUp.Status.PENDING, FollowUp.Status.IN_PROGRESS, FollowUp.Status.POSTPONED, FollowUp.Status.COMPLETED, FollowUp.Status.CANCELLED},
    FollowUp.Status.COMPLETED: set(),
    FollowUp.Status.CANCELLED: set(),
}
# Legacy rows are never created again, but may be moved into the canonical
# workflow without discarding their historic value or activity trail.
for _legacy_status in LEGACY_ACTIVE_FOLLOW_UP_STATUSES:
    FOLLOW_UP_TRANSITIONS[_legacy_status] = set(ACTIVE_FOLLOW_UP_STATUSES) | {FollowUp.Status.COMPLETED, FollowUp.Status.CANCELLED}

TASK_TRANSITIONS = {
    Task.Status.TODO: {Task.Status.IN_PROGRESS, Task.Status.BLOCKED, Task.Status.COMPLETED, Task.Status.CANCELLED},
    Task.Status.IN_PROGRESS: {Task.Status.TODO, Task.Status.BLOCKED, Task.Status.COMPLETED, Task.Status.CANCELLED},
    Task.Status.BLOCKED: {Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.COMPLETED, Task.Status.CANCELLED},
    Task.Status.COMPLETED: set(),
    Task.Status.CANCELLED: set(),
}
ACTIVE_TASK_STATUSES = [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.BLOCKED]


def company_for(user):
    if not user.is_authenticated or not user.is_active or not user.company_id:
        raise PermissionDenied("An active company account is required.")
    return user.company


def profile_for(user):
    try:
        profile = user.employee_profile
    except EmployeeProfile.DoesNotExist:
        raise PermissionDenied("An employee profile is required for workspace access.")
    if not profile.is_active or not user.is_active or profile.branch.company_id != user.company_id:
        raise PermissionDenied("Your employee profile is not active in this company.")
    return profile


def is_company_admin(user):
    return user.is_superuser or user.role == "CEO"


def visible_profiles(user):
    company = company_for(user)
    base = EmployeeProfile.objects.filter(branch__company=company, user__company=company, is_active=True, user__is_active=True)
    if is_company_admin(user):
        return base
    profile = profile_for(user)
    if user.role == "MANAGER":
        return base.filter(Q(pk=profile.pk) | Q(reporting_manager=profile))
    return base.filter(pk=profile.pk)


def validate_assignee(user, assignee):
    company = company_for(user)
    if not assignee or not assignee.is_active or not assignee.user.is_active:
        raise ValidationError({"assigned_to": "Assigned employee must be active."})
    if assignee.branch.company_id != company.id or assignee.user.company_id != company.id:
        raise ValidationError({"assigned_to": "Assigned employee must belong to your company."})
    if not visible_profiles(user).filter(pk=assignee.pk).exists():
        raise PermissionDenied("You cannot assign work outside your permitted team.")
    return assignee


def follow_up_queryset(user):
    company = company_for(user)
    return FollowUp.objects.select_related("assigned_to__user", "branch", "created_by", "lead").filter(company=company, assigned_to__in=visible_profiles(user))


def task_queryset(user):
    company = company_for(user)
    return Task.objects.select_related("assigned_to__user", "branch", "created_by", "related_follow_up").filter(company=company, assigned_to__in=visible_profiles(user))


def _activity(follow_up, actor, activity_type, *, previous_status="", previous_scheduled_at=None, note=""):
    return FollowUpActivity.objects.create(
        company=follow_up.company,
        follow_up=follow_up,
        performed_by=actor,
        previous_status=previous_status,
        new_status=follow_up.status,
        previous_scheduled_at=previous_scheduled_at,
        new_scheduled_at=follow_up.scheduled_at,
        note=note,
        activity_type=activity_type,
    )


def create_follow_up(*, actor, data):
    assignee = validate_assignee(actor, data.pop("assigned_to"))
    lead = data.get("lead")
    with transaction.atomic():
        company = company_for(actor)
        if lead:
            from leads.services import lead_queryset, log_lead_activity
            if lead.company_id != company.id or not lead_queryset(actor).filter(pk=lead.pk).exists():
                raise PermissionDenied("Lead is not available.")
        follow_up = FollowUp.objects.create(company=company, branch=assignee.branch, assigned_to=assignee, created_by=actor, **data)
        _activity(follow_up, actor, FollowUpActivity.Type.CREATED, note=follow_up.description)
        log_action(actor=actor, company=follow_up.company, action="follow_up.created", target=follow_up)
        if assignee.user_id != actor.pk:
            create_notification(
                company=follow_up.company,
                recipient=assignee.user,
                notification_type="FOLLOW_UP_ASSIGNED",
                title="New follow-up assigned",
                body=follow_up.title,
                href=f"/follow-ups?follow_up={follow_up.pk}",
                metadata={"follow_up_id": follow_up.pk, "lead_id": follow_up.lead_id},
            )
        if lead:
            log_lead_activity(lead=lead, actor=actor, activity_type="FOLLOW_UP_CREATED", note=follow_up.title, metadata={"follow_up_id": follow_up.pk})
    return follow_up


def transition_follow_up(*, actor, follow_up, status, note="", scheduled_at=None):
    if status == follow_up.status and scheduled_at is None:
        return follow_up
    if status != follow_up.status and status not in FOLLOW_UP_TRANSITIONS.get(follow_up.status, set()):
        raise ValidationError({"status": f"Cannot change a {follow_up.get_status_display().lower()} follow-up to {status.lower()}."})
    with transaction.atomic():
        follow_up = FollowUp.objects.select_for_update().get(pk=follow_up.pk, company=company_for(actor))
        prior_status, prior_schedule = follow_up.status, follow_up.scheduled_at
        if status != prior_status and status not in FOLLOW_UP_TRANSITIONS.get(prior_status, set()):
            raise ValidationError({"status": "This status transition is no longer available."})
        if scheduled_at is not None:
            follow_up.scheduled_at = scheduled_at
        follow_up.status = status
        follow_up.completed_at = timezone.now() if status == FollowUp.Status.COMPLETED else None
        follow_up.save()
        kind = (
            FollowUpActivity.Type.COMPLETED
            if status == FollowUp.Status.COMPLETED
            else FollowUpActivity.Type.CANCELLED
            if status in {FollowUp.Status.CLOSED, FollowUp.Status.CANCELLED}
            else FollowUpActivity.Type.POSTPONED
            if status == FollowUp.Status.POSTPONED or scheduled_at is not None
            else FollowUpActivity.Type.STATUS_CHANGED
        )
        _activity(follow_up, actor, kind, previous_status=prior_status, previous_scheduled_at=prior_schedule, note=note)
        log_action(actor=actor, company=follow_up.company, action=f"follow_up.{status.lower()}", target=follow_up, reason=note)
        _record_follow_up_lead_history(
            follow_up=follow_up,
            actor=actor,
            activity_type=(
                "FOLLOW_UP_COMPLETED" if status == FollowUp.Status.COMPLETED
                else "FOLLOW_UP_RESCHEDULED" if scheduled_at is not None
                else None
            ),
            note=note,
            metadata={"follow_up_id": follow_up.pk, "status": status},
        )
    return follow_up


def update_follow_up(*, actor, follow_up, data):
    status = data.pop("status", None)
    note = data.pop("activity_note", "")
    assignee = data.pop("assigned_to", None)
    scheduled_at = data.pop("scheduled_at", None) if status is not None else None
    if status is not None:
        follow_up = transition_follow_up(actor=actor, follow_up=follow_up, status=status, note=note, scheduled_at=scheduled_at)
    with transaction.atomic():
        follow_up = FollowUp.objects.select_for_update().get(pk=follow_up.pk, company=company_for(actor))
        old_assignee, old_schedule = follow_up.assigned_to_id, follow_up.scheduled_at
        if assignee is not None:
            assignee = validate_assignee(actor, assignee)
            follow_up.assigned_to, follow_up.branch = assignee, assignee.branch
        lead = data.get("lead")
        if lead:
            from leads.services import lead_queryset
            if lead.company_id != follow_up.company_id or not lead_queryset(actor).filter(pk=lead.pk).exists():
                raise PermissionDenied("Lead is not available.")
        for field, value in data.items():
            setattr(follow_up, field, value)
        follow_up.save()
        if assignee is not None and old_assignee != assignee.pk:
            _activity(follow_up, actor, FollowUpActivity.Type.REASSIGNED, previous_scheduled_at=old_schedule, note=note)
            _record_follow_up_lead_history(
                follow_up=follow_up,
                actor=actor,
                activity_type="FOLLOW_UP_REASSIGNED",
                note=note,
                metadata={"follow_up_id": follow_up.pk, "assigned_to": assignee.pk},
            )
            if assignee.user_id != actor.pk:
                create_notification(
                    company=follow_up.company,
                    recipient=assignee.user,
                    notification_type="FOLLOW_UP_ASSIGNED",
                    title="Follow-up reassigned to you",
                    body=follow_up.title,
                    href=f"/follow-ups?follow_up={follow_up.pk}",
                    metadata={"follow_up_id": follow_up.pk, "lead_id": follow_up.lead_id},
                )
        elif data or note:
            activity_type = FollowUpActivity.Type.POSTPONED if "scheduled_at" in data and old_schedule != follow_up.scheduled_at else FollowUpActivity.Type.NOTE_ADDED if note and not data else FollowUpActivity.Type.UPDATED
            _activity(follow_up, actor, activity_type, previous_scheduled_at=old_schedule, note=note)
            if "scheduled_at" in data and old_schedule != follow_up.scheduled_at:
                _record_follow_up_lead_history(
                    follow_up=follow_up,
                    actor=actor,
                    activity_type="FOLLOW_UP_RESCHEDULED",
                    note=note,
                    metadata={"follow_up_id": follow_up.pk},
                )
        log_action(actor=actor, company=follow_up.company, action="follow_up.updated", target=follow_up)
    return follow_up


def _record_follow_up_lead_history(*, follow_up, actor, activity_type, note="", metadata=None):
    """Mirror Follow-up lifecycle events into the existing Lead timeline."""
    if not follow_up.lead_id or not activity_type:
        return
    from leads.services import log_lead_activity

    log_lead_activity(
        lead=follow_up.lead,
        actor=actor,
        activity_type=activity_type,
        note=note or follow_up.title,
        metadata=metadata or {"follow_up_id": follow_up.pk},
    )


def sync_active_follow_up_owners(*, actor, lead, assignee, note=""):
    """Keep active Lead work aligned when its owner changes.

    Completed and cancelled Follow-ups intentionally retain their historical
    assignee. The caller holds the Lead lock, so this also serializes a Lead
    reassignment with a move-to-follow-up operation.
    """
    follow_ups = FollowUp.objects.select_for_update().filter(
        company=lead.company,
        lead=lead,
        status__in=ACTIVE_FOLLOW_UP_STATUSES,
    ).exclude(assigned_to=assignee)
    for follow_up in follow_ups:
        previous_schedule = follow_up.scheduled_at
        follow_up.assigned_to = assignee
        follow_up.branch = assignee.branch
        follow_up.save(update_fields=["assigned_to", "branch", "updated_at"])
        _activity(
            follow_up,
            actor,
            FollowUpActivity.Type.REASSIGNED,
            previous_scheduled_at=previous_schedule,
            note=note or "Synced with lead owner",
        )
        _record_follow_up_lead_history(
            follow_up=follow_up,
            actor=actor,
            activity_type="FOLLOW_UP_REASSIGNED",
            note=note or "Synced with lead owner",
            metadata={"follow_up_id": follow_up.pk, "assigned_to": assignee.pk},
        )
        if assignee.user_id != actor.pk:
            create_notification(
                company=follow_up.company,
                recipient=assignee.user,
                notification_type="FOLLOW_UP_ASSIGNED",
                title="Follow-up reassigned to you",
                body=follow_up.title,
                href=f"/follow-ups?follow_up={follow_up.pk}",
                metadata={"follow_up_id": follow_up.pk, "lead_id": follow_up.lead_id},
            )


def reassign_follow_up(*, actor, follow_up, assignee, note=""):
    if actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
        raise PermissionDenied("Only managers can reassign follow-ups.")
    return update_follow_up(actor=actor, follow_up=follow_up, data={"assigned_to": assignee, "activity_note": note})


def create_task(*, actor, data):
    assignee = validate_assignee(actor, data.pop("assigned_to"))
    related = data.get("related_follow_up")
    lead = data.get("lead")
    company = company_for(actor)
    if related and related.company_id != company.id:
        raise ValidationError({"related_follow_up": "Related follow-up must belong to your company."})
    with transaction.atomic():
        if lead:
            from leads.services import lead_queryset, log_lead_activity
            if lead.company_id != company.id or not lead_queryset(actor).filter(pk=lead.pk).exists():
                raise PermissionDenied("Lead is not available.")
        task = Task.objects.create(company=company, branch=assignee.branch, assigned_to=assignee, created_by=actor, **data)
        log_action(actor=actor, company=company, action="task.created", target=task)
        if assignee.user_id != actor.pk:
            create_notification(
                company=company,
                recipient=assignee.user,
                notification_type="TASK_ASSIGNED",
                title="New task assigned",
                body=task.title,
                href="/tasks",
                metadata={"task_id": task.pk, "lead_id": task.lead_id},
            )
        if lead:
            log_lead_activity(lead=lead, actor=actor, activity_type="TASK_CREATED", note=task.title, metadata={"task_id": task.pk})
    return task


def transition_task(*, actor, task, status):
    if status == task.status:
        return task
    if status != task.status and status not in TASK_TRANSITIONS[task.status]:
        raise ValidationError({"status": f"Cannot change a {task.get_status_display().lower()} task to {status.lower()}."})
    with transaction.atomic():
        task = Task.objects.select_for_update().get(pk=task.pk, company=company_for(actor))
        if status != task.status and status not in TASK_TRANSITIONS[task.status]:
            raise ValidationError({"status": "This status transition is no longer available."})
        task.status = status
        task.completed_at = timezone.now() if status == Task.Status.COMPLETED else None
        task.save()
        log_action(actor=actor, company=task.company, action=f"task.{status.lower()}", target=task)
    return task


def update_task(*, actor, task, data):
    status = data.pop("status", None)
    assignee = data.pop("assigned_to", None)
    if status is not None:
        task = transition_task(actor=actor, task=task, status=status)
    with transaction.atomic():
        task = Task.objects.select_for_update().get(pk=task.pk, company=company_for(actor))
        previous_assignee_id = task.assigned_to_id
        if assignee is not None:
            assignee = validate_assignee(actor, assignee)
            task.assigned_to, task.branch = assignee, assignee.branch
        related = data.get("related_follow_up")
        if related and related.company_id != task.company_id:
            raise ValidationError({"related_follow_up": "Related follow-up must belong to your company."})
        lead = data.get("lead")
        if lead:
            from leads.services import lead_queryset
            if lead.company_id != task.company_id or not lead_queryset(actor).filter(pk=lead.pk).exists():
                raise PermissionDenied("Lead is not available.")
        for field, value in data.items():
            setattr(task, field, value)
        task.save()
        log_action(actor=actor, company=task.company, action="task.updated", target=task)
        if assignee is not None and previous_assignee_id != assignee.pk and assignee.user_id != actor.pk:
            create_notification(
                company=task.company,
                recipient=assignee.user,
                notification_type="TASK_ASSIGNED",
                title="Task reassigned to you",
                body=task.title,
                href="/tasks",
                metadata={"task_id": task.pk, "lead_id": task.lead_id},
            )
    return task


def reassign_task(*, actor, task, assignee):
    if actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
        raise PermissionDenied("Only managers can reassign tasks.")
    return update_task(actor=actor, task=task, data={"assigned_to": assignee})


def follow_up_overdue_q(now=None):
    return Q(scheduled_at__lt=now or timezone.now(), status__in=ACTIVE_FOLLOW_UP_STATUSES)


def task_overdue_q(now=None):
    now = now or timezone.now()
    return Q(status__in=ACTIVE_TASK_STATUSES) & (Q(due_date__lt=timezone.localdate(now)) | Q(due_date=timezone.localdate(now), due_time__lt=timezone.localtime(now).time()))


def get_reminder_preference(user):
    company = company_for(user)
    preference, _ = ReminderPreference.objects.get_or_create(company=company, user=user)
    return preference


def _create_follow_up_reminder(*, follow_up, user, kind, source_key, scheduled_for, title, body):
    event, was_created = ReminderEvent.objects.get_or_create(
        company=follow_up.company,
        user=user,
        source_key=source_key,
        defaults={"follow_up": follow_up, "kind": kind, "scheduled_for": scheduled_for},
    )
    if was_created:
        create_notification(
            company=follow_up.company,
            recipient=user,
            notification_type="FOLLOW_UP_REMINDER",
            title=title,
            body=body,
            href=f"/follow-ups?follow_up={follow_up.pk}",
            metadata={"follow_up_id": follow_up.pk, "reminder_event_id": event.pk, "kind": kind},
        )
    return event, was_created


def prepare_reminder_events(*, now=None, user=None):
    """Idempotently persist and expose in-app reminders.

    A scheduled worker may call this without ``user``. The notification API
    also prepares only the requesting user's events, which keeps reminders
    useful in deployments that have not configured a worker yet.
    """
    now = now or timezone.now()
    created = []
    followups = FollowUp.objects.select_related("assigned_to__user", "company").filter(status__in=ACTIVE_FOLLOW_UP_STATUSES)
    if user is not None:
        followups = followups.filter(assigned_to__user=user)
    for follow_up in followups:
        preference = get_reminder_preference(follow_up.assigned_to.user)
        scheduled_key = follow_up.scheduled_at.isoformat()
        if preference.upcoming_follow_up_reminders_enabled and now <= follow_up.scheduled_at <= now + timedelta(minutes=preference.reminder_lead_minutes):
            event, was_created = _create_follow_up_reminder(
                follow_up=follow_up, user=follow_up.assigned_to.user,
                kind=ReminderEvent.Kind.UPCOMING_FOLLOW_UP,
                source_key=f"follow-up:{follow_up.pk}:upcoming:{scheduled_key}",
                scheduled_for=follow_up.scheduled_at,
                title="Follow-up coming up",
                body=f"{follow_up.title} is due at {timezone.localtime(follow_up.scheduled_at):%I:%M %p}.",
            )
            if was_created: created.append(event)
        if follow_up.scheduled_at <= now:
            event, was_created = _create_follow_up_reminder(
                follow_up=follow_up, user=follow_up.assigned_to.user,
                kind=ReminderEvent.Kind.DUE_FOLLOW_UP,
                source_key=f"follow-up:{follow_up.pk}:due:{scheduled_key}",
                scheduled_for=follow_up.scheduled_at,
                title="Follow-up is due now",
                body=follow_up.title,
            )
            if was_created: created.append(event)
        if preference.overdue_follow_up_reminders_enabled and follow_up.scheduled_at <= now - timedelta(minutes=15):
            event, was_created = _create_follow_up_reminder(
                follow_up=follow_up, user=follow_up.assigned_to.user,
                kind=ReminderEvent.Kind.OVERDUE_FOLLOW_UP,
                source_key=f"follow-up:{follow_up.pk}:overdue:{scheduled_key}",
                scheduled_for=follow_up.scheduled_at,
                title="Follow-up is overdue",
                body=follow_up.title,
            )
            if was_created: created.append(event)
    tasks = Task.objects.select_related("assigned_to__user", "company").filter(task_overdue_q(now))
    if user is not None:
        tasks = tasks.filter(assigned_to__user=user)
    for task in tasks:
        preference = get_reminder_preference(task.assigned_to.user)
        if not preference.overdue_task_reminders_enabled:
            continue
        key = f"task:{task.pk}:overdue:{timezone.localdate(now).isoformat()}"
        event, was_created = ReminderEvent.objects.get_or_create(company=task.company, user=task.assigned_to.user, source_key=key, defaults={"task": task, "kind": ReminderEvent.Kind.OVERDUE_TASK, "scheduled_for": now})
        if was_created:
            created.append(event)
    return created

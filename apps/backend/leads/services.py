"""Tenant-safe lead domain operations.

All mutation paths go through this module so normal editing, source ingestion, and
future integrations share the same deduplication and audit guarantees.
"""

import re
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.audit import log_action
from organizations.models import EmployeeProfile

from .models import Lead, LeadActivity, LeadAssignment, LeadAssignmentCursor, LeadSource


EDITABLE_FIELDS = (
    "name", "email", "alternate_phone", "property_type", "preferred_location",
    "budget_minimum", "budget_maximum", "bhk", "purpose", "requirement_notes",
    "source_details",
)


def company_for(user):
    if not user.is_authenticated or not user.is_active or not user.company_id or not user.company.is_active:
        raise PermissionDenied("An active company account is required.")
    return user.company


def profile_for(user):
    try:
        profile = user.employee_profile
    except EmployeeProfile.DoesNotExist:
        raise PermissionDenied("An employee profile is required for this action.")
    if not profile.is_active or not user.is_active or profile.branch.company_id != user.company_id:
        raise PermissionDenied("Your employee profile is not active in this company.")
    return profile


def is_company_admin(user):
    return user.is_superuser or user.role == "CEO"


def visible_profiles(user):
    company = company_for(user)
    profiles = EmployeeProfile.objects.filter(
        branch__company=company, user__company=company, is_active=True, user__is_active=True,
    )
    if is_company_admin(user):
        return profiles
    profile = profile_for(user)
    if user.role == "MANAGER":
        return profiles.filter(Q(pk=profile.pk) | Q(reporting_manager=profile))
    return profiles.filter(pk=profile.pk)


def lead_queryset(user):
    company = company_for(user)
    queryset = Lead.objects.select_related(
        "company", "branch", "assigned_to__user", "created_by",
    ).filter(company=company)
    if is_company_admin(user):
        return queryset
    return queryset.filter(assigned_to__in=visible_profiles(user))


def normalize_phone(phone):
    """Canonicalize common Indian mobile formats without guessing arbitrary countries.

    Stored values contain digits only.  The documented 10-digit, +91, and 091
    forms all canonicalize to the same 12-digit Indian number. Other valid-looking
    international inputs retain their country prefix after punctuation is removed.
    """
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 10 and digits[0] in "6789":
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return f"91{digits[1:]}"
    if len(digits) == 12 and digits.startswith("0") and digits[1:3] == "91":
        return digits[1:]
    if len(digits) == 13 and digits.startswith("091"):
        return digits[1:]
    return digits


def _display(value):
    if value is None or value == "":
        return "Not provided"
    return str(value)


def _activity(*, lead, actor, activity_type, field_name="", old_value="", new_value="", note="", metadata=None):
    return LeadActivity.objects.create(
        company=lead.company, lead=lead,
        performed_by=actor if getattr(actor, "is_authenticated", False) else None,
        activity_type=activity_type, field_name=field_name, old_value=_display(old_value),
        new_value=_display(new_value), note=note, metadata=metadata or {},
    )


def log_lead_activity(*, lead, actor, activity_type, note="", metadata=None):
    """Public, safe bridge used by Phase 4 creation services."""
    return _activity(lead=lead, actor=actor, activity_type=activity_type, note=note, metadata=metadata)


def _validate_branch(company, branch):
    if not branch or branch.company_id != company.id or not branch.is_active:
        raise ValidationError({"branch": "Branch must be an active branch in your company."})
    return branch


def validate_assignee(actor, assignee):
    company = company_for(actor)
    if not assignee or not assignee.is_active or not assignee.user.is_active:
        raise ValidationError({"assigned_to": "Assigned employee must be active."})
    if assignee.branch.company_id != company.id or assignee.user.company_id != company.id:
        raise ValidationError({"assigned_to": "Assigned employee must belong to your company."})
    if not visible_profiles(actor).filter(pk=assignee.pk).exists():
        raise PermissionDenied("You cannot assign a lead outside your permitted team.")
    return assignee


def _eligible_assignees(company, branch=None):
    queryset = EmployeeProfile.objects.select_related("user", "branch").filter(
        branch__company=company, user__company=company, is_active=True, user__is_active=True,
        can_receive_leads=True, user__role="EMPLOYEE",
    )
    if branch:
        queryset = queryset.filter(branch=branch)
    return queryset.order_by("pk")


def _next_round_robin_assignee(company, branch=None):
    candidates = list(_eligible_assignees(company, branch))
    if not candidates:
        return None
    # The cursor lock makes selection and cursor movement atomic across workers.
    try:
        cursor, _ = LeadAssignmentCursor.objects.select_for_update().get_or_create(company=company)
    except IntegrityError:
        cursor = LeadAssignmentCursor.objects.select_for_update().get(company=company)
    candidate_ids = [candidate.pk for candidate in candidates]
    if cursor.last_assignee_id in candidate_ids:
        position = candidate_ids.index(cursor.last_assignee_id)
        assignee = candidates[(position + 1) % len(candidates)]
    else:
        assignee = candidates[0]
    cursor.last_assignee = assignee
    cursor.save(update_fields=["last_assignee", "updated_at"])
    return assignee


def _record_assignment(*, lead, actor, assignee, assignment_type, reason=""):
    previous = lead.assigned_to
    if previous and previous.pk == assignee.pk:
        return False
    lead.assigned_to = assignee
    lead.branch = assignee.branch
    lead.save(update_fields=["assigned_to", "branch", "updated_at"])
    LeadAssignment.objects.create(
        company=lead.company, lead=lead, previous_assignee=previous, assigned_to=assignee,
        assigned_by=actor if getattr(actor, "is_authenticated", False) else None,
        assignment_type=assignment_type, reason=reason,
    )
    _activity(
        lead=lead, actor=actor,
        activity_type=LeadActivity.Type.REASSIGNED if previous else LeadActivity.Type.ASSIGNED,
        field_name="assigned_to", old_value=previous.user.username if previous else "",
        new_value=assignee.user.username, note=reason,
    )
    return True


def _source_event(*, lead, source, source_details="", external_lead_id="", external_contact_id="", external_conversation_id="", metadata=None, received_at=None):
    defaults = {
        "lead": lead, "source_details": source_details, "external_contact_id": external_contact_id,
        "external_conversation_id": external_conversation_id, "metadata": metadata or {},
        "received_at": received_at or timezone.now(),
    }
    if external_lead_id:
        try:
            with transaction.atomic():
                event, created = LeadSource.objects.get_or_create(
                    company=lead.company, source=source, external_lead_id=external_lead_id, defaults=defaults,
                )
        except IntegrityError:
            event = LeadSource.objects.get(company=lead.company, source=source, external_lead_id=external_lead_id)
            created = False
        if event.lead_id != lead.pk:
            raise ValidationError({"external_lead_id": "This source lead identifier already belongs to another lead."})
        return event, created
    return LeadSource.objects.create(company=lead.company, source=source, external_lead_id="", **defaults), True


@dataclass
class LeadMutation:
    lead: Lead
    created: bool


def _initial_branch(actor, company, data):
    branch = data.pop("branch", None)
    if branch is not None:
        return _validate_branch(company, branch)
    if actor is not None and not is_company_admin(actor):
        return profile_for(actor).branch
    branches = list(company.branches.filter(is_active=True).order_by("pk")[:2])
    if len(branches) == 1:
        return branches[0]
    raise ValidationError({"branch": "Choose an active branch when your company has multiple branches."})


def _create_or_enrich_for_company(*, company, actor, data):
    """Internal implementation for authenticated CRM and server-trusted integration intake."""
    data = data.copy()
    source = data.pop("source", Lead.Source.MANUAL)
    metadata = data.pop("source_metadata", {})
    external_lead_id = data.pop("external_lead_id", "")
    external_contact_id = data.pop("external_contact_id", "")
    external_conversation_id = data.pop("external_conversation_id", "")
    received_at = data.pop("received_at", None)
    requested_assignee = data.pop("assigned_to", None)
    phone = data.pop("phone")
    normalized_phone = normalize_phone(phone)
    if not normalized_phone:
        raise ValidationError({"phone": "Enter a valid phone number."})

    with transaction.atomic():
        existing = Lead.objects.select_for_update().filter(company=company, normalized_phone=normalized_phone).first()
        if existing:
            source_event, source_created = _source_event(lead=existing, source=source, source_details=data.get("source_details", ""), external_lead_id=external_lead_id, external_contact_id=external_contact_id, external_conversation_id=external_conversation_id, metadata=metadata, received_at=received_at)
            if source_created:
                _activity(lead=existing, actor=actor, activity_type=LeadActivity.Type.SOURCE_RECEIVED, note=f"Source received: {source}", metadata={"source": source, "source_id": source_event.pk})
            changed = _enrich_locked(lead=existing, actor=actor, data=data)
            if changed:
                log_action(actor=actor, company=company, action="lead.enriched", target=existing, metadata={"fields": changed})
            return LeadMutation(existing, False)

        branch = _initial_branch(actor, company, data)
        if requested_assignee is not None:
            assignee = validate_assignee(actor, requested_assignee)
        elif actor is not None and not is_company_admin(actor) and actor.role != "MANAGER":
            assignee = profile_for(actor)
        else:
            assignee = _next_round_robin_assignee(company, branch)
        if assignee and assignee.branch_id != branch.id:
            branch = assignee.branch
        try:
            with transaction.atomic():
                lead = Lead.objects.create(company=company, branch=branch, assigned_to=assignee, created_by=actor if actor is not None else None, phone=phone.strip(), normalized_phone=normalized_phone, source=source, **data)
        except IntegrityError:
            lead = Lead.objects.select_for_update().get(company=company, normalized_phone=normalized_phone)
            source_event, source_created = _source_event(lead=lead, source=source, source_details=data.get("source_details", ""), external_lead_id=external_lead_id, external_contact_id=external_contact_id, external_conversation_id=external_conversation_id, metadata=metadata, received_at=received_at)
            if source_created:
                _activity(lead=lead, actor=actor, activity_type=LeadActivity.Type.SOURCE_RECEIVED, note=f"Source received: {source}", metadata={"source": source, "source_id": source_event.pk})
            _enrich_locked(lead=lead, actor=actor, data=data)
            return LeadMutation(lead, False)
        _activity(lead=lead, actor=actor, activity_type=LeadActivity.Type.CREATED, note="Lead created")
        source_event, _ = _source_event(lead=lead, source=source, source_details=lead.source_details, external_lead_id=external_lead_id, external_contact_id=external_contact_id, external_conversation_id=external_conversation_id, metadata=metadata, received_at=received_at)
        _activity(lead=lead, actor=actor, activity_type=LeadActivity.Type.SOURCE_RECEIVED, note=f"Source received: {source}", metadata={"source": source, "source_id": source_event.pk})
        if assignee:
            LeadAssignment.objects.create(company=company, lead=lead, assigned_to=assignee, assigned_by=actor if actor is not None else None, assignment_type=LeadAssignment.Type.ASSIGNED if requested_assignee else LeadAssignment.Type.AUTO_ASSIGNED)
            _activity(lead=lead, actor=actor, activity_type=LeadActivity.Type.ASSIGNED, field_name="assigned_to", new_value=assignee.user.username)
        log_action(actor=actor, company=company, action="lead.created", target=lead, metadata={"source": source})
        return LeadMutation(lead, True)


def create_or_enrich_lead(*, actor, data, company=None):
    """Create a lead or atomically enrich the existing tenant phone match."""
    company = company or company_for(actor)
    return _create_or_enrich_for_company(company=company, actor=actor, data=data)


def _enrich_locked(*, lead, actor, data):
    changed = []
    for field in EDITABLE_FIELDS:
        if field not in data:
            continue
        incoming = data[field]
        if incoming in (None, ""):
            continue
        current = getattr(lead, field)
        if current != incoming:
            setattr(lead, field, incoming)
            changed.append(field)
            _activity(lead=lead, actor=actor, activity_type=LeadActivity.Type.FIELD_CHANGED,
                      field_name=field, old_value=current, new_value=incoming, note="Lead enriched")
    if changed:
        lead.save(update_fields=[*changed, "updated_at"])
    return changed


def update_lead(*, actor, lead, data):
    company_for(actor)
    data = data.copy()
    if "phone" in data:
        submitted = normalize_phone(data.pop("phone"))
        if submitted != lead.normalized_phone:
            raise ValidationError({"phone": "Phone cannot be changed after lead creation."})
    data.pop("normalized_phone", None)
    assigned_to = data.pop("assigned_to", None)
    if assigned_to is not None:
        if actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
            raise PermissionDenied("Only managers can reassign leads.")
        return reassign_lead(actor=actor, lead=lead, assignee=assigned_to, reason=data.pop("assignment_note", ""))
    data.pop("branch", None)
    source = data.pop("source", None)
    if source is not None:
        raise ValidationError({"source": "Source attribution is recorded through source events, not normal editing."})
    allowed = set(EDITABLE_FIELDS) | {"status", "temperature"}
    unexpected = set(data) - allowed
    if unexpected:
        raise ValidationError({field: "This field cannot be changed." for field in unexpected})
    with transaction.atomic():
        locked = Lead.objects.select_for_update().get(pk=lead.pk, company=company_for(actor))
        changed = []
        for field, value in data.items():
            old = getattr(locked, field)
            if old == value:
                continue
            setattr(locked, field, value)
            changed.append(field)
            event_type = LeadActivity.Type.STATUS_CHANGED if field == "status" else LeadActivity.Type.TEMPERATURE_CHANGED if field == "temperature" else LeadActivity.Type.FIELD_CHANGED
            _activity(lead=locked, actor=actor, activity_type=event_type, field_name=field, old_value=old, new_value=value)
        if changed:
            locked.save(update_fields=[*changed, "updated_at"])
            log_action(actor=actor, company=locked.company, action="lead.updated", target=locked, metadata={"fields": changed})
        return locked


def reassign_lead(*, actor, lead, assignee, reason=""):
    if actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
        raise PermissionDenied("Only managers can reassign leads.")
    assignee = validate_assignee(actor, assignee)
    with transaction.atomic():
        locked = Lead.objects.select_for_update().get(pk=lead.pk, company=company_for(actor))
        _record_assignment(lead=locked, actor=actor, assignee=assignee, assignment_type=LeadAssignment.Type.REASSIGNED, reason=reason)
        log_action(actor=actor, company=locked.company, action="lead.reassigned", target=locked, metadata={"assigned_to": assignee.pk}, reason=reason)
        return locked


def move_lead_to_follow_up(*, actor, lead, data):
    """Create one active follow-up for a lead safely and atomically."""

    from workspace.models import FollowUp
    from workspace.services import create_follow_up

    company = company_for(actor)

    with transaction.atomic():
        # Lock ONLY the Lead row.
        # Do not use select_related() here because PostgreSQL can reject
        # FOR UPDATE when nullable relations are joined.
        locked = Lead.objects.select_for_update().get(
            pk=lead.pk,
            company_id=company.id,
        )

        if not locked.assigned_to_id:
            raise ValidationError({
                "assigned_to": "Assign this lead before moving it to follow-up."
            })

        # Verify the assignee belongs to the same active company.
        assignee = EmployeeProfile.objects.select_related(
            "user",
            "branch",
        ).filter(
            pk=locked.assigned_to_id,
            branch__company_id=company.id,
            user__company_id=company.id,
            is_active=True,
            user__is_active=True,
        ).first()

        if not assignee:
            raise ValidationError({
                "assigned_to": "The assigned employee is no longer active in this company."
            })

        # Check whether an active follow-up already exists.
        # This query intentionally does NOT use select_for_update().
        existing = FollowUp.objects.filter(
            company_id=company.id,
            lead_id=locked.pk,
            status__in=(
                FollowUp.Status.PENDING,
                FollowUp.Status.IN_PROGRESS,
                FollowUp.Status.POSTPONED,
                FollowUp.Status.MISSED,
            ),
        ).order_by(
            "scheduled_at",
            "pk",
        ).first()

        if existing:
            return existing, False

        follow_up_data = {
            "assigned_to": assignee,
            "lead": locked,
            "title": data.get("title") or f"Follow up: {locked.name or locked.phone}",
            "description": data.get("description", ""),
            "scheduled_at": data["scheduled_at"],
            "follow_up_type": data.get("follow_up_type", "CALL"),
            "priority": data.get("priority", "MEDIUM"),
            "status": FollowUp.Status.PENDING,
        }

        follow_up = create_follow_up(
            actor=actor,
            data=follow_up_data,
        )

        old_status = locked.status

        if old_status != Lead.Status.FOLLOW_UP_NEEDED:
            locked.status = Lead.Status.FOLLOW_UP_NEEDED
            locked.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            _activity(
                lead=locked,
                actor=actor,
                activity_type=LeadActivity.Type.STATUS_CHANGED,
                field_name="status",
                old_value=old_status,
                new_value=Lead.Status.FOLLOW_UP_NEEDED,
                note="Moved to follow-up workflow",
                metadata={
                    "follow_up_id": follow_up.pk,
                },
            )

        log_action(
            actor=actor,
            company=locked.company,
            action="lead.moved_to_follow_up",
            target=locked,
            metadata={
                "follow_up_id": follow_up.pk,
            },
        )

        return follow_up, True


def add_note(*, actor, lead, note):
    if not note.strip():
        raise ValidationError({"note": "A note cannot be empty."})
    with transaction.atomic():
        locked = Lead.objects.select_for_update().get(pk=lead.pk, company=company_for(actor))
        return _activity(lead=locked, actor=actor, activity_type=LeadActivity.Type.NOTE_ADDED, note=note.strip())


def delete_lead(*, actor, lead):
    if actor.role not in ("CEO", "MANAGER") and not actor.is_superuser:
        raise PermissionDenied("Only managers can delete leads.")
    with transaction.atomic():
        locked = Lead.objects.select_for_update().get(pk=lead.pk, company=company_for(actor))
        # AuditLog stores only model label + identifier, so this remains useful after
        # hard deletion without retaining lead contact data.
        log_action(actor=actor, company=locked.company, action="lead.deleted", target=locked)
        locked.delete()

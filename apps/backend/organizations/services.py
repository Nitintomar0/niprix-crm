from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.audit import log_action

from .models import EmployeeProfile


def visible_employee_profiles(user):
    """Return the tenant-safe employee scope for profile and HRMS operations."""
    from .models import EmployeeProfile

    queryset = EmployeeProfile.objects.select_related("user", "branch", "department", "reporting_manager__user").filter(is_deleted=False)
    if not user or not user.is_authenticated:
        return queryset.none()
    if user.is_superuser or user.role == "CEO":
        return queryset.filter(branch__company=user.company)
    try:
        profile = user.employee_profile
    except EmployeeProfile.DoesNotExist:
        return queryset.none()
    if user.role == "MANAGER":
        return queryset.filter(branch__company=profile.branch.company).filter(Q(pk=profile.pk) | Q(reporting_manager=profile))
    return queryset.filter(pk=profile.pk, branch__company=profile.branch.company)


def validate_reporting_manager(profile, manager):
    if not manager:
        return
    if profile and manager.pk == profile.pk:
        raise ValidationError({"reporting_manager": "An employee cannot report to themselves."})
    if manager.branch.company_id != profile.branch.company_id:
        raise ValidationError({"reporting_manager": "Manager must belong to the same company."})
    cursor = manager
    seen = set()
    while cursor:
        if cursor.pk in seen or (profile and cursor.pk == profile.pk):
            raise ValidationError({"reporting_manager": "This assignment would create a reporting cycle."})
        seen.add(cursor.pk)
        cursor = cursor.reporting_manager


def deactivate_employee(*, actor, profile):
    """Deactivate an employee without orphaning their live customer work."""
    if not (actor.is_superuser or actor.role == "CEO"):
        raise PermissionDenied("Only CEO users can deactivate employees.")

    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
    from leads.models import Lead
    from leads.services import _next_round_robin_assignee, reassign_lead
    from workspace.models import FollowUp
    from workspace.services import ACTIVE_FOLLOW_UP_STATUSES, reassign_follow_up

    with transaction.atomic():
        locked = EmployeeProfile.objects.select_for_update().select_related("user", "branch__company").get(pk=profile.pk)
        if locked.branch.company_id != actor.company_id:
            raise PermissionDenied("Employee is not available in your company.")
        if locked.user_id == actor.pk:
            raise ValidationError({"detail": "A CEO cannot deactivate their own account."})
        if not locked.is_active and not locked.user.is_active:
            return {"already_deactivated": True, "leads_reassigned": 0, "follow_ups_reassigned": 0}

        # Do this before choosing recipients so existing eligibility logic can
        # never select the employee who is being removed.
        user = type(locked.user).objects.select_for_update().get(pk=locked.user_id)
        locked.is_active = False
        locked.can_receive_leads = False
        if locked.employment_status != EmployeeProfile.EmploymentStatus.OFFBOARDED:
            locked.employment_status = EmployeeProfile.EmploymentStatus.INACTIVE
        locked.save(update_fields=["is_active", "can_receive_leads", "employment_status", "updated_at"])
        user.is_active = False
        user.save(update_fields=["is_active"])

        leads = list(Lead.objects.select_for_update().filter(company=locked.branch.company, assigned_to=locked).order_by("pk"))
        follow_ups = list(FollowUp.objects.select_for_update().filter(
            company=locked.branch.company, assigned_to=locked,
            status__in=ACTIVE_FOLLOW_UP_STATUSES,
        ).order_by("pk"))

        def replacement_for(branch):
            assignee = _next_round_robin_assignee(locked.branch.company, branch)
            if not assignee:
                raise ValidationError({"detail": f"Cannot deactivate this employee: no active, eligible replacement exists in {branch.name}."})
            return assignee

        for lead in leads:
            reassign_lead(
                actor=actor, lead=lead, assignee=replacement_for(lead.branch),
                reason=f"Reassigned because {locked.user.username} was deactivated.",
            )
        for follow_up in follow_ups:
            reassign_follow_up(
                actor=actor, follow_up=follow_up, assignee=replacement_for(follow_up.branch),
                note=f"Reassigned because {locked.user.username} was deactivated.",
            )

        # Blacklist recorded refresh tokens immediately; authentication and the
        # refresh serializer also consult the current account state.
        for token in OutstandingToken.objects.filter(user=user, expires_at__gt=timezone.now()):
            BlacklistedToken.objects.get_or_create(token=token)
        log_action(
            actor=actor, company=locked.branch.company, action="employee.deactivated", target=locked,
            metadata={"leads_reassigned": len(leads), "follow_ups_reassigned": len(follow_ups)},
        )
        return {"already_deactivated": False, "leads_reassigned": len(leads), "follow_ups_reassigned": len(follow_ups)}


def delete_inactive_employee(*, actor, profile):
    """Remove an inactive employee from operations without corrupting history.

    EmployeeProfile is intentionally protected by attendance, work, and HR
    records. Hard-deleting it would either fail or require deleting evidence.
    This tombstones the inactive account instead: it is hidden from every
    operational People query, cannot authenticate, and keeps all historical
    foreign keys and audit records valid.
    """
    if not (actor.is_superuser or actor.role == "CEO"):
        raise PermissionDenied("Only CEO users can permanently delete inactive employees.")
    with transaction.atomic():
        locked = EmployeeProfile.objects.select_for_update().select_related("user", "branch__company").get(pk=profile.pk)
        if locked.branch.company_id != actor.company_id:
            raise PermissionDenied("Employee is not available in your company.")
        if locked.is_deleted:
            return {"already_deleted": True}
        if locked.is_active or locked.user.is_active or locked.employment_status not in (
            EmployeeProfile.EmploymentStatus.INACTIVE, EmployeeProfile.EmploymentStatus.OFFBOARDED,
        ):
            raise ValidationError({"detail": "Only inactive or offboarded employees can be permanently deleted."})
        if locked.user_id == actor.pk:
            raise ValidationError({"detail": "A CEO cannot delete their own account."})

        # A deleted manager must no longer appear in the reporting chain.
        EmployeeProfile.objects.filter(reporting_manager=locked, is_deleted=False).update(reporting_manager=None)
        locked.is_deleted = True
        locked.deleted_at = timezone.now()
        locked.can_receive_leads = False
        locked.save(update_fields=["is_deleted", "deleted_at", "can_receive_leads", "updated_at"])
        log_action(actor=actor, company=locked.branch.company, action="employee.deleted", target=locked)
    return {"already_deleted": False}

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.views import OptionalPageNumberPagination

from .models import Notification
from .serializers import NotificationSerializer


GLOBAL_SEARCH_DEFAULT_LIMIT = 5
GLOBAL_SEARCH_MAX_LIMIT = 10


def _masked_phone(value):
    """Return a useful, non-sensitive phone hint for a search suggestion."""
    digits = "".join(character for character in value or "" if character.isdigit())
    if not digits:
        return ""
    return f"•••• {digits[-4:]}" if len(digits) > 4 else f"•• {digits}"


def _search_query(term, *, name="name", email="email", phone="normalized_phone", extra=()):
    """Build the shared partial-text/partial-phone predicate without changing stored phone formats."""
    query = Q(**{f"{name}__icontains": term}) | Q(**{f"{email}__icontains": term})
    digits = "".join(character for character in term if character.isdigit())
    if len(digits) >= 2:
        # Normalized values retain every phone digit, so icontains deliberately
        # supports 2+ digits from the middle of an Indian or international number.
        query |= Q(**{f"{phone}__icontains": digits})
    for field in extra:
        query |= Q(**{f"{field}__icontains": term})
    return query


class GlobalSearchView(APIView):
    """Compact, permission-scoped suggestions for the navbar search."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        term = request.query_params.get("q", "").strip()
        if len(term) > 100:
            raise ValidationError({"q": "Must be 100 characters or fewer."})
        try:
            limit = int(request.query_params.get("limit", GLOBAL_SEARCH_DEFAULT_LIMIT))
        except ValueError:
            raise ValidationError({"limit": "Must be a positive integer."})
        if not 1 <= limit <= GLOBAL_SEARCH_MAX_LIMIT:
            raise ValidationError({"limit": f"Must be between 1 and {GLOBAL_SEARCH_MAX_LIMIT}."})

        # The client does not request until this threshold is met. Returning an
        # empty shape here also makes direct API use safe and predictable.
        searchable = len(term) >= 2 or len("".join(character for character in term if character.isdigit())) >= 2
        result = {"leads": [], "lead_recovery": [], "follow_ups": [], "raw_data": [], "inventory": []}
        if not searchable:
            return Response({"query": term, "results": result})

        # Import lazily to keep core's notification module free from app import
        # cycles. Each helper is the canonical source of tenant and role scope.
        from inventory.views import inventory_queryset
        from leads.models import Lead
        from leads.services import lead_queryset
        from raw_data.services import raw_queryset
        from workspace.models import FollowUp
        from workspace.services import follow_up_queryset

        lead_filter = _search_query(term, extra=("preferred_location",))
        lead_digits = "".join(character for character in term if character.isdigit())
        if term.isdigit() and len(term) <= 9:
            lead_filter |= Q(pk=int(term))

        active_leads = lead_queryset(request.user).filter(lead_filter, recovery_category__isnull=True).order_by("-updated_at", "-id")[:limit]
        result["leads"] = [
            {
                "id": lead.pk,
                "title": lead.name or "Unnamed lead",
                "detail": " · ".join(value for value in (_masked_phone(lead.phone), lead.email, lead.status.replace("_", " ").title()) if value),
            }
            for lead in active_leads
        ]

        recovery_leads = lead_queryset(request.user).filter(lead_filter, recovery_category__isnull=False).order_by("-recovery_at", "-id")[:limit]
        result["lead_recovery"] = [
            {
                "id": lead.pk,
                "title": lead.name or "Unnamed lead",
                "detail": " · ".join(value for value in (_masked_phone(lead.phone), lead.recovery_category.replace("_", " ").title() if lead.recovery_category else "") if value),
            }
            for lead in recovery_leads
        ]

        follow_up_filter = (
            Q(title__icontains=term)
            | Q(customer_name__icontains=term)
            | Q(lead__name__icontains=term)
            | Q(lead__email__icontains=term)
        )
        if len(lead_digits) >= 2:
            follow_up_filter |= Q(lead__normalized_phone__icontains=lead_digits) | Q(customer_phone__icontains=lead_digits)
        follow_ups = follow_up_queryset(request.user).filter(follow_up_filter).order_by("-updated_at", "-id")[:limit]
        result["follow_ups"] = [
            {
                "id": follow_up.pk,
                "title": follow_up.title or (follow_up.lead.name if follow_up.lead else follow_up.customer_name) or "Untitled follow-up",
                "detail": " · ".join(value for value in (
                    follow_up.lead.name if follow_up.lead else follow_up.customer_name,
                    _masked_phone(follow_up.lead.phone if follow_up.lead else follow_up.customer_phone),
                    follow_up.status.replace("_", " ").title(),
                ) if value),
            }
            for follow_up in follow_ups
        ]

        # Raw Data has stricter CEO-only access. Do not execute, count, or
        # otherwise reveal that query to non-CEOs.
        if request.user.is_superuser or request.user.role == "CEO":
            raw_leads = raw_queryset(request.user).filter(
                _search_query(term, extra=("preferred_location", "property_type", "source_details"))
            ).order_by("-updated_at", "-id")[:limit]
            result["raw_data"] = [
                {
                    "id": raw.pk,
                    "title": raw.name or "Unnamed raw lead",
                    "detail": " · ".join(value for value in (_masked_phone(raw.phone), raw.email, raw.preferred_location, raw.source.replace("_", " ").title()) if value),
                }
                for raw in raw_leads
            ]

        inventory = inventory_queryset(request.user).filter(
            Q(project__icontains=term) | Q(unit_number__icontains=term)
        ).order_by("-updated_at", "-id")[:limit]
        result["inventory"] = [
            {
                "id": item.pk,
                "title": item.project,
                "detail": " · ".join(value for value in (f"Unit {item.unit_number}", item.status.replace("_", " ").title(), item.property_type) if value),
            }
            for item in inventory
        ]
        return Response({"query": term, "results": result})


def _prepare_requester_reminders(user):
    if not user.company_id:
        return
    # No scheduler is configured in this deployment. Preparing only this
    # user's events here is tenant-safe and preserves the same idempotency
    # guarantees a scheduled worker would use.
    from workspace.services import prepare_reminder_events
    prepare_reminder_events(user=user)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = OptionalPageNumberPagination

    def get_queryset(self):
        _prepare_requester_reminders(self.request.user)
        if not self.request.user.company_id:
            return Notification.objects.none()
        queryset = Notification.objects.filter(
            company_id=self.request.user.company_id,
            recipient=self.request.user,
        )
        unread = self.request.query_params.get("unread")
        if unread is not None:
            if unread not in {"true", "false"}:
                raise ValidationError({"unread": "Use true or false."})
            queryset = queryset.filter(is_read=unread == "true")
        return queryset


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _prepare_requester_reminders(request.user)
        count = Notification.objects.filter(
            company_id=request.user.company_id,
            recipient=request.user,
            is_read=False,
        ).count() if request.user.company_id else 0
        return Response({"count": count})


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        notification = Notification.objects.filter(
            pk=pk,
            company_id=request.user.company_id,
            recipient=request.user,
        ).first()
        if not notification:
            return Response({"detail": "Notification is not available."}, status=status.HTTP_404_NOT_FOUND)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(
            company_id=request.user.company_id,
            recipient=request.user,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)

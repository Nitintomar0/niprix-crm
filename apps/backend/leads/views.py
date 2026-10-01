from datetime import date

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Lead, LeadActivity, LeadAssignment, LeadSource
from .serializers import (
    LeadActivitySerializer, LeadAssignmentSerializer, LeadNoteSerializer, LeadReassignSerializer,
    LeadMoveToFollowUpSerializer, LeadSerializer, LeadSourceSerializer, LeadStatusSerializer, LeadTemperatureSerializer,
)
from .services import add_note, company_for, delete_lead, lead_queryset, move_lead_to_follow_up, reassign_lead, update_lead
from workspace.serializers import FollowUpSerializer


class LeadPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class ScopedLeadListMixin:
    pagination_class = LeadPagination

    def _date(self, value, name):
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValidationError({name: "Use ISO date format YYYY-MM-DD."})

    def filtered_queryset(self):
        params = self.request.query_params
        # The Leads workspace is the active inbox. A lead remains intact and
        # addressable after entering follow-up, but is not shown in both lists.
        queryset = lead_queryset(self.request.user).exclude(status=Lead.Status.FOLLOW_UP_NEEDED)
        if params.get("search"):
            search = params["search"].strip()
            if len(search) > 200:
                raise ValidationError({"search": "Must be 200 characters or fewer."})
            normalized = "".join(character for character in search if character.isdigit())
            query = Q(name__icontains=search) | Q(email__icontains=search) | Q(preferred_location__icontains=search)
            if search.isdigit():
                query |= Q(pk=int(search))
            if normalized:
                from .services import normalize_phone
                query |= Q(normalized_phone__icontains=normalize_phone(search))
            queryset = queryset.filter(query)
        for key, field, valid in (
            ("status", "status", Lead.Status.values), ("temperature", "temperature", Lead.Temperature.values),
            ("source", "source", Lead.Source.values),
        ):
            if params.get(key):
                values = [value.strip() for value in params[key].split(",") if value.strip()]
                if not values or any(value not in valid for value in values):
                    raise ValidationError({key: "Contains an unsupported value."})
                queryset = queryset.filter(**{f"{field}__in": values})
        for key, field in (("assigned_to", "assigned_to_id"), ("branch", "branch_id")):
            if params.get(key):
                try:
                    value = int(params[key])
                except ValueError:
                    raise ValidationError({key: "Must be a positive integer."})
                if value <= 0:
                    raise ValidationError({key: "Must be a positive integer."})
                queryset = queryset.filter(**{field: value})
        for key, field in (("property_type", "property_type"), ("location", "preferred_location")):
            if params.get(key):
                queryset = queryset.filter(**{f"{field}__icontains": params[key].strip()})
        date_from = self._date(params.get("date_from"), "date_from")
        date_to = self._date(params.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "Must be on or after date_from."})
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        ordering = params.get("ordering", "-created_at")
        if ordering.lstrip("-") not in {"created_at", "updated_at", "name", "status", "temperature"}:
            raise ValidationError({"ordering": "Unsupported ordering field."})
        return queryset.order_by(ordering, "-id")


class LeadListCreateView(ScopedLeadListMixin, generics.ListCreateAPIView):
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.filtered_queryset()


class LeadDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return lead_queryset(self.request.user)

    def perform_destroy(self, instance):
        delete_lead(actor=self.request.user, lead=instance)


def _lead_or_denied(user, pk):
    lead = lead_queryset(user).filter(pk=pk).first()
    if not lead:
        raise PermissionDenied("Lead is not available.")
    return lead


class LeadStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = LeadStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = _lead_or_denied(request.user, pk)
        updated = update_lead(actor=request.user, lead=lead, data={"status": serializer.validated_data["status"]})
        if serializer.validated_data.get("note"):
            add_note(actor=request.user, lead=updated, note=serializer.validated_data["note"])
        return Response(LeadSerializer(updated, context={"request": request}).data)


class LeadTemperatureView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = LeadTemperatureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = _lead_or_denied(request.user, pk)
        updated = update_lead(actor=request.user, lead=lead, data={"temperature": serializer.validated_data["temperature"]})
        if serializer.validated_data.get("note"):
            add_note(actor=request.user, lead=updated, note=serializer.validated_data["note"])
        return Response(LeadSerializer(updated, context={"request": request}).data)


class LeadAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = LeadReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = _lead_or_denied(request.user, pk)
        updated = reassign_lead(actor=request.user, lead=lead, assignee=serializer.validated_data["assigned_to"], reason=serializer.validated_data.get("note", ""))
        return Response(LeadSerializer(updated, context={"request": request}).data)


class LeadMoveToFollowUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        serializer = LeadMoveToFollowUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lead = _lead_or_denied(request.user, pk)
        follow_up, created = move_lead_to_follow_up(
            actor=request.user, lead=lead, data=serializer.validated_data,
        )
        return Response(
            {"follow_up": FollowUpSerializer(follow_up, context={"request": request}).data, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeadActivityListCreateView(generics.ListCreateAPIView):
    serializer_class = LeadActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LeadPagination

    def get_queryset(self):
        _lead_or_denied(self.request.user, self.kwargs["pk"])
        return LeadActivity.objects.select_related("performed_by").filter(company=company_for(self.request.user), lead_id=self.kwargs["pk"])

    def post(self, request, pk):
        lead = _lead_or_denied(request.user, pk)
        serializer = LeadNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = add_note(actor=request.user, lead=lead, note=serializer.validated_data["note"])
        return Response(LeadActivitySerializer(activity).data, status=status.HTTP_201_CREATED)


class LeadSourceListView(generics.ListAPIView):
    serializer_class = LeadSourceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LeadPagination

    def get_queryset(self):
        _lead_or_denied(self.request.user, self.kwargs["pk"])
        return LeadSource.objects.filter(company=company_for(self.request.user), lead_id=self.kwargs["pk"])


class LeadAssignmentListView(generics.ListAPIView):
    serializer_class = LeadAssignmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = LeadPagination

    def get_queryset(self):
        _lead_or_denied(self.request.user, self.kwargs["pk"])
        return LeadAssignment.objects.select_related("previous_assignee__user", "assigned_to__user", "assigned_by").filter(company=company_for(self.request.user), lead_id=self.kwargs["pk"])


class LeadSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = lead_queryset(request.user)
        return Response({
            "scope": "company" if request.user.role == "CEO" or request.user.is_superuser else "team" if request.user.role == "MANAGER" else "personal",
            "total": queryset.count(),
            "new": queryset.filter(status=Lead.Status.NEW).count(),
            "contacted": queryset.filter(status=Lead.Status.CONTACTED).count(),
            "hot": queryset.filter(temperature=Lead.Temperature.HOT).count(),
            "follow_up_needed": queryset.filter(status=Lead.Status.FOLLOW_UP_NEEDED).count(),
            "site_visits": queryset.filter(status__in=[Lead.Status.SITE_VISIT_REQUESTED, Lead.Status.SITE_VISIT_DONE]).count(),
            "closed": queryset.filter(status=Lead.Status.CLOSED).count(),
        })

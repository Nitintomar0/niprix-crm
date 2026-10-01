from datetime import date, timedelta

from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from organizations.views import OptionalPageNumberPagination

from .models import FollowUp, FollowUpActivity, Task
from .serializers import (
    CompleteSerializer, FollowUpActivitySerializer, FollowUpSerializer, PostponeSerializer,
    ReassignSerializer, ReminderPreferenceSerializer, TaskSerializer,
)
from .services import (
    ACTIVE_FOLLOW_UP_STATUSES, ACTIVE_TASK_STATUSES, company_for, follow_up_overdue_q,
    follow_up_queryset, get_reminder_preference, reassign_follow_up, reassign_task,
    task_overdue_q, task_queryset, transition_follow_up, transition_task, update_follow_up,
)


class WorkspacePagination(OptionalPageNumberPagination):
    page_size = 20
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        return super(OptionalPageNumberPagination, self).paginate_queryset(queryset, request, view)


class ScopedListMixin:
    pagination_class = WorkspacePagination

    def initial(self, request, *args, **kwargs):
        for name, maximum in (("page", None), ("page_size", 100)):
            value = request.query_params.get(name)
            if value is not None:
                try:
                    number = int(value)
                except ValueError:
                    raise ValidationError({name: "Must be a positive integer."})
                if number <= 0 or (maximum is not None and number > maximum):
                    raise ValidationError({name: "Must be a positive integer." if maximum is None else f"Must be between 1 and {maximum}."})
        return super().initial(request, *args, **kwargs)

    def _date(self, name):
        value = self.request.query_params.get(name)
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValidationError({name: "Use ISO date format YYYY-MM-DD."})

    def _employee(self, queryset):
        value = self.request.query_params.get("assigned_to")
        if not value:
            return queryset
        try:
            employee_id = int(value)
        except ValueError:
            raise ValidationError({"assigned_to": "Must be a positive integer."})
        if employee_id <= 0:
            raise ValidationError({"assigned_to": "Must be a positive integer."})
        return queryset.filter(assigned_to_id=employee_id)

    def _common_filters(self, queryset, *, date_field, statuses, priorities):
        params = self.request.query_params
        queryset = self._employee(queryset)
        if params.get("lead"):
            try:
                lead_id = int(params["lead"])
            except ValueError:
                raise ValidationError({"lead": "Must be a positive integer."})
            if lead_id <= 0:
                raise ValidationError({"lead": "Must be a positive integer."})
            queryset = queryset.filter(lead_id=lead_id)
        if params.get("status"):
            values = [value.strip() for value in params["status"].split(",") if value.strip()]
            if not values or any(value not in statuses for value in values):
                raise ValidationError({"status": "Contains an unsupported status."})
            queryset = queryset.filter(status__in=values)
        if params.get("priority"):
            values = [value.strip() for value in params["priority"].split(",") if value.strip()]
            if not values or any(value not in priorities for value in values):
                raise ValidationError({"priority": "Contains an unsupported priority."})
            queryset = queryset.filter(priority__in=values)
        if params.get("search"):
            search = params["search"].strip()
            if len(search) > 200:
                raise ValidationError({"search": "Must be 200 characters or fewer."})
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        on_date = self._date("date")
        date_from = self._date("date_from")
        date_to = self._date("date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "Must be on or after date_from."})
        if on_date:
            queryset = queryset.filter(**{f"{date_field}__date" if date_field == "scheduled_at" else date_field: on_date})
        if date_from:
            queryset = queryset.filter(**{f"{date_field}__date__gte" if date_field == "scheduled_at" else f"{date_field}__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{date_field}__date__lte" if date_field == "scheduled_at" else f"{date_field}__lte": date_to})
        return queryset


class FollowUpListCreateView(ScopedListMixin, generics.ListCreateAPIView):
    serializer_class = FollowUpSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = follow_up_queryset(self.request.user)
        queryset = self._common_filters(queryset, date_field="scheduled_at", statuses=FollowUp.Status.values, priorities=["LOW", "MEDIUM", "HIGH", "URGENT"])
        if self.request.query_params.get("overdue") == "true":
            queryset = queryset.filter(follow_up_overdue_q())
        return queryset.order_by("scheduled_at", "id")


class FollowUpDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FollowUpSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return follow_up_queryset(self.request.user)

    def perform_destroy(self, instance):
        if instance.status == FollowUp.Status.COMPLETED:
            raise ValidationError({"detail": "Completed follow-ups are retained for audit history."})
        # Preserve the task itself but remove its obsolete follow-up pointer;
        # activity rows describe the deleted work item and are removed with it.
        # The linked Lead is deliberately untouched (FollowUp.lead is SET_NULL).
        with transaction.atomic():
            Task.objects.filter(company=instance.company, related_follow_up=instance).update(related_follow_up=None)
            FollowUpActivity.objects.filter(company=instance.company, follow_up=instance).delete()
            log_action(actor=self.request.user, company=instance.company, action="follow_up.deleted", target=instance)
            instance.delete()


class FollowUpCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        follow_up = follow_up_queryset(request.user).filter(pk=pk).first()
        if not follow_up:
            raise PermissionDenied("Follow-up is not available.")
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(FollowUpSerializer(transition_follow_up(actor=request.user, follow_up=follow_up, status=FollowUp.Status.COMPLETED, note=serializer.validated_data.get("note", ""))).data)


class FollowUpPostponeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        follow_up = follow_up_queryset(request.user).filter(pk=pk).first()
        if not follow_up:
            raise PermissionDenied("Follow-up is not available.")
        serializer = PostponeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(FollowUpSerializer(transition_follow_up(actor=request.user, follow_up=follow_up, status=FollowUp.Status.POSTPONED, scheduled_at=data["scheduled_at"], note=data.get("note", ""))).data)


class FollowUpReassignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        follow_up = follow_up_queryset(request.user).filter(pk=pk).first()
        if not follow_up:
            raise PermissionDenied("Follow-up is not available.")
        serializer = ReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(FollowUpSerializer(reassign_follow_up(actor=request.user, follow_up=follow_up, assignee=data["assigned_to"], note=data.get("note", ""))).data)


class FollowUpActivityListView(generics.ListAPIView):
    serializer_class = FollowUpActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = WorkspacePagination

    def get_queryset(self):
        if not follow_up_queryset(self.request.user).filter(pk=self.kwargs["pk"]).exists():
            raise PermissionDenied("Follow-up activity is not available.")
        return FollowUpActivity.objects.select_related("performed_by").filter(company=company_for(self.request.user), follow_up_id=self.kwargs["pk"])


class TaskListCreateView(ScopedListMixin, generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = task_queryset(self.request.user)
        queryset = self._common_filters(queryset, date_field="due_date", statuses=Task.Status.values, priorities=["LOW", "MEDIUM", "HIGH", "URGENT"])
        if self.request.query_params.get("overdue") == "true":
            queryset = queryset.filter(task_overdue_q())
        return queryset.order_by("due_date", "due_time", "id")


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return task_queryset(self.request.user)

    def perform_destroy(self, instance):
        if instance.status == Task.Status.COMPLETED:
            raise ValidationError({"detail": "Completed tasks are retained for audit history."})
        log_action(actor=self.request.user, company=instance.company, action="task.deleted", target=instance)
        instance.delete()


class TaskCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = task_queryset(request.user).filter(pk=pk).first()
        if not task:
            raise PermissionDenied("Task is not available.")
        serializer = CompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(TaskSerializer(transition_task(actor=request.user, task=task, status=Task.Status.COMPLETED)).data)


class TaskReassignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = task_queryset(request.user).filter(pk=pk).first()
        if not task:
            raise PermissionDenied("Task is not available.")
        serializer = ReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(TaskSerializer(reassign_task(actor=request.user, task=task, assignee=serializer.validated_data["assigned_to"])).data)


class WorkspaceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        today = timezone.localdate(now)
        followups = follow_up_queryset(request.user)
        tasks = task_queryset(request.user)
        return Response({
            "scope": "company" if request.user.role == "CEO" or request.user.is_superuser else "team" if request.user.role == "MANAGER" else "personal",
            "follow_ups": {
                "today": followups.filter(scheduled_at__date=today).count(),
                "pending": followups.filter(status__in=ACTIVE_FOLLOW_UP_STATUSES).count(),
                "completed": followups.filter(status=FollowUp.Status.COMPLETED).count(),
                "upcoming": followups.filter(status__in=ACTIVE_FOLLOW_UP_STATUSES, scheduled_at__gte=now, scheduled_at__lt=now + timedelta(days=7)).count(),
                "overdue": followups.filter(follow_up_overdue_q(now)).count(),
            },
            "tasks": {
                "assigned": tasks.filter(status__in=ACTIVE_TASK_STATUSES).count(),
                "due_today": tasks.filter(status__in=ACTIVE_TASK_STATUSES, due_date=today).count(),
                "overdue": tasks.filter(task_overdue_q(now)).count(),
                "completed": tasks.filter(status=Task.Status.COMPLETED).count(),
            },
        })


class WorkspaceUpcomingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        until = now + timedelta(days=7)
        return Response({
            "follow_ups": FollowUpSerializer(follow_up_queryset(request.user).filter(status__in=ACTIVE_FOLLOW_UP_STATUSES, scheduled_at__gte=now, scheduled_at__lt=until).order_by("scheduled_at")[:100], many=True).data,
            "tasks": TaskSerializer(task_queryset(request.user).filter(status__in=ACTIVE_TASK_STATUSES, due_date__gte=timezone.localdate(now), due_date__lte=timezone.localdate(until)).order_by("due_date", "due_time")[:100], many=True).data,
        })


class WorkspaceOverdueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        return Response({
            "follow_ups": FollowUpSerializer(follow_up_queryset(request.user).filter(follow_up_overdue_q(now)).order_by("scheduled_at")[:100], many=True).data,
            "tasks": TaskSerializer(task_queryset(request.user).filter(task_overdue_q(now)).order_by("due_date", "due_time")[:100], many=True).data,
        })


class ReminderPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ReminderPreferenceSerializer(get_reminder_preference(request.user)).data)

    def patch(self, request):
        preference = get_reminder_preference(request.user)
        serializer = ReminderPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

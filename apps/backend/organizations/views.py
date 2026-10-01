from django.shortcuts import render

# Create your views here.
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, filters
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from core.audit import log_action
from rest_framework.permissions import IsAuthenticated

from accounts.models import User

from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer, EmployeeWriteSerializer, SelfServiceProfileSerializer
from .services import deactivate_employee, delete_inactive_employee, visible_employee_profiles


class OptionalPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if "page" not in request.query_params and "page_size" not in request.query_params:
            return None
        return super().paginate_queryset(queryset, request, view)


class EmployeeListView(generics.ListAPIView):
    serializer_class = EmployeeProfileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = OptionalPageNumberPagination

    def get_queryset(self):
        queryset = visible_employee_profiles(self.request.user)
        params = self.request.query_params
        if params.get("search"):
            from django.db.models import Q
            value = params["search"]
            queryset = queryset.filter(Q(employee_code__icontains=value) | Q(user__username__icontains=value) | Q(user__email__icontains=value) | Q(user__first_name__icontains=value) | Q(user__last_name__icontains=value))
        for key, field in (("branch", "branch_id"), ("department", "department_id"), ("role", "user__role")):
            if params.get(key):
                queryset = queryset.filter(**{field: params[key]})
        for key in ("team", "designation", "employment_status"):
            if params.get(key):
                queryset = queryset.filter(**{key: params[key]})
        if params.get("is_active") in ("true", "false"):
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        ordering = params.get("ordering", "employee_code")
        return queryset.order_by(ordering if ordering.lstrip("-") in {"employee_code", "joining_date", "created_at"} else "employee_code")


class EmployeeDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeProfile.objects.select_related("user", "branch", "department", "reporting_manager__user")

    def get_queryset(self):
        return visible_employee_profiles(self.request.user)

    def get_serializer_class(self):
        return EmployeeProfileSerializer if self.request.method == "GET" else (EmployeeWriteSerializer if self.request.user.role == "CEO" else SelfServiceProfileSerializer)

    def perform_update(self, serializer):
        if self.request.user.role != "CEO" and serializer.instance.user_id != self.request.user.id:
            raise PermissionDenied("You can only update your own personal profile.")
        if serializer.instance.is_active and str(self.request.data.get("is_active", "")).lower() in {"false", "0"}:
            raise ValidationError({"is_active": "Use the employee deactivation action so active leads and follow-ups are safely reassigned."})
        profile = serializer.save()
        sensitive_fields = {"role", "branch", "department", "reporting_manager", "is_active"}
        changed = sorted(set(self.request.data).intersection(sensitive_fields))
        action = "employee.updated" if not changed else f"employee.{changed[0]}_changed"
        log_action(actor=self.request.user, company=profile.branch.company, action=action, target=profile, metadata={"changed_fields": changed})


class EmployeeCreateView(generics.CreateAPIView):
    serializer_class = EmployeeWriteSerializer

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.CEO:
            raise PermissionDenied("Only CEO users can create employees.")
        profile = serializer.save()
        log_action(actor=self.request.user, company=profile.branch.company, action="employee.created", target=profile)


class EmployeeDeactivateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = visible_employee_profiles(request.user).filter(pk=pk).first()
        if not profile:
            raise PermissionDenied("Employee is not available.")
        return Response(deactivate_employee(actor=request.user, profile=profile))


class EmployeeDeleteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not (request.user.is_superuser or request.user.role == User.Role.CEO):
            raise PermissionDenied("Only CEOs can permanently delete inactive employees.")
        profile = EmployeeProfile.objects.select_related("user", "branch__company").filter(
            pk=pk, branch__company=request.user.company, is_deleted=False
        ).first()
        if not profile:
            raise PermissionDenied("Employee is not available.")
        if profile.is_active or profile.user.is_active or profile.employment_status not in ("INACTIVE", "OFFBOARDED"):
            raise ValidationError({"detail": "Only inactive or offboarded employees can be permanently deleted."})
        delete_inactive_employee(actor=request.user, profile=profile)
        return Response(status=204)


class EmployeeScopedView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_profile(self):
        profile = visible_employee_profiles(self.request.user).filter(pk=self.kwargs["pk"]).first()
        if not profile:
            raise PermissionDenied("Employee is not available.")
        return profile


class EmployeeOverviewView(EmployeeScopedView):
    def retrieve(self, request, *args, **kwargs):
        from attendance.models import AttendanceRecord
        from hrms.models import LeaveBalance
        from leads.models import Lead
        from workspace.models import FollowUp, Task

        profile = self.get_profile()
        today = timezone.localdate()
        leads = Lead.objects.filter(company=profile.branch.company, assigned_to=profile)
        tasks = Task.objects.filter(company=profile.branch.company, assigned_to=profile)
        followups = FollowUp.objects.filter(company=profile.branch.company, assigned_to=profile)
        attendance = AttendanceRecord.objects.filter(company=profile.branch.company, employee=profile, attendance_date__year=today.year, attendance_date__month=today.month)
        attendance_days = attendance.count()
        return Response({
            "employee": EmployeeProfileSerializer(profile, context={"request": request}).data,
            "kpis": {
                "total_leads": leads.count(), "active_leads": leads.exclude(status__in=["CLOSED", "NOT_INTERESTED", "INVALID_PHONE"]).count(), "closed_leads": leads.filter(status="CLOSED").count(),
                "completed_follow_ups": followups.filter(status="COMPLETED").count(), "pending_follow_ups": followups.filter(status__in=["PENDING", "IN_PROGRESS", "POSTPONED"]).count(),
                "completed_tasks": tasks.filter(status="COMPLETED").count(), "overdue_tasks": tasks.exclude(status__in=["COMPLETED", "CANCELLED"]).filter(due_date__lt=today).count(),
                "attendance_percentage": round((attendance.filter(status__in=["PRESENT", "LATE"]).count() / attendance_days * 100) if attendance_days else 0, 1),
                "leave_balance": str(sum((balance.available_days for balance in LeaveBalance.objects.filter(employee=profile)), 0)),
            },
        })


class EmployeePerformanceView(EmployeeScopedView):
    def retrieve(self, request, *args, **kwargs):
        from .analytics import employee_performance
        return Response(employee_performance(self.get_profile()))


class EmployeeAttendanceView(EmployeeScopedView):
    def retrieve(self, request, *args, **kwargs):
        from attendance.models import AttendanceRecord
        profile = self.get_profile()
        records = AttendanceRecord.objects.filter(employee=profile, company=profile.branch.company).order_by("-attendance_date")[:31]
        from attendance.serializers import AttendanceRecordSerializer
        return Response(AttendanceRecordSerializer(records, many=True).data)


class EmployeeLeadsView(EmployeeScopedView):
    def retrieve(self, request, *args, **kwargs):
        from leads.models import Lead
        from leads.serializers import LeadSerializer
        profile = self.get_profile()
        leads = Lead.objects.select_related("assigned_to__user", "created_by").filter(company=profile.branch.company, assigned_to=profile).order_by("-updated_at")[:50]
        return Response(LeadSerializer(leads, many=True).data)


class EmployeeWorkView(EmployeeScopedView):
    def retrieve(self, request, *args, **kwargs):
        from workspace.models import FollowUp, Task
        from workspace.serializers import FollowUpSerializer, TaskSerializer
        profile = self.get_profile()
        tasks = Task.objects.select_related("assigned_to__user", "created_by", "lead").filter(company=profile.branch.company, assigned_to=profile).order_by("due_date")[:50]
        followups = FollowUp.objects.select_related("assigned_to__user", "created_by", "lead").filter(company=profile.branch.company, assigned_to=profile).order_by("scheduled_at")[:50]
        return Response({"tasks": TaskSerializer(tasks, many=True).data, "follow_ups": FollowUpSerializer(followups, many=True).data})


class EmployeeActivityView(EmployeeScopedView):
    def retrieve(self, request, *args, **kwargs):
        from core.models import AuditLog
        profile = self.get_profile()
        from hrms.models import LeaveRequest
        leave_ids = LeaveRequest.objects.filter(employee=profile).values_list("pk", flat=True)
        activities = AuditLog.objects.filter(company=profile.branch.company).filter(
            Q(target_type="organizations.EmployeeProfile", target_id=str(profile.pk)) |
            Q(target_type="hrms.LeaveRequest", target_id__in=[str(item) for item in leave_ids])
        ).select_related("actor").order_by("-created_at")[:50]
        return Response([{"id": item.pk, "action": item.action, "actor": item.actor.username if item.actor else "System", "created_at": item.created_at, "reason": item.reason} for item in activities])

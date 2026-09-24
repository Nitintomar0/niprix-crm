from django.shortcuts import render

# Create your views here.
from rest_framework import generics, filters
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from core.audit import log_action
from rest_framework.permissions import IsAuthenticated

from .models import EmployeeProfile
from .serializers import EmployeeProfileSerializer, EmployeeWriteSerializer, SelfServiceProfileSerializer


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
        user = self.request.user

        queryset = EmployeeProfile.objects.select_related("user", "branch", "department", "reporting_manager__user")
        if user.role == "CEO":
            queryset = queryset.filter(branch__company=user.company)
        elif user.role == "MANAGER" and hasattr(user, "employee_profile"):
            queryset = queryset.filter(reporting_manager=user.employee_profile)
        elif hasattr(user, "employee_profile"):
            queryset = queryset.filter(pk=user.employee_profile.pk)
        else:
            return EmployeeProfile.objects.none()
        params = self.request.query_params
        if params.get("search"):
            from django.db.models import Q
            value = params["search"]
            queryset = queryset.filter(Q(employee_code__icontains=value) | Q(user__username__icontains=value) | Q(user__email__icontains=value) | Q(user__first_name__icontains=value) | Q(user__last_name__icontains=value))
        for key, field in (("branch", "branch_id"), ("department", "department_id"), ("role", "user__role")):
            if params.get(key):
                queryset = queryset.filter(**{field: params[key]})
        if params.get("is_active") in ("true", "false"):
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        ordering = params.get("ordering", "employee_code")
        return queryset.order_by(ordering if ordering.lstrip("-") in {"employee_code", "joining_date", "created_at"} else "employee_code")


class EmployeeDetailView(generics.RetrieveUpdateAPIView):
    queryset = EmployeeProfile.objects.select_related("user", "branch", "department", "reporting_manager__user")

    def get_queryset(self):
        user = self.request.user
        if user.role == "CEO":
            return self.queryset.filter(branch__company=user.company)
        if hasattr(user, "employee_profile"):
            return self.queryset.filter(pk=user.employee_profile.pk)
        return self.queryset.none()

    def get_serializer_class(self):
        return EmployeeProfileSerializer if self.request.method == "GET" else (EmployeeWriteSerializer if self.request.user.role == "CEO" else SelfServiceProfileSerializer)

    def perform_update(self, serializer):
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

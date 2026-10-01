from django.db.models import Q
from django.http import FileResponse
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import EmployeeProfile
from organizations.services import visible_employee_profiles

from .models import EmployeeDocument, Holiday, LeaveBalance, LeaveRequest, LeaveType
from .serializers import EmployeeDocumentSerializer, HolidaySerializer, LeaveBalanceSerializer, LeaveRequestSerializer, LeaveTypeSerializer
from .services import cancel_leave_request, create_leave_request, employee_in_scope, hr_dashboard, review_leave_request


def is_admin(user): return bool(user.is_superuser or user.role == "CEO")


class LeaveTypeListView(generics.ListCreateAPIView):
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return LeaveType.objects.filter(company=self.request.user.company).order_by("name")
    def perform_create(self, serializer):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage leave types.")
        leave_type = serializer.save(company=self.request.user.company)
        from core.audit import log_action
        log_action(actor=self.request.user, company=leave_type.company, action="leave_type.created", target=leave_type)


class LeaveTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return LeaveType.objects.filter(company=self.request.user.company)
    def perform_update(self, serializer):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage leave types.")
        leave_type = serializer.save()
        from core.audit import log_action
        log_action(actor=self.request.user, company=leave_type.company, action="leave_type.updated", target=leave_type)
    def perform_destroy(self, instance):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage leave types.")
        from core.audit import log_action
        log_action(actor=self.request.user, company=instance.company, action="leave_type.deleted", target=instance)
        instance.delete()


class LeaveBalanceListView(generics.ListAPIView):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return LeaveBalance.objects.select_related("employee__user", "leave_type").filter(employee__in=visible_employee_profiles(self.request.user))


class LeaveBalanceDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return LeaveBalance.objects.select_related("employee__user", "leave_type").filter(employee__in=visible_employee_profiles(self.request.user))
    def perform_update(self, serializer):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can update leave allocations.")
        balance = serializer.save()
        from core.audit import log_action
        log_action(actor=self.request.user, company=balance.employee.branch.company, action="leave.balance_updated", target=balance)


class LeaveRequestListCreateView(generics.ListCreateAPIView):
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return LeaveRequest.objects.select_related("employee__user", "leave_type", "reviewed_by").filter(employee__in=visible_employee_profiles(self.request.user))
    def perform_create(self, serializer):
        employee = serializer.validated_data.get("employee") or self.request.user.employee_profile
        request = create_leave_request(actor=self.request.user, employee=employee, leave_type=serializer.validated_data["leave_type"], start_date=serializer.validated_data["start_date"], end_date=serializer.validated_data["end_date"], reason=serializer.validated_data["reason"])
        serializer.instance = request


class LeaveRequestActionView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk, action):
        leave_request = LeaveRequest.objects.filter(pk=pk, employee__in=visible_employee_profiles(request.user)).first()
        if not leave_request: raise PermissionDenied("Leave request is not available.")
        if action == "cancel": result = cancel_leave_request(actor=request.user, request=leave_request)
        else: result = review_leave_request(actor=request.user, request=leave_request, approved=action == "approve", comment=request.data.get("comment", ""))
        return Response(LeaveRequestSerializer(result).data)


class HolidayListCreateView(generics.ListCreateAPIView):
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        queryset = Holiday.objects.filter(company=self.request.user.company, is_active=True)
        if is_admin(self.request.user):
            return queryset.order_by("holiday_date")
        branch_ids = visible_employee_profiles(self.request.user).values_list("branch_id", flat=True)
        return queryset.filter(Q(branch__isnull=True) | Q(branch_id__in=branch_ids)).order_by("holiday_date")
    def perform_create(self, serializer):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage holidays.")
        holiday = serializer.save(company=self.request.user.company)
        from core.audit import log_action
        log_action(actor=self.request.user, company=holiday.company, action="holiday.created", target=holiday)


class HolidayDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = HolidaySerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return Holiday.objects.filter(company=self.request.user.company)
    def perform_update(self, serializer):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage holidays.")
        holiday = serializer.save()
        from core.audit import log_action
        log_action(actor=self.request.user, company=holiday.company, action="holiday.updated", target=holiday)
    def perform_destroy(self, instance):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage holidays.")
        from core.audit import log_action
        log_action(actor=self.request.user, company=instance.company, action="holiday.deleted", target=instance)
        instance.delete()


class EmployeeDocumentListCreateView(generics.ListCreateAPIView):
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return EmployeeDocument.objects.filter(employee_id=self.kwargs["employee_id"], employee__in=visible_employee_profiles(self.request.user))
    def perform_create(self, serializer):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can upload employee documents.")
        employee = visible_employee_profiles(self.request.user).filter(pk=self.kwargs["employee_id"]).first()
        if not employee: raise PermissionDenied("Employee is not available.")
        document = serializer.save(employee=employee, uploaded_by=self.request.user)
        from core.audit import log_action
        log_action(actor=self.request.user, company=employee.branch.company, action="employee_document.uploaded", target=document)


class EmployeeDocumentOverviewListView(generics.ListAPIView):
    serializer_class = EmployeeDocumentSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        if not is_admin(self.request.user): raise PermissionDenied("Only CEO users can manage employee documents.")
        return EmployeeDocument.objects.select_related("employee__user").filter(employee__in=visible_employee_profiles(self.request.user)).order_by("-created_at")


class HRDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request): return Response(hr_dashboard(actor=request.user))


class EmployeeDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        document = EmployeeDocument.objects.filter(pk=pk, employee__in=visible_employee_profiles(request.user)).first()
        if not document: raise PermissionDenied("Document is not available.")
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.title)


class EmployeeDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def delete(self, request, pk):
        if not is_admin(request.user):
            raise PermissionDenied("Only CEO users can delete employee documents.")
        document = EmployeeDocument.objects.filter(pk=pk, employee__in=visible_employee_profiles(request.user)).first()
        if not document:
            raise PermissionDenied("Document is not available.")
        from core.audit import log_action
        log_action(actor=request.user, company=document.employee.branch.company, action="employee_document.deleted", target=document)
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import log_action
from organizations.views import OptionalPageNumberPagination
from .models import AttendanceCorrection, AttendanceRecord
from .serializers import AttendanceCorrectionSerializer, AttendanceRecordSerializer
from .services import check_in, check_out, get_policy, recalculate_record, validate_profile_tenant


def profile_for(user):
    if not hasattr(user, "employee_profile"):
        raise PermissionDenied("An employee profile is required.")
    return user.employee_profile


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        return Response(AttendanceRecordSerializer(check_in(profile_for(request.user))).data, status=201)


class CheckOutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        return Response(AttendanceRecordSerializer(check_out(profile_for(request.user))).data)


class AttendanceListView(generics.ListAPIView):
    serializer_class = AttendanceRecordSerializer
    pagination_class = OptionalPageNumberPagination

    def initial(self, request, *args, **kwargs):
        for name, maximum in (("page", None), ("page_size", 100)):
            value = request.query_params.get(name)
            if value is None:
                continue
            try:
                value = int(value)
            except ValueError:
                raise ValidationError({name: "Must be a positive integer."})
            if value <= 0 or (maximum is not None and value > maximum):
                message = "Must be a positive integer." if maximum is None else f"Must be between 1 and {maximum}."
                raise ValidationError({name: message})
        return super().initial(request, *args, **kwargs)

    def get_queryset(self):
        user, params = self.request.user, self.request.query_params
        queryset = AttendanceRecord.objects.select_related("employee__user", "branch")
        if user.role == "CEO" or user.is_superuser:
            queryset = queryset.filter(company=user.company)
        elif user.role == "MANAGER" and hasattr(user, "employee_profile"):
            queryset = queryset.filter(
                company=user.company,
                employee__reporting_manager=user.employee_profile,
            )
        elif hasattr(user, "employee_profile"):
            queryset = queryset.filter(employee=user.employee_profile)
        else:
            return queryset.none()
        for key, field in (("employee", "employee_id"), ("branch", "branch_id"), ("department", "employee__department_id")):
            if params.get(key):
                try:
                    value = int(params[key])
                except ValueError:
                    raise ValidationError({key: "Must be a positive integer."})
                if value <= 0:
                    raise ValidationError({key: "Must be a positive integer."})
                queryset = queryset.filter(**{field: value})
        date_from = self._date_param("date_from")
        date_to = self._date_param("date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_to": "Must be on or after date_from."})
        if date_from: queryset = queryset.filter(attendance_date__gte=date_from)
        if date_to: queryset = queryset.filter(attendance_date__lte=date_to)
        return queryset.order_by("-attendance_date", "-check_in_at")

    def _date_param(self, name):
        value = self.request.query_params.get(name)
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValidationError({name: "Use ISO date format YYYY-MM-DD."})


class CurrentAttendanceView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        profile = profile_for(request.user)
        record = AttendanceRecord.objects.filter(
            employee=profile,
            company=request.user.company,
            attendance_date=timezone.localdate(),
        ).first()
        return Response(AttendanceRecordSerializer(record).data if record else {"status": "NOT_CHECKED_IN"})


class AttendanceCorrectionView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        if request.user.role != "CEO" and not request.user.is_superuser:
            raise PermissionDenied("Only CEO users can correct attendance.")
        record = AttendanceRecord.objects.select_related("employee__branch").filter(pk=pk, company=request.user.company).first()
        if not record: raise PermissionDenied("Attendance record is not available.")
        validate_profile_tenant(record.employee)
        if record.branch_id != record.employee.branch_id or record.company_id != record.employee.branch.company_id:
            raise PermissionDenied("Attendance record tenant context is invalid.")
        serializer = AttendanceCorrectionSerializer(data=request.data, context={"record": record})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            record = AttendanceRecord.objects.select_for_update().get(pk=record.pk, company=request.user.company)
            old = {"check_in_at": record.check_in_at.isoformat() if record.check_in_at else None, "check_out_at": record.check_out_at.isoformat() if record.check_out_at else None}
            changes = serializer.validated_data
            for field in ("check_in_at", "check_out_at"):
                if field in changes: setattr(record, field, changes[field])
            recalculate_record(record, get_policy(record.company))
            record.corrected_at = timezone.now(); record.save()
            updated = {"check_in_at": record.check_in_at.isoformat() if record.check_in_at else None, "check_out_at": record.check_out_at.isoformat() if record.check_out_at else None}
            AttendanceCorrection.objects.create(record=record, corrected_by=request.user, reason=changes["reason"], original_values=old, updated_values=updated)
            log_action(actor=request.user, company=record.company, action="attendance.corrected", target=record, reason=changes["reason"])
        return Response(AttendanceRecordSerializer(record).data)

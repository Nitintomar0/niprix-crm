from django.utils import timezone
from rest_framework import serializers
from .models import AttendanceRecord


class AttendanceRecordSerializer(serializers.ModelSerializer):
    employee_code = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()

    def get_employee_code(self, obj):
        return obj.employee.employee_code if obj.employee_id else "CEO"

    def get_employee_name(self, obj):
        return obj.employee.user.username if obj.employee_id else obj.attendance_user.username

    class Meta:
        model = AttendanceRecord
        fields = ["id", "employee", "attendance_user", "employee_code", "employee_name", "branch", "attendance_date", "check_in_at", "check_out_at", "status", "late_minutes", "total_work_minutes", "early_checkout", "corrected_at"]
        read_only_fields = fields


class AttendanceCorrectionSerializer(serializers.Serializer):
    check_in_at = serializers.DateTimeField(required=False)
    check_out_at = serializers.DateTimeField(required=False, allow_null=True)
    reason = serializers.CharField(min_length=3, max_length=1000)

    def validate(self, attrs):
        if not any(key in attrs for key in ("check_in_at", "check_out_at")):
            raise serializers.ValidationError("Provide at least one timestamp to correct.")
        reason = attrs.get("reason", "").strip()
        if len(reason) < 3:
            raise serializers.ValidationError({"reason": "Provide a meaningful correction reason."})
        attrs["reason"] = reason
        record = self.context["record"]
        check_in_at = attrs.get("check_in_at", record.check_in_at)
        check_out_at = attrs.get("check_out_at", record.check_out_at)
        for field, value in (("check_in_at", attrs.get("check_in_at")), ("check_out_at", attrs.get("check_out_at"))):
            if value and value > timezone.now():
                raise serializers.ValidationError({field: "Future timestamps are not allowed."})
        if check_out_at and not check_in_at:
            raise serializers.ValidationError({"check_in_at": "A check-in is required before check-out."})
        if check_in_at and check_out_at and check_out_at < check_in_at:
            raise serializers.ValidationError({"check_out_at": "Check-out cannot be before check-in."})
        if "check_in_at" in attrs and check_in_at and check_in_at.date() != record.attendance_date:
            raise serializers.ValidationError({"check_in_at": "Check-in must be on the attendance date."})
        if "check_out_at" in attrs and check_out_at and check_out_at.date() != record.attendance_date:
            raise serializers.ValidationError({"check_out_at": "Check-out must be on the attendance date."})
        return attrs

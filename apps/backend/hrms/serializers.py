from rest_framework import serializers

from organizations.models import Branch, EmployeeProfile

from .models import EmployeeDocument, Holiday, LeaveBalance, LeaveRequest, LeaveType


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ("id", "name", "description", "annual_allocation", "allows_negative_balance", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    employee_name = serializers.CharField(source="employee.user.username", read_only=True)
    allocated_days = serializers.DecimalField(max_digits=6, decimal_places=1, required=False, write_only=True)
    remaining_days = serializers.DecimalField(source="available_days", max_digits=6, decimal_places=1, read_only=True)
    class Meta:
        model = LeaveBalance
        fields = ("id", "employee", "employee_name", "employee_code", "leave_type", "leave_type_name", "allocated_days", "remaining_days", "available_days", "used_days", "updated_at")
        read_only_fields = ("id", "employee", "employee_name", "employee_code", "leave_type", "leave_type_name", "remaining_days", "available_days", "used_days", "updated_at")

    def update(self, instance, validated_data):
        allocated = validated_data.pop("allocated_days", None)
        if allocated is not None:
            if allocated < instance.used_days:
                raise serializers.ValidationError({"allocated_days": "Allocation cannot be lower than leave already used."})
            instance.available_days = allocated - instance.used_days
        instance.save(update_fields=["available_days", "updated_at"])
        return instance


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=EmployeeProfile.objects.all(), required=False)
    employee_name = serializers.CharField(source="employee.user.username", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.username", read_only=True)
    class Meta:
        model = LeaveRequest
        fields = ("id", "employee", "employee_name", "leave_type", "leave_type_name", "start_date", "end_date", "number_of_days", "reason", "status", "reviewed_by", "reviewed_by_name", "reviewed_at", "review_comment", "created_at")
        read_only_fields = ("id", "number_of_days", "status", "reviewed_by", "reviewed_by_name", "reviewed_at", "review_comment", "created_at")


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ("id", "branch", "name", "holiday_date", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_branch(self, branch):
        if branch and branch.company_id != self.context["request"].user.company_id:
            raise serializers.ValidationError("Branch must belong to your company.")
        return branch


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.user.username", read_only=True)
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    class Meta:
        model = EmployeeDocument
        fields = ("id", "employee", "employee_name", "employee_code", "kind", "title", "file", "created_at")
        read_only_fields = ("id", "employee", "created_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("file", None)
        return data

    def validate_file(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Document must not exceed 10 MB.")
        extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
        if extension not in {"pdf", "jpg", "jpeg", "png", "doc", "docx"}:
            raise serializers.ValidationError("Document type is not allowed.")
        return value

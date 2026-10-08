from django.utils import timezone
from rest_framework import serializers

from organizations.models import EmployeeProfile

from .models import FollowUp, FollowUpActivity, ReminderPreference, Task
from .services import FOLLOW_UP_WORKFLOW_STATUSES, create_follow_up, create_task, update_follow_up, update_task


class EmployeeReferenceSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeProfile
        fields = ("id", "employee_code", "username", "display_name")

    def get_display_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class FollowUpSerializer(serializers.ModelSerializer):
    assigned_to_detail = EmployeeReferenceSerializer(source="assigned_to", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    lead_name = serializers.CharField(source="lead.name", read_only=True)
    lead_phone = serializers.CharField(source="lead.phone", read_only=True)
    activity_note = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)

    class Meta:
        model = FollowUp
        fields = (
            "id", "company", "branch", "assigned_to", "assigned_to_detail", "created_by", "created_by_name", "lead", "lead_name", "lead_phone",
            "follow_up_type", "title", "description", "scheduled_at", "status", "priority", "completed_at",
            "activity_note", "created_at", "updated_at",
        )
        read_only_fields = ("id", "company", "branch", "created_by", "completed_at", "created_at", "updated_at")

    def validate_assigned_to(self, value):
        return value

    def validate_scheduled_at(self, value):
        if value < timezone.now() and self.instance is None:
            raise serializers.ValidationError("Scheduled time must be in the future when creating a follow-up.")
        return value

    def validate_status(self, value):
        if value not in FOLLOW_UP_WORKFLOW_STATUSES:
            raise serializers.ValidationError("Use a follow-up workflow status (pending, in progress, postponed, completed, cancelled, or missed).")
        return value

    def create(self, validated_data):
        return create_follow_up(actor=self.context["request"].user, data=validated_data)

    def update(self, instance, validated_data):
        return update_follow_up(actor=self.context["request"].user, follow_up=instance, data=validated_data)


class FollowUpActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source="performed_by.username", read_only=True)

    class Meta:
        model = FollowUpActivity
        fields = "__all__"
        read_only_fields = (
            "id", "company", "follow_up", "performed_by", "previous_status", "new_status",
            "previous_scheduled_at", "new_scheduled_at", "note", "activity_type", "created_at",
        )


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_detail = EmployeeReferenceSerializer(source="assigned_to", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Task
        fields = (
            "id", "company", "branch", "title", "description", "assigned_to", "assigned_to_detail", "created_by", "lead",
            "created_by_name", "related_follow_up", "due_date", "due_time", "priority", "status", "completed_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "company", "branch", "created_by", "completed_at", "created_at", "updated_at")

    def validate_due_date(self, value):
        if value < timezone.localdate() and self.instance is None:
            raise serializers.ValidationError("Due date cannot be in the past when creating a task.")
        return value

    def create(self, validated_data):
        return create_task(actor=self.context["request"].user, data=validated_data)

    def update(self, instance, validated_data):
        return update_task(actor=self.context["request"].user, task=instance, data=validated_data)


class ReminderPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderPreference
        fields = ("upcoming_follow_up_reminders_enabled", "overdue_follow_up_reminders_enabled", "overdue_task_reminders_enabled", "reminder_lead_minutes", "daily_summary_enabled", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate_reminder_lead_minutes(self, value):
        if not 0 <= value <= 1440:
            raise serializers.ValidationError("Reminder lead time must be between 0 and 1440 minutes.")
        return value


class CompleteSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class PostponeSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("Postponed follow-up time must be in the future.")
        return value


class ReassignSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=EmployeeProfile.objects.all())
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

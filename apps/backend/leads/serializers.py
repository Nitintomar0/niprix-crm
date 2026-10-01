from rest_framework import serializers

from organizations.models import Branch, EmployeeProfile
from workspace.serializers import EmployeeReferenceSerializer

from .models import Lead, LeadActivity, LeadAssignment, LeadSource
from .services import create_or_enrich_lead, update_lead


class LeadSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadSource
        fields = (
            "id", "source", "external_lead_id", "external_contact_id",
            "external_conversation_id", "source_details", "metadata", "received_at", "created_at",
        )
        read_only_fields = fields


class LeadAssignmentSerializer(serializers.ModelSerializer):
    assigned_to_detail = EmployeeReferenceSerializer(source="assigned_to", read_only=True)
    previous_assignee_detail = EmployeeReferenceSerializer(source="previous_assignee", read_only=True)
    assigned_by_name = serializers.CharField(source="assigned_by.username", read_only=True)

    class Meta:
        model = LeadAssignment
        fields = (
            "id", "previous_assignee", "previous_assignee_detail", "assigned_to",
            "assigned_to_detail", "assigned_by", "assigned_by_name", "assignment_type",
            "reason", "created_at",
        )
        read_only_fields = fields


class LeadActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source="performed_by.username", read_only=True)

    class Meta:
        model = LeadActivity
        fields = (
            "id", "activity_type", "field_name", "old_value", "new_value", "note",
            "metadata", "performed_by", "performed_by_name", "created_at",
        )
        read_only_fields = fields


class LeadSerializer(serializers.ModelSerializer):
    assigned_to_detail = EmployeeReferenceSerializer(source="assigned_to", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    source_metadata = serializers.JSONField(write_only=True, required=False)
    external_lead_id = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    external_contact_id = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    external_conversation_id = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    received_at = serializers.DateTimeField(write_only=True, required=False)
    assignment_note = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=EmployeeProfile.objects.all(), required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)

    class Meta:
        model = Lead
        fields = (
            "id", "company", "branch", "assigned_to", "assigned_to_detail", "created_by", "created_by_name",
            "name", "phone", "alternate_phone", "email", "property_type", "preferred_location",
            "budget_minimum", "budget_maximum", "bhk", "purpose", "requirement_notes", "source",
            "source_details", "status", "temperature", "created_at", "updated_at",
            "source_metadata", "external_lead_id", "external_contact_id", "external_conversation_id",
            "received_at", "assignment_note",
        )
        read_only_fields = (
            "id", "company", "created_by", "assigned_to_detail", "created_by_name", "created_at", "updated_at",
        )
        extra_kwargs = {"phone": {"required": True}}

    def validate(self, attrs):
        if self.instance is None and not attrs.get("phone", "").strip():
            raise serializers.ValidationError({"phone": "Phone is required when creating a manual lead."})
        low, high = attrs.get("budget_minimum"), attrs.get("budget_maximum")
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"budget_maximum": "Must be greater than or equal to budget minimum."})
        return attrs

    def create(self, validated_data):
        return create_or_enrich_lead(actor=self.context["request"].user, data=validated_data).lead

    def update(self, instance, validated_data):
        for field in ("source_metadata", "external_lead_id", "external_contact_id", "external_conversation_id", "received_at"):
            if field in validated_data:
                raise serializers.ValidationError({field: "Source fields are only accepted when creating or ingesting a lead."})
        return update_lead(actor=self.context["request"].user, lead=instance, data=validated_data)


class LeadStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Lead.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class LeadTemperatureSerializer(serializers.Serializer):
    temperature = serializers.ChoiceField(choices=Lead.Temperature.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class LeadReassignSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=EmployeeProfile.objects.all())
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class LeadMoveToFollowUpSerializer(serializers.Serializer):
    """The small, explicit payload needed to turn a lead into scheduled work."""

    title = serializers.CharField(required=False, allow_blank=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    scheduled_at = serializers.DateTimeField()
    follow_up_type = serializers.ChoiceField(choices=(
        "CALL", "WHATSAPP", "EMAIL", "SITE_VISIT", "MEETING", "OTHER",
    ), required=False, default="CALL")
    priority = serializers.ChoiceField(choices=("LOW", "MEDIUM", "HIGH", "URGENT"), required=False, default="MEDIUM")

    def validate_scheduled_at(self, value):
        from django.utils import timezone
        if value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value


class LeadNoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=4000)

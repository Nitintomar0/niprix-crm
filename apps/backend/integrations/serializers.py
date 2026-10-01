from rest_framework import serializers

from organizations.models import Branch

from .models import IntegrationConfiguration, IntegrationEvent


class IntegrationConfigurationSerializer(serializers.ModelSerializer):
    secret_configured = serializers.SerializerMethodField()
    failed_event_count = serializers.SerializerMethodField()

    class Meta:
        model = IntegrationConfiguration
        fields = (
            "id", "provider", "branch", "external_account_id", "is_enabled", "status",
            "secret_configured", "last_success_at", "last_failure_at", "last_failure_message",
            "failed_event_count", "created_at", "updated_at",
        )
        read_only_fields = ("id", "status", "secret_configured", "last_success_at", "last_failure_at", "last_failure_message", "failed_event_count", "created_at", "updated_at")

    def get_secret_configured(self, obj):
        from .services import _secret_for
        return bool(_secret_for(obj.provider))

    def get_failed_event_count(self, obj):
        return obj.events.filter(status=IntegrationEvent.Status.FAILED).count()

    def validate_branch(self, branch):
        user = self.context["request"].user
        if branch.company_id != user.company_id or not branch.is_active:
            raise serializers.ValidationError("Branch must be active and belong to your company.")
        return branch

    def create(self, validated_data):
        return IntegrationConfiguration.objects.create(company=self.context["request"].user.company, **validated_data)


class IntegrationEventSerializer(serializers.ModelSerializer):
    lead_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = IntegrationEvent
        # Raw payload and idempotency keys are deliberately not client-visible.
        fields = ("id", "provider", "event_type", "external_event_id", "external_lead_id", "lead_id", "status", "received_at", "processed_at", "retry_count", "error_message")
        read_only_fields = fields

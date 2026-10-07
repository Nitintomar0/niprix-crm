from rest_framework import serializers

from leads.models import Lead
from leads.services import normalize_phone

from .models import RawLead


RAW_FIELDS = (
    "name", "phone", "alternate_phone", "email", "property_type", "preferred_location",
    "budget_minimum", "budget_maximum", "bhk", "purpose", "requirement_notes", "source", "source_details",
)


class RawLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawLead
        fields = ("id", "company", "created_by", *RAW_FIELDS, "created_at", "updated_at")
        read_only_fields = ("id", "company", "created_by", "created_at", "updated_at")

    def validate_phone(self, value):
        if not normalize_phone(value):
            raise serializers.ValidationError("Enter a valid phone number.")
        return value.strip()

    def validate(self, attrs):
        low = attrs.get("budget_minimum", getattr(self.instance, "budget_minimum", None))
        high = attrs.get("budget_maximum", getattr(self.instance, "budget_maximum", None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"budget_maximum": "Must be greater than or equal to budget minimum."})
        return attrs


class PreviewRowsSerializer(serializers.Serializer):
    rows = serializers.ListField(child=serializers.DictField(), allow_empty=False, max_length=5000)


class DistributionRequestSerializer(serializers.Serializer):
    raw_lead_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=False, max_length=1000)
    quantity = serializers.IntegerField(min_value=1, required=False)
    employee_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=100)
    mode = serializers.ChoiceField(choices=("EQUAL", "SPECIFIC", "CUSTOM"))
    allocations = serializers.DictField(child=serializers.IntegerField(min_value=0), required=False)

    def validate(self, attrs):
        if bool(attrs.get("raw_lead_ids")) == bool(attrs.get("quantity")):
            raise serializers.ValidationError("Choose selected raw leads or a quantity, but not both.")
        if attrs["mode"] == "SPECIFIC" and len(attrs["employee_ids"]) != 1:
            raise serializers.ValidationError({"employee_ids": "Specific employee distribution needs exactly one employee."})
        if attrs["mode"] == "CUSTOM" and not attrs.get("allocations"):
            raise serializers.ValidationError({"allocations": "Provide an allocation for each selected employee."})
        return attrs

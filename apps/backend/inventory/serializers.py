from rest_framework import serializers

from .models import InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = ("id", "project", "unit_number", "property_type", "size_sqft", "floor", "basic_price", "landing", "status", "booking_date", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if not request or not (request.user.is_superuser or request.user.role == "CEO"):
            fields.pop("landing", None)
        return fields


class InventoryBulkCreateSerializer(serializers.Serializer):
    items = InventoryItemSerializer(many=True, allow_empty=False)

    def validate_items(self, items):
        seen = set()
        for index, item in enumerate(items):
            key = (item["project"].strip().casefold(), item["unit_number"].strip().casefold())
            if key in seen:
                raise serializers.ValidationError({index: {"unit_number": "Duplicate project and unit in this submission."}})
            seen.add(key)
        return items

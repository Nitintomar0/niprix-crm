from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import CustomerLedger, IssuedReceipt, Payment


def received_total(customer: CustomerLedger) -> Decimal:
    return customer.payments.filter(status=Payment.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


class ReceiptSerializer(serializers.ModelSerializer):
    receipt_pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = IssuedReceipt
        fields = (
            "id", "serial_number", "receipt_date", "amount_received", "total_amount", "balance_amount",
            "payment_method", "reference_number", "drawn_on", "status", "issued_at", "cancelled_at",
            "cancellation_reason", "receipt_pdf_url",
        )

    def get_receipt_pdf_url(self, instance):
        return f"/api/accounts/receipts/{instance.pk}/pdf/"


class PaymentSerializer(serializers.ModelSerializer):
    receipt = ReceiptSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id", "amount", "payment_method", "reference_number", "drawn_on", "paid_on", "status",
            "reversed_at", "reversal_reason", "created_at", "receipt",
        )


class CustomerLedgerSerializer(serializers.ModelSerializer):
    customer_id = serializers.CharField(source="customer_code", read_only=True)
    total_received = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True, read_only=True)
    receipts = ReceiptSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerLedger
        fields = (
            "id", "customer_id", "name", "mobile", "residential_address", "project", "plot_number", "plot_size",
            "total_agreed_amount", "total_received", "outstanding_balance", "due_date", "status", "payments", "receipts",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "customer_id", "total_received", "outstanding_balance", "payments", "receipts", "created_at", "updated_at")

    def get_total_received(self, instance):
        return f"{received_total(instance):.2f}"

    def get_outstanding_balance(self, instance):
        return f"{instance.total_agreed_amount - received_total(instance):.2f}"

    def validate_total_agreed_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total agreed amount must be greater than zero.")
        return value

    def validate(self, attrs):
        if self.instance and "total_agreed_amount" in attrs:
            current_received = received_total(self.instance)
            if attrs["total_agreed_amount"] < current_received:
                raise serializers.ValidationError({"total_agreed_amount": "Total amount cannot be lower than successfully received payments."})
        return attrs


class IssueReceiptSerializer(serializers.Serializer):
    serial_number = serializers.CharField(max_length=64)
    receipt_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)
    reference_number = serializers.CharField(max_length=120, required=False, allow_blank=True)
    drawn_on = serializers.CharField(max_length=160, required=False, allow_blank=True)
    idempotency_key = serializers.CharField(max_length=128)

    def validate_serial_number(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Receipt serial number is required.")
        return value

    def validate_idempotency_key(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A submission identifier is required.")
        return value


class CancellationSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("A cancellation reason is required.")
        return value.strip()

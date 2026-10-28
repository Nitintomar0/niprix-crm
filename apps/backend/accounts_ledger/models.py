from django.conf import settings
from django.db import models


class CustomerLedger(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"
        ON_HOLD = "ON_HOLD", "On hold"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="customer_ledgers")
    name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=32)
    residential_address = models.TextField(blank=True)
    project = models.CharField(max_length=255, blank=True)
    plot_number = models.CharField(max_length=100, blank=True)
    plot_size = models.CharField(max_length=100, blank=True)
    total_agreed_amount = models.DecimalField(max_digits=14, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_customer_ledgers")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="updated_customer_ledgers")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["company", "status", "updated_at"]),
            models.Index(fields=["company", "name", "mobile"]),
        ]

    @property
    def customer_code(self):
        return f"CUS-{self.pk:06d}" if self.pk else ""

    def __str__(self):
        return f"{self.customer_code} — {self.name}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        CHEQUE = "CHEQUE", "Cheque"
        DRAFT = "DRAFT", "Draft"
        TRANSFER = "TRANSFER", "Bank transfer"
        UPI = "UPI", "UPI"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Successful"
        REVERSED = "REVERSED", "Reversed"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="ledger_payments")
    customer = models.ForeignKey(CustomerLedger, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=16, choices=Method.choices)
    reference_number = models.CharField(max_length=120, blank=True)
    drawn_on = models.CharField(max_length=160, blank=True)
    paid_on = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUCCESS)
    idempotency_key = models.CharField(max_length=128)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_ledger_payments")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_ledger_payments")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["paid_on", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "idempotency_key"], name="unique_ledger_payment_request_per_company"),
        ]
        indexes = [models.Index(fields=["company", "customer", "status", "paid_on"])]


class IssuedReceipt(models.Model):
    class Status(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        CANCELLED = "CANCELLED", "Cancelled"

    company = models.ForeignKey("organizations.Company", on_delete=models.PROTECT, related_name="issued_receipts")
    customer = models.ForeignKey(CustomerLedger, on_delete=models.PROTECT, related_name="receipts")
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="receipt")
    serial_number = models.CharField(max_length=64)
    receipt_date = models.DateField()
    amount_received = models.DecimalField(max_digits=14, decimal_places=2)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2)
    balance_amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=16, choices=Payment.Method.choices)
    reference_number = models.CharField(max_length=120, blank=True)
    drawn_on = models.CharField(max_length=160, blank=True)
    snapshot = models.JSONField(default=dict)
    template_version = models.CharField(max_length=32, default="paramshiv-original-v1")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ISSUED)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="cancelled_ledger_receipts")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="issued_ledger_receipts")
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["company", "serial_number"], name="unique_receipt_serial_per_company")]
        indexes = [models.Index(fields=["company", "customer", "receipt_date"])]

    def __str__(self):
        return f"{self.serial_number} — {self.customer.name}"

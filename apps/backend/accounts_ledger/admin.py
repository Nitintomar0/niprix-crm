from django.contrib import admin

from .models import CustomerLedger, IssuedReceipt, Payment


@admin.register(CustomerLedger)
class CustomerLedgerAdmin(admin.ModelAdmin):
    list_display = ("customer_code", "name", "mobile", "project", "plot_number", "total_agreed_amount", "status", "company")
    list_filter = ("company", "status")
    search_fields = ("name", "mobile", "project", "plot_number")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "amount", "payment_method", "paid_on", "status", "company")
    list_filter = ("company", "status", "payment_method")
    search_fields = ("customer__name", "reference_number")


@admin.register(IssuedReceipt)
class IssuedReceiptAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "customer", "amount_received", "receipt_date", "status", "company")
    list_filter = ("company", "status")
    search_fields = ("serial_number", "customer__name")

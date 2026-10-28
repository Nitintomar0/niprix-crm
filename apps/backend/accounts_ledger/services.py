from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from core.audit import log_action

from .models import CustomerLedger, IssuedReceipt, Payment


def _received_total(customer: CustomerLedger) -> Decimal:
    return customer.payments.filter(status=Payment.Status.SUCCESS).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")


def issue_receipt(*, customer_id: int, company_id: int, actor, data: dict) -> IssuedReceipt:
    """Atomically records one payment and one immutable receipt snapshot.

    The row lock serializes payments for a customer. The database receipt serial
    constraint remains the final guard for cross-request and multi-process races.
    """
    try:
        with transaction.atomic():
            customer = CustomerLedger.objects.select_for_update().get(pk=customer_id, company_id=company_id)
            existing = Payment.objects.filter(company_id=company_id, idempotency_key=data["idempotency_key"]).select_related("receipt").first()
            if existing:
                if existing.customer_id != customer.pk:
                    raise ValidationError({"idempotency_key": "This submission identifier was already used for another customer."})
                return existing.receipt

            already_received = _received_total(customer)
            outstanding = customer.total_agreed_amount - already_received
            amount = data["amount"]
            if amount > outstanding:
                raise ValidationError({"amount": f"Payment exceeds the outstanding balance of {outstanding:.2f}."})
            if IssuedReceipt.objects.filter(company_id=company_id, serial_number=data["serial_number"]).exists():
                raise ValidationError({"serial_number": "This receipt serial number has already been issued for this company."})

            payment = Payment.objects.create(
                company_id=company_id, customer=customer, amount=amount,
                payment_method=data["payment_method"], reference_number=data.get("reference_number", ""),
                drawn_on=data.get("drawn_on", ""), paid_on=data["receipt_date"],
                idempotency_key=data["idempotency_key"], created_by=actor,
            )
            balance = outstanding - amount
            snapshot = {
                "customer_name": customer.name, "mobile": customer.mobile,
                "residential_address": customer.residential_address, "project": customer.project,
                "plot_number": customer.plot_number, "plot_size": customer.plot_size,
                "due_date": customer.due_date.isoformat() if customer.due_date else "",
                "company_name": customer.company.name,
            }
            receipt = IssuedReceipt.objects.create(
                company_id=company_id, customer=customer, payment=payment, serial_number=data["serial_number"],
                receipt_date=data["receipt_date"], amount_received=amount, total_amount=customer.total_agreed_amount,
                balance_amount=balance, payment_method=payment.payment_method, reference_number=payment.reference_number,
                drawn_on=payment.drawn_on, snapshot=snapshot, issued_by=actor,
            )
            log_action(actor=actor, company=customer.company, action="accounts.receipt_issued", target=receipt, metadata={"customer_id": customer.pk, "payment_id": payment.pk, "serial_number": receipt.serial_number, "amount": str(amount)})
            return receipt
    except IntegrityError:
        # The unique serial constraint protects concurrent issuance after the
        # application-level preflight above.
        raise ValidationError({"serial_number": "This receipt serial number has already been issued for this company."})


def cancel_receipt(*, receipt: IssuedReceipt, actor, reason: str) -> IssuedReceipt:
    with transaction.atomic():
        receipt = IssuedReceipt.objects.select_for_update().select_related("payment", "company").get(pk=receipt.pk)
        if receipt.status == IssuedReceipt.Status.CANCELLED:
            raise ValidationError({"detail": "This receipt has already been cancelled."})
        now = timezone.now()
        receipt.status = IssuedReceipt.Status.CANCELLED
        receipt.cancelled_at = now
        receipt.cancelled_by = actor
        receipt.cancellation_reason = reason
        receipt.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason"])
        receipt.payment.status = Payment.Status.REVERSED
        receipt.payment.reversed_at = now
        receipt.payment.reversed_by = actor
        receipt.payment.reversal_reason = reason
        receipt.payment.save(update_fields=["status", "reversed_at", "reversed_by", "reversal_reason"])
        log_action(actor=actor, company=receipt.company, action="accounts.receipt_cancelled", target=receipt, reason=reason, metadata={"payment_id": receipt.payment_id, "serial_number": receipt.serial_number})
        return receipt

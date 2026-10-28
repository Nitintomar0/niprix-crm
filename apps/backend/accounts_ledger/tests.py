from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Company

from .models import CustomerLedger, IssuedReceipt, Payment
from .pdf import PAGE_SIZE


class AccountsLedgerAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Paramshiv Urban Real Estate")
        self.other_company = Company.objects.create(name="Other Realty")
        self.ceo = User.objects.create_user(username="accounts-ceo", password="TestPassword123!", role=User.Role.CEO, company=self.company)
        self.employee = User.objects.create_user(username="accounts-employee", password="TestPassword123!", role=User.Role.EMPLOYEE, company=self.company)
        self.other_ceo = User.objects.create_user(username="other-ceo", password="TestPassword123!", role=User.Role.CEO, company=self.other_company)
        self.super_admin = User.objects.create_superuser(username="accounts-super-admin", password="TestPassword123!", email="super@example.com")
        self.super_admin.company = self.company
        self.super_admin.save(update_fields=["company"])

    def customer_payload(self, **overrides):
        payload = {
            "name": "Aman Verma", "mobile": "9876543210", "residential_address": "Noida, Uttar Pradesh",
            "project": "Paramshiv Greens", "plot_number": "A-101", "plot_size": "100 sq yd",
            "total_agreed_amount": "500000.00", "due_date": "2026-12-31", "status": "ACTIVE",
        }
        payload.update(overrides)
        return payload

    def create_customer(self):
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("accounts-customer-list"), self.customer_payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data

    def issue(self, customer_id, **overrides):
        body = {"serial_number": "031", "receipt_date": "2026-10-27", "amount": "100000.00", "payment_method": "CASH", "reference_number": "", "drawn_on": "", "idempotency_key": "submission-a"}
        body.update(overrides)
        return self.client.post(reverse("accounts-receipt-issue", args=[customer_id]), body, format="json")

    def test_ceo_only_and_tenant_scoped_customer_access(self):
        customer = self.create_customer()
        self.client.force_authenticate(self.employee)
        self.assertEqual(self.client.get(reverse("accounts-customer-list")).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse("accounts-customer-detail", args=[customer["id"]])).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.other_ceo)
        self.assertEqual(self.client.get(reverse("accounts-customer-detail", args=[customer["id"]])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("accounts-customer-list")).data["count"], 0)

    def test_django_super_admin_is_authorized(self):
        self.client.force_authenticate(self.super_admin)
        response = self.client.post(reverse("accounts-customer-list"), self.customer_payload(name="Super Admin customer"), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_multiple_payments_balance_and_receipt_snapshot_are_preserved(self):
        customer = self.create_customer()
        first = self.issue(customer["id"])
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertEqual(first.data["balance_amount"], "400000.00")
        second = self.issue(customer["id"], serial_number="032", amount="20000.00", payment_method="UPI", reference_number="UPI-1", idempotency_key="submission-b")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        detail = self.client.get(reverse("accounts-customer-detail", args=[customer["id"]]))
        self.assertEqual(detail.data["total_received"], "120000.00")
        self.assertEqual(detail.data["outstanding_balance"], "380000.00")
        self.assertEqual(len(detail.data["payments"]), 2)
        customer_model = CustomerLedger.objects.get(pk=customer["id"])
        customer_model.residential_address = "New Address"
        customer_model.save(update_fields=["residential_address"])
        self.assertEqual(IssuedReceipt.objects.get(pk=first.data["id"]).snapshot["residential_address"], "Noida, Uttar Pradesh")

    def test_duplicate_serial_idempotency_and_excess_amount_are_rejected(self):
        customer = self.create_customer()
        first = self.issue(customer["id"])
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        same_submission = self.issue(customer["id"])
        self.assertEqual(same_submission.status_code, status.HTTP_201_CREATED)
        self.assertEqual(same_submission.data["id"], first.data["id"])
        self.assertEqual(Payment.objects.count(), 1)
        duplicate_serial = self.issue(customer["id"], idempotency_key="other", amount="1.00")
        self.assertEqual(duplicate_serial.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("serial_number", duplicate_serial.data)
        excess = self.issue(customer["id"], serial_number="033", idempotency_key="third", amount="400001.00")
        self.assertEqual(excess.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("amount", excess.data)

    def test_cancellation_reverses_the_balance_without_deleting_history_and_pdf_is_fixed_size(self):
        customer = self.create_customer()
        issued = self.issue(customer["id"])
        receipt_id = issued.data["id"]
        cancelled = self.client.post(reverse("accounts-receipt-cancel", args=[receipt_id]), {"reason": "Cheque returned"}, format="json")
        self.assertEqual(cancelled.status_code, status.HTTP_200_OK, cancelled.data)
        self.assertEqual(cancelled.data["status"], "CANCELLED")
        detail = self.client.get(reverse("accounts-customer-detail", args=[customer["id"]]))
        self.assertEqual(detail.data["total_received"], "0.00")
        self.assertEqual(len(detail.data["receipts"]), 1)
        pdf = self.client.get(reverse("accounts-receipt-pdf", args=[receipt_id]))
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertGreater(PAGE_SIZE[0], PAGE_SIZE[1])
        self.assertAlmostEqual(PAGE_SIZE[0] / PAGE_SIZE[1], 1.40625, places=3)

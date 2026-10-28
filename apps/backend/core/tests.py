from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Company
from organizations.models import Branch, Department, EmployeeProfile
from leads.models import Lead
from raw_data.models import RawLead
from inventory.models import InventoryItem
from workspace.models import FollowUp

from .models import Notification
from .notifications import create_notification


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="NIPRIX One")
        self.other_company = Company.objects.create(name="NIPRIX Two")
        self.user = User.objects.create_user(
            username="notification_user",
            password="TestPassword123!",
            company=self.company,
        )
        self.other_user = User.objects.create_user(
            username="notification_other",
            password="TestPassword123!",
            company=self.other_company,
        )

    def notification(self, **overrides):
        values = {
            "company": self.company,
            "recipient": self.user,
            "notification_type": Notification.Type.SYSTEM,
            "title": "Workspace update",
            "body": "A real system update is available.",
            "href": "/leads",
        }
        values.update(overrides)
        return Notification.objects.create(**values)

    def test_notifications_are_private_to_user_and_company(self):
        own = self.notification()
        self.notification(recipient=self.other_user, company=self.other_company, title="Other tenant")
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("notification-list"), {"page": 1, "page_size": 20})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], own.id)
        self.assertEqual(self.client.get(reverse("notification-unread-count")).data["count"], 1)

    def test_read_and_mark_all_only_update_current_users_notifications(self):
        first = self.notification()
        second = self.notification(title="Second update")
        foreign = self.notification(recipient=self.other_user, company=self.other_company, title="Other tenant")
        self.client.force_authenticate(self.user)

        read = self.client.post(reverse("notification-read", args=[first.pk]), {}, format="json")
        self.assertEqual(read.status_code, status.HTTP_200_OK)
        self.assertTrue(read.data["is_read"])
        marked = self.client.post(reverse("notification-mark-all-read"), {}, format="json")
        self.assertEqual(marked.status_code, status.HTTP_204_NO_CONTENT)
        second.refresh_from_db()
        foreign.refresh_from_db()
        self.assertTrue(second.is_read)
        self.assertFalse(foreign.is_read)

    def test_delivery_service_rejects_cross_company_recipient(self):
        notification = create_notification(
            company=self.company,
            recipient=self.other_user,
            notification_type=Notification.Type.SYSTEM,
            title="Should not cross tenants",
        )

        self.assertIsNone(notification)
        self.assertFalse(Notification.objects.exists())


class GlobalSearchAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Search Co")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Noida")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="search-ceo", password="TestPassword123!", role=User.Role.CEO, company=self.company)
        self.employee_user = User.objects.create_user(username="search-employee", password="TestPassword123!", company=self.company)
        self.employee = EmployeeProfile.objects.create(user=self.employee_user, branch=self.branch, department=self.department, employee_code="SEARCH-EMP")
        self.other = Company.objects.create(name="Other Search Co")
        self.other_ceo = User.objects.create_user(username="other-search-ceo", password="TestPassword123!", role=User.Role.CEO, company=self.other)

        self.lead = Lead.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.ceo, name="Aman Verma", phone="+91 98765-43210", normalized_phone="919876543210", email="aman@example.com")
        self.recovery = Lead.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.ceo, name="Aman Recovery", phone="9876512345", normalized_phone="919876512345", email="recover@example.com", recovery_category=Lead.RecoveryCategory.NOT_PICK_CALL)
        self.follow_up = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.ceo, lead=self.lead, title="Call Aman", scheduled_at=timezone.now())
        self.raw = RawLead.objects.create(company=self.company, created_by=self.ceo, name="Aman Raw", phone="9876599999", normalized_phone="919876599999", email="raw@example.com")
        self.inventory = InventoryItem.objects.create(company=self.company, created_by=self.ceo, project="Aman Heights", unit_number="B-203", property_type="Apartment", size_sqft="1000", floor="2", basic_price="5000000", landing="4500000")
        RawLead.objects.create(company=self.other, created_by=self.other_ceo, name="Aman Foreign", phone="9876500000", normalized_phone="919876500000")

    def search(self, user, query, **params):
        self.client.force_authenticate(user)
        return self.client.get(reverse("global-search"), {"q": query, **params})

    def test_searches_all_record_types_and_masks_sensitive_phone_and_inventory_price(self):
        response = self.search(self.ceo, "Aman")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        results = response.data["results"]
        self.assertEqual(results["leads"][0]["id"], self.lead.pk)
        self.assertEqual(results["lead_recovery"][0]["id"], self.recovery.pk)
        self.assertEqual(results["follow_ups"][0]["id"], self.follow_up.pk)
        self.assertEqual(results["raw_data"][0]["id"], self.raw.pk)
        self.assertEqual(results["inventory"][0]["id"], self.inventory.pk)
        self.assertIn("•••• 3210", results["leads"][0]["detail"])
        self.assertNotIn("landing", str(results["inventory"]).lower())
        self.assertNotIn("5000000", str(results["inventory"]))

    def test_partial_phone_middle_digits_recovery_and_role_scope(self):
        two_digits = self.search(self.ceo, "54")
        self.assertEqual(two_digits.status_code, status.HTTP_200_OK)
        self.assertEqual(two_digits.data["results"]["leads"][0]["id"], self.lead.pk)
        middle = self.search(self.ceo, "765")
        self.assertEqual(middle.data["results"]["lead_recovery"][0]["id"], self.recovery.pk)
        self.assertEqual(middle.data["results"]["follow_ups"][0]["id"], self.follow_up.pk)
        employee_response = self.search(self.employee_user, "Aman")
        self.assertEqual(employee_response.status_code, status.HTTP_200_OK)
        self.assertEqual(employee_response.data["results"]["raw_data"], [])
        self.assertNotIn("Foreign", str(employee_response.data))

    def test_empty_invalid_limits_and_result_cap_are_safe(self):
        empty = self.search(self.ceo, "")
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertTrue(all(not rows for rows in empty.data["results"].values()))
        self.assertEqual(self.search(self.ceo, "A", limit=0).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.search(self.ceo, "A" * 101).status_code, status.HTTP_400_BAD_REQUEST)

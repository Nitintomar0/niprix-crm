from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from leads.models import Lead, LeadAssignment
from organizations.models import Branch, Company, Department, EmployeeProfile

from .models import RawLead


class RawDataAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Raw Data Co")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Noida")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="raw-ceo", password="password", role="CEO", company=self.company)
        self.manager_user = User.objects.create_user(username="raw-manager", password="password", role="MANAGER", company=self.company)
        self.manager = EmployeeProfile.objects.create(user=self.manager_user, branch=self.branch, department=self.department, employee_code="RAW-MANAGER")
        self.employee_user = User.objects.create_user(username="raw-employee", password="password", role="EMPLOYEE", company=self.company)
        self.employee = EmployeeProfile.objects.create(user=self.employee_user, branch=self.branch, department=self.department, employee_code="RAW-EMP")
        self.employee2_user = User.objects.create_user(username="raw-employee2", password="password", role="EMPLOYEE", company=self.company)
        self.employee2 = EmployeeProfile.objects.create(user=self.employee2_user, branch=self.branch, department=self.department, employee_code="RAW-EMP2")
        self.other = Company.objects.create(name="Other Raw Co")
        self.other_branch = Branch.objects.create(company=self.other, name="Other", city="Delhi")
        self.other_department = Department.objects.create(branch=self.other_branch, name="Sales")
        self.other_ceo = User.objects.create_user(username="other-raw-ceo", password="password", role="CEO", company=self.other)

    def raw(self, phone, **fields):
        return RawLead.objects.create(company=self.company, created_by=self.ceo, phone=phone, normalized_phone=f"91{phone}", **fields)

    def post_distribution(self, body, preview=False):
        self.client.force_authenticate(self.ceo)
        return self.client.post(reverse("raw-data-distribution-preview" if preview else "raw-data-distribute"), body, format="json")

    def test_only_ceo_can_access_and_companies_are_isolated(self):
        mine = self.raw("9876543210", name="Mine")
        foreign = RawLead.objects.create(company=self.other, created_by=self.other_ceo, phone="9876543211", normalized_phone="919876543211")
        for user in (self.manager_user, self.employee_user):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(reverse("raw-lead-list")).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        listed = self.client.get(reverse("raw-lead-list"))
        self.assertEqual([row["id"] for row in listed.data["results"]], [mine.pk])
        self.assertEqual(self.client.get(reverse("raw-lead-detail", args=[foreign.pk])).status_code, status.HTTP_404_NOT_FOUND)

    def test_manual_create_and_duplicate_protection(self):
        self.client.force_authenticate(self.ceo)
        body = {"name": "Aman", "phone": "+91 98765-43210", "preferred_location": "Noida"}
        created = self.client.post(reverse("raw-lead-list"), body, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertEqual(RawLead.objects.get().normalized_phone, "919876543210")
        duplicate = self.client.post(reverse("raw-lead-list"), {"phone": "9876543210"}, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_preview_is_stateless_and_detects_invalid_and_duplicate_rows(self):
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("raw-data-preview"), {"rows": [
            {"name": "Good", "phone": "9876543210"},
            {"name": "Repeated", "phone": "9876543210"},
            {"name": "Bad", "phone": "not-a-phone"},
        ]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(RawLead.objects.count(), 0)
        self.assertEqual(response.data["summary"]["valid"], 0)
        self.assertIn("Duplicate phone number in this file.", response.data["rows"][0]["errors"])

    def test_edited_preview_rows_can_be_saved_without_invalid_rows(self):
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("raw-data-save-preview"), {"rows": [
            {"name": "Edited", "phone": "9876543210", "source": "manual"},
            {"name": "Ignored", "phone": "bad"},
        ]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(RawLead.objects.count(), 1)

    def test_equal_specific_custom_distribution_and_removal(self):
        leads = [self.raw(f"98765432{index:02d}") for index in range(10, 14)]
        preview = self.post_distribution({"raw_lead_ids": [lead.pk for lead in leads], "employee_ids": [self.employee.pk, self.employee2.pk], "mode": "EQUAL"}, preview=True)
        self.assertEqual(preview.status_code, status.HTTP_200_OK, preview.data)
        self.assertEqual([item["count"] for item in preview.data["allocations"]], [2, 2])
        response = self.post_distribution({"raw_lead_ids": [lead.pk for lead in leads], "employee_ids": [self.employee.pk, self.employee2.pk], "mode": "EQUAL"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(RawLead.objects.count(), 0)
        self.assertEqual(Lead.objects.count(), 4)
        self.assertEqual(LeadAssignment.objects.count(), 4)
        more = [self.raw(f"98765433{index:02d}") for index in range(10, 13)]
        response = self.post_distribution({"raw_lead_ids": [lead.pk for lead in more], "employee_ids": [self.employee.pk], "mode": "SPECIFIC"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Lead.objects.filter(assigned_to=self.employee).count(), 5)
        custom = [self.raw(f"98765434{index:02d}") for index in range(10, 14)]
        response = self.post_distribution({"raw_lead_ids": [lead.pk for lead in custom], "employee_ids": [self.employee.pk, self.employee2.pk], "mode": "CUSTOM", "allocations": {str(self.employee.pk): 3, str(self.employee2.pk): 1}})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(RawLead.objects.count(), 0)

    def test_uneven_quantity_distribution_and_invalid_requests(self):
        [self.raw(f"98765435{index:02d}") for index in range(10, 15)]
        preview = self.post_distribution({"quantity": 5, "employee_ids": [self.employee.pk, self.employee2.pk], "mode": "EQUAL"}, preview=True)
        self.assertEqual([row["count"] for row in preview.data["allocations"]], [3, 2])
        invalid = self.post_distribution({"quantity": 6, "employee_ids": [self.employee.pk], "mode": "SPECIFIC"})
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        ids = list(RawLead.objects.values_list("pk", flat=True))
        mismatch = self.post_distribution({"raw_lead_ids": ids, "employee_ids": [self.employee.pk, self.employee2.pk], "mode": "CUSTOM", "allocations": {str(self.employee.pk): 1, str(self.employee2.pk): 1}})
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_employee_and_normal_lead_collision_are_rejected_atomically(self):
        raw = self.raw("9876543610")
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])
        inactive = self.post_distribution({"raw_lead_ids": [raw.pk], "employee_ids": [self.employee.pk], "mode": "SPECIFIC"})
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(RawLead.objects.filter(pk=raw.pk).exists())
        self.employee.is_active = True
        self.employee.save(update_fields=["is_active"])
        Lead.objects.create(company=self.company, branch=self.branch, phone=raw.phone, normalized_phone=raw.normalized_phone)
        collision = self.post_distribution({"raw_lead_ids": [raw.pk], "employee_ids": [self.employee.pk], "mode": "SPECIFIC"})
        self.assertEqual(collision.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(RawLead.objects.filter(pk=raw.pk).exists())

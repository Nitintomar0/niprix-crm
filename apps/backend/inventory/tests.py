from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Branch, Company, Department, EmployeeProfile
from .models import InventoryItem


class InventoryAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Inventory A")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Noida")
        department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="inventory_ceo", password="TestPassword123!", role="CEO", company=self.company)
        self.manager_user = User.objects.create_user(username="inventory_manager", password="TestPassword123!", role="MANAGER", company=self.company)
        EmployeeProfile.objects.create(user=self.manager_user, branch=self.branch, department=department, employee_code="INV-MGR")
        self.employee = User.objects.create_user(username="inventory_employee", password="TestPassword123!", company=self.company)
        EmployeeProfile.objects.create(user=self.employee, branch=self.branch, department=department, employee_code="INV-EMP")
        other = Company.objects.create(name="Inventory B")
        other_branch = Branch.objects.create(company=other, name="HQ", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        self.other_ceo = User.objects.create_user(username="inventory_other", password="TestPassword123!", role="CEO", company=other)
        EmployeeProfile.objects.create(user=self.other_ceo, branch=other_branch, department=other_department, employee_code="INV-OTHER")

    def payload(self, **overrides):
        return {"project": "Apex Park", "unit_number": "Shop 101", "property_type": "Commercial", "size_sqft": "250", "floor": "Ground", "basic_price": "30000", "landing": "26000", "status": "AVAILABLE", **overrides}

    def test_ceo_landing_is_private_and_bulk_items_are_tenant_scoped(self):
        self.client.force_authenticate(self.ceo)
        created = self.client.post(reverse("inventory-list"), self.payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        item_id = created.data["id"]
        self.assertEqual(created.data["landing"], "26000.00")
        bulk = self.client.post(reverse("inventory-bulk-create"), {"items": [self.payload(unit_number="Shop 102", landing="27000"), self.payload(unit_number="Shop 103", landing="28000", status="HOLD")]}, format="json")
        self.assertEqual(bulk.status_code, status.HTTP_201_CREATED, bulk.data)
        self.assertEqual(InventoryItem.objects.filter(company=self.company).count(), 3)
        filtered = self.client.get(reverse("inventory-list"), {"search": "Shop", "status": "HOLD", "page": 1, "page_size": 1})
        self.assertEqual(filtered.data["count"], 1)
        self.assertEqual(filtered.data["results"][0]["unit_number"], "Shop 103")

        self.client.force_authenticate(self.manager_user)
        response = self.client.get(reverse("inventory-detail", args=[item_id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("landing", response.data)
        self.assertEqual(self.client.patch(reverse("inventory-detail", args=[item_id]), {"landing": "1"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(reverse("inventory-bulk-create"), {"items": [self.payload(unit_number="Shop 104", landing="1")]}, format="json").status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.other_ceo)
        self.assertEqual(self.client.get(reverse("inventory-detail", args=[item_id])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(reverse("inventory-list")).data["count"], 0)

    def test_archive_and_employee_write_protection(self):
        self.client.force_authenticate(self.ceo)
        item = self.client.post(reverse("inventory-list"), self.payload(), format="json").data
        self.client.force_authenticate(self.employee)
        self.assertEqual(self.client.post(reverse("inventory-list"), self.payload(unit_number="Shop 105"), format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        self.assertEqual(self.client.delete(reverse("inventory-detail", args=[item["id"]])).status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(InventoryItem.objects.get(pk=item["id"]).archived_at)
        self.assertEqual(self.client.get(reverse("inventory-list")).data["count"], 0)

from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Company, Branch, Department, EmployeeProfile


class EmployeeAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Test Realty",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            name="Main Branch",
            city="Bengaluru",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            name="Sales",
        )

        self.ceo = User.objects.create_user(
            username="api_ceo",
            password="TestPassword123!",
            role=User.Role.CEO,
            company=self.company,
        )

        self.employee = User.objects.create_user(
            username="api_employee",
            password="TestPassword123!",
            role=User.Role.EMPLOYEE,
        )

        EmployeeProfile.objects.create(
            user=self.employee,
            branch=self.branch,
            department=self.department,
            employee_code="API-EMP-001",
        )

    def test_ceo_can_list_company_employees(self):
        self.client.force_authenticate(user=self.ceo)

        response = self.client.get(
            reverse("employee-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(len(response.data), 1)

    def test_unauthenticated_user_cannot_list_employees(self):
        response = self.client.get(
            reverse("employee-list")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_ceo_cannot_see_other_company_employees(self):
        other_company = Company.objects.create(
            name="Other Realty",
        )

        other_branch = Branch.objects.create(
            company=other_company,
            name="Other Branch",
            city="Delhi",
        )

        other_department = Department.objects.create(
            branch=other_branch,
            name="Sales",
        )

        other_employee = User.objects.create_user(
            username="other_employee",
            role=User.Role.EMPLOYEE,
        )

        EmployeeProfile.objects.create(
            user=other_employee,
            branch=other_branch,
            department=other_department,
            employee_code="OTHER-EMP-001",
        )

        self.client.force_authenticate(user=self.ceo)

        response = self.client.get(
            reverse("employee-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["employee_code"],
            "API-EMP-001",
        )

    def test_employee_cannot_see_other_branch_employees(self):
        other_branch = Branch.objects.create(
            company=self.company,
            name="Other Branch",
            city="Delhi",
        )

        other_department = Department.objects.create(
            branch=other_branch,
            name="Sales",
        )

        other_employee = User.objects.create_user(
            username="branch_employee",
            role=User.Role.EMPLOYEE,
        )

        EmployeeProfile.objects.create(
            user=other_employee,
            branch=other_branch,
            department=other_department,
            employee_code="BRANCH-EMP-001",
        )

        self.client.force_authenticate(user=self.employee)

        response = self.client.get(
            reverse("employee-list")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["employee_code"],
            "API-EMP-001",
        )

    def test_ceo_can_filter_and_paginate_company_employees(self):
        self.client.force_authenticate(user=self.ceo)
        response = self.client.get(reverse("employee-list"), {"search": "API", "page": 1, "page_size": 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)

    def test_employee_cannot_update_protected_fields(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.patch(reverse("employee-detail", args=[self.employee.employee_profile.pk]), {"branch": self.branch.pk, "phone": "9999999999"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.employee_profile.refresh_from_db()
        self.assertEqual(self.employee.employee_profile.phone, "9999999999")

    def test_ceo_cannot_assign_cross_company_manager(self):
        other_company = Company.objects.create(name="Manager Other Realty")
        other_branch = Branch.objects.create(company=other_company, name="Other", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        other_user = User.objects.create_user(username="cross_manager", company=other_company)
        other_profile = EmployeeProfile.objects.create(user=other_user, branch=other_branch, department=other_department, employee_code="CROSS-MANAGER")
        self.client.force_authenticate(user=self.ceo)
        response = self.client.patch(reverse("employee-detail", args=[self.employee.employee_profile.pk]), {"reporting_manager": other_profile.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

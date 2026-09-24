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
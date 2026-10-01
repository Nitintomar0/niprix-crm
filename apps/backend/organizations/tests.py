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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.employee.employee_profile.refresh_from_db()
        self.assertNotEqual(self.employee.employee_profile.phone, "9999999999")

    def test_ceo_cannot_assign_cross_company_manager(self):
        other_company = Company.objects.create(name="Manager Other Realty")
        other_branch = Branch.objects.create(company=other_company, name="Other", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        other_user = User.objects.create_user(username="cross_manager", company=other_company)
        other_profile = EmployeeProfile.objects.create(user=other_user, branch=other_branch, department=other_department, employee_code="CROSS-MANAGER")
        self.client.force_authenticate(user=self.ceo)
        response = self.client.patch(reverse("employee-detail", args=[self.employee.employee_profile.pk]), {"reporting_manager": other_profile.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ceo_deactivation_reassigns_live_work_and_invalidates_tokens(self):
        from datetime import timedelta
        from django.utils import timezone
        from leads.models import Lead, LeadAssignment
        from workspace.models import FollowUp, FollowUpActivity

        replacement_user = User.objects.create_user(
            username="replacement", password="TestPassword123!", role=User.Role.EMPLOYEE, company=self.company,
        )
        replacement = EmployeeProfile.objects.create(
            user=replacement_user, branch=self.branch, department=self.department, employee_code="API-EMP-002",
        )
        profile = self.employee.employee_profile
        lead = Lead.objects.create(
            company=self.company, branch=self.branch, assigned_to=profile, created_by=self.ceo,
            phone="9876543210", normalized_phone="919876543210", name="Assigned customer",
        )
        active_follow_up = FollowUp.objects.create(
            company=self.company, branch=self.branch, assigned_to=profile, created_by=self.ceo,
            lead=lead, title="Upcoming callback", scheduled_at=timezone.now() + timedelta(days=1),
        )
        completed_follow_up = FollowUp.objects.create(
            company=self.company, branch=self.branch, assigned_to=profile, created_by=self.ceo,
            lead=lead, title="Completed callback", scheduled_at=timezone.now() + timedelta(days=1),
            status=FollowUp.Status.COMPLETED, completed_at=timezone.now(),
        )
        token_response = self.client.post(reverse("token_obtain_pair"), {"username": "api_employee", "password": "TestPassword123!"}, format="json")
        self.assertEqual(token_response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.ceo)
        response = self.client.post(reverse("employee-deactivate", args=[profile.pk]), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["leads_reassigned"], 1)
        self.assertEqual(response.data["follow_ups_reassigned"], 1)
        profile.refresh_from_db(); self.employee.refresh_from_db(); lead.refresh_from_db(); active_follow_up.refresh_from_db(); completed_follow_up.refresh_from_db()
        self.assertFalse(profile.is_active)
        self.assertFalse(profile.can_receive_leads)
        self.assertFalse(self.employee.is_active)
        self.assertEqual(lead.assigned_to, replacement)
        self.assertEqual(active_follow_up.assigned_to, replacement)
        self.assertEqual(completed_follow_up.assigned_to, profile)
        self.assertTrue(LeadAssignment.objects.filter(lead=lead, previous_assignee=profile, assigned_to=replacement).exists())
        self.assertTrue(FollowUpActivity.objects.filter(follow_up=active_follow_up, activity_type="REASSIGNED").exists())

        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        self.assertEqual(self.client.get(reverse("employee-list")).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials()
        refresh = self.client.post(reverse("token_refresh"), {"refresh": token_response.data["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_ceo_cannot_deactivate_an_employee(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(reverse("employee-deactivate", args=[self.employee.employee_profile.pk]), format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ceo_history_safe_deletion_hides_an_inactive_employee(self):
        profile = self.employee.employee_profile
        profile.is_active = False
        profile.employment_status = EmployeeProfile.EmploymentStatus.INACTIVE
        profile.save(update_fields=["is_active", "employment_status"])
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])
        self.client.force_authenticate(user=self.ceo)
        response = self.client.delete(reverse("employee-delete", args=[profile.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        profile.refresh_from_db()
        self.assertTrue(profile.is_deleted)
        self.assertFalse(EmployeeProfile.objects.filter(pk=profile.pk).exclude(is_deleted=True).exists())
        self.assertNotIn(profile.pk, [item["id"] for item in self.client.get(reverse("employee-list")).data])

        self.client.force_authenticate(user=self.employee)
        self.assertEqual(self.client.delete(reverse("employee-delete", args=[profile.pk])).status_code, status.HTTP_403_FORBIDDEN)

    def test_only_ceo_can_create_employee_login_and_direct_deactivation_is_blocked(self):
        payload = {
            "username": "new_sales_employee", "email": "new@example.com", "password": "TestPassword123!",
            "role": User.Role.EMPLOYEE, "branch": self.branch.pk, "department": self.department.pk,
            "employee_code": "API-EMP-NEW",
        }
        self.client.force_authenticate(user=self.employee)
        denied = self.client.post(reverse("employee-create"), payload, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.ceo)
        created = self.client.post(reverse("employee-create"), payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.client.force_authenticate(user=None)
        logged_in = self.client.post(reverse("token_obtain_pair"), {"username": payload["username"], "password": payload["password"]}, format="json")
        self.assertEqual(logged_in.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.ceo)
        bypass = self.client.patch(reverse("employee-detail", args=[self.employee.employee_profile.pk]), {"is_active": False}, format="json")
        self.assertEqual(bypass.status_code, status.HTTP_400_BAD_REQUEST)

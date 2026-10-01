from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Branch, Company, Department, EmployeeProfile

from .models import EmployeeDocument, Holiday, LeaveBalance, LeaveRequest, LeaveType


class HrmsSecurityTests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="HRMS Company")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Noida")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="hrms_ceo", password="TestPassword123!", role="CEO", company=self.company)
        self.manager_user = User.objects.create_user(username="hrms_manager", password="TestPassword123!", role="MANAGER", company=self.company)
        self.manager = EmployeeProfile.objects.create(user=self.manager_user, branch=self.branch, department=self.department, employee_code="HR-MGR")
        self.employee_user = User.objects.create_user(username="hrms_employee", password="TestPassword123!", company=self.company)
        self.employee = EmployeeProfile.objects.create(user=self.employee_user, branch=self.branch, department=self.department, employee_code="HR-EMP", reporting_manager=self.manager)
        self.unrelated_user = User.objects.create_user(username="hrms_unrelated", password="TestPassword123!", company=self.company)
        self.unrelated = EmployeeProfile.objects.create(user=self.unrelated_user, branch=self.branch, department=self.department, employee_code="HR-OTHER")
        self.other_company = Company.objects.create(name="Foreign Company")
        self.other_branch = Branch.objects.create(company=self.other_company, name="Other", city="Delhi")
        self.other_department = Department.objects.create(branch=self.other_branch, name="Sales")
        self.other_user = User.objects.create_user(username="foreign_employee", password="TestPassword123!", company=self.other_company)
        self.foreign = EmployeeProfile.objects.create(user=self.other_user, branch=self.other_branch, department=self.other_department, employee_code="HR-FOREIGN")
        self.leave_type = LeaveType.objects.create(company=self.company, name="Casual Leave", annual_allocation=10)

    def create_request(self):
        self.client.force_authenticate(self.employee_user)
        return self.client.post(reverse("leave-request-list"), {"leave_type": self.leave_type.pk, "start_date": str(timezone.localdate() + timedelta(days=2)), "end_date": str(timezone.localdate() + timedelta(days=3)), "reason": "Family event"}, format="json")

    def test_employee_profile_scope_and_restricted_patch(self):
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.get(reverse("employee-detail", args=[self.employee.pk])).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("employee-detail", args=[self.unrelated.pk])).status_code, status.HTTP_404_NOT_FOUND)
        response = self.client.patch(reverse("employee-detail", args=[self.employee.pk]), {"phone": "9999999999", "branch": self.branch.pk, "employee_code": "ESCALATE", "employment_status": "OFFBOARDED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.employee.refresh_from_db()
        self.assertNotEqual(self.employee.phone, "9999999999")
        self.assertEqual(self.employee.employee_code, "HR-EMP")

    def test_manager_and_ceo_scopes_are_tenant_safe(self):
        self.client.force_authenticate(self.manager_user)
        self.assertEqual(self.client.get(reverse("employee-detail", args=[self.employee.pk])).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("employee-detail", args=[self.unrelated.pk])).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.ceo)
        self.assertEqual(self.client.get(reverse("employee-overview", args=[self.employee.pk])).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("employee-detail", args=[self.foreign.pk])).status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_360_detail_endpoints_follow_employee_scope(self):
        self.client.force_authenticate(self.employee_user)
        for name in ("employee-overview", "employee-performance", "employee-attendance", "employee-leads", "employee-work", "employee-activity"):
            self.assertEqual(self.client.get(reverse(name, args=[self.employee.pk])).status_code, status.HTTP_200_OK)
            self.assertIn(self.client.get(reverse(name, args=[self.unrelated.pk])).status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))

    def test_self_service_profile_photo_remove_is_allowed_and_protected(self):
        self.employee.profile_photo.save("portrait.png", SimpleUploadedFile("portrait.png", b"image", content_type="image/png"), save=True)
        self.client.force_authenticate(self.employee_user)
        response = self.client.patch(reverse("employee-detail", args=[self.employee.pk]), {"remove_profile_photo": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.profile_photo)

    def test_leave_workflow_is_atomic_and_scoped(self):
        created = self.create_request()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        leave_request = LeaveRequest.objects.get()
        overlap = self.client.post(reverse("leave-request-list"), {"leave_type": self.leave_type.pk, "start_date": leave_request.start_date, "end_date": leave_request.end_date, "reason": "Duplicate"}, format="json")
        self.assertEqual(overlap.status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(self.unrelated_user)
        self.assertEqual(self.client.post(reverse("leave-request-action", args=[leave_request.pk, "approve"]), {}).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.manager_user)
        approved = self.client.post(reverse("leave-request-action", args=[leave_request.pk, "approve"]), {"comment": "Approved"}, format="json")
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        balance = LeaveBalance.objects.get(employee=self.employee, leave_type=self.leave_type)
        self.assertEqual(balance.available_days, Decimal("8"))
        self.assertEqual(balance.used_days, Decimal("2"))

    def test_holidays_and_documents_are_company_scoped_and_private(self):
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.post(reverse("holiday-list"), {"name": "Holiday", "holiday_date": "2026-12-25"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        holiday = self.client.post(reverse("holiday-list"), {"name": "Holiday", "holiday_date": "2026-12-25"}, format="json")
        self.assertEqual(holiday.status_code, status.HTTP_201_CREATED, holiday.data)
        upload = self.client.post(reverse("employee-document-list", args=[self.employee.pk]), {"kind": "JOINING", "title": "Offer letter", "file": SimpleUploadedFile("offer.pdf", b"safe document", content_type="application/pdf")}, format="multipart")
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)
        self.assertNotIn("file", upload.data)
        document = EmployeeDocument.objects.get()
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(reverse("employee-document-download", args=[document.pk])).status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_is_real_scoped_and_denies_employees(self):
        from attendance.models import AttendanceRecord
        from core.models import AuditLog

        today = timezone.localdate()
        AttendanceRecord.objects.create(employee=self.employee, company=self.company, branch=self.branch, attendance_date=today, check_in_at=timezone.now(), status="PRESENT")
        LeaveRequest.objects.create(company=self.company, employee=self.unrelated, leave_type=self.leave_type, start_date=today, end_date=today, number_of_days=1, reason="Medical", status="APPROVED")
        LeaveRequest.objects.create(company=self.company, employee=self.unrelated, leave_type=self.leave_type, start_date=today + timedelta(days=4), end_date=today + timedelta(days=4), number_of_days=1, reason="Travel", status="PENDING")
        Holiday.objects.create(company=self.company, name="Republic Day", holiday_date=today + timedelta(days=7))
        EmployeeDocument.objects.create(employee=self.employee, kind="IDENTITY", title="ID proof", file=SimpleUploadedFile("id.pdf", b"safe", content_type="application/pdf"), uploaded_by=self.ceo)
        AuditLog.objects.create(company=self.company, actor=self.ceo, action="employee.created", target_type="organizations.EmployeeProfile", target_id=str(self.employee.pk))
        foreign_holiday = Holiday.objects.create(company=self.other_company, name="Foreign holiday", holiday_date=today + timedelta(days=1))

        self.client.force_authenticate(self.ceo)
        response = self.client.get(reverse("hr-dashboard"))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["kpis"]["total_employees"], 3)
        self.assertEqual(response.data["kpis"]["present_today"], 1)
        self.assertEqual(response.data["kpis"]["on_leave_today"], 1)
        self.assertEqual(response.data["kpis"]["pending_leave_requests"], 1)
        self.assertEqual(response.data["documents"]["total"], 1)
        self.assertNotIn(foreign_holiday.name, [item["name"] for item in response.data["holidays"]])
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.get(reverse("hr-dashboard")).status_code, status.HTTP_403_FORBIDDEN)

    def test_ceo_can_update_allocation_but_employee_cannot(self):
        balance = LeaveBalance.objects.create(employee=self.employee, leave_type=self.leave_type, available_days=8, used_days=2)
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.patch(reverse("leave-balance-detail", args=[balance.pk]), {"allocated_days": "12"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        updated = self.client.patch(reverse("leave-balance-detail", args=[balance.pk]), {"allocated_days": "12"}, format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK, updated.data)
        self.assertEqual(updated.data["remaining_days"], "10.0")

    def test_employee_only_sees_company_or_relevant_branch_holidays(self):
        other_branch = Branch.objects.create(company=self.company, name="Branch Two", city="Agra")
        Holiday.objects.create(company=self.company, name="Company day", holiday_date="2026-12-25")
        Holiday.objects.create(company=self.company, branch=self.branch, name="HQ day", holiday_date="2026-12-26")
        Holiday.objects.create(company=self.company, branch=other_branch, name="Other branch day", holiday_date="2026-12-27")
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(reverse("holiday-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({item["name"] for item in response.data}, {"Company day", "HQ day"})

from datetime import datetime, timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Branch, Company, Department, EmployeeProfile
from .models import AttendanceCorrection, AttendancePolicy, AttendanceRecord
from .services import calculate_arrival, calculate_total_work_minutes


class AttendanceAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Attendance Realty")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Bengaluru")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="attendance_ceo", password="TestPassword123!", role=User.Role.CEO, company=self.company)
        self.user = User.objects.create_user(username="attendance_employee", password="TestPassword123!", role=User.Role.EMPLOYEE, company=self.company)
        self.profile = EmployeeProfile.objects.create(user=self.user, branch=self.branch, department=self.department, employee_code="ATT-001")

    def test_check_in_checkout_and_duplicate_protection(self):
        self.client.force_authenticate(self.user)
        checked_in = self.client.post(reverse("attendance-check-in"))
        self.assertEqual(checked_in.status_code, status.HTTP_201_CREATED)
        self.assertTrue(timezone.is_aware(AttendanceRecord.objects.get().check_in_at))
        self.assertEqual(self.client.post(reverse("attendance-check-in")).status_code, status.HTTP_400_BAD_REQUEST)
        checked_out = self.client.post(reverse("attendance-check-out"))
        self.assertEqual(checked_out.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(checked_out.data["total_work_minutes"], 0)
        self.assertEqual(self.client.post(reverse("attendance-check-out")).status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_requires_checkin_and_inactive_profile_is_blocked(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(reverse("attendance-check-out")).status_code, status.HTTP_400_BAD_REQUEST)
        self.profile.is_active = False; self.profile.save()
        self.assertEqual(self.client.post(reverse("attendance-check-in")).status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_profile_cannot_check_out(self):
        record = AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=timezone.now() - timedelta(hours=1))
        self.profile.is_active = False
        self.profile.save()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(reverse("attendance-check-out")).status_code, status.HTTP_400_BAD_REQUEST)
        record.refresh_from_db()
        self.assertIsNone(record.check_out_at)

    def test_late_status_respects_grace_period(self):
        policy = AttendancePolicy.objects.create(company=self.company, workday_start=datetime(2020, 1, 1, 9, 0).time(), grace_minutes=15)
        on_time = timezone.make_aware(datetime.combine(timezone.localdate(), datetime(2020, 1, 1, 9, 15).time()))
        late = timezone.make_aware(datetime.combine(timezone.localdate(), datetime(2020, 1, 1, 9, 16).time()))
        self.assertEqual(calculate_arrival(on_time, policy), (0, AttendanceRecord.Status.PRESENT))
        self.assertEqual(calculate_arrival(late, policy), (1, AttendanceRecord.Status.LATE))

    def test_duration_rejects_checkout_before_checkin(self):
        now = timezone.now() - timedelta(hours=1)
        with self.assertRaisesMessage(Exception, "Check-out cannot be before check-in"):
            calculate_total_work_minutes(now, now - timedelta(minutes=1))

    def test_employee_history_is_scoped_and_ceo_can_correct_with_audit(self):
        record = AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=timezone.now() - timedelta(hours=8))
        other_company = Company.objects.create(name="Other Attendance Realty")
        other_branch = Branch.objects.create(company=other_company, name="Other HQ", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        other_user = User.objects.create_user(username="other_attendance", company=other_company)
        other_profile = EmployeeProfile.objects.create(user=other_user, branch=other_branch, department=other_department, employee_code="ATT-OTHER")
        AttendanceRecord.objects.create(employee=other_profile, company=other_company, branch=other_branch, attendance_date=timezone.localdate(), check_in_at=timezone.now())
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("attendance-list"))
        self.assertEqual(len(response.data), 1)
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_out_at": (timezone.now() - timedelta(hours=1)).isoformat(), "reason": "Approved missed checkout"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AttendanceCorrection.objects.filter(record=record).count(), 1)
        self.assertGreater(record.company.audit_logs.count(), 0)

    def test_employee_cannot_correct_attendance(self):
        record = AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate())
        self.client.force_authenticate(self.user)
        response = self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_in_at": timezone.now().isoformat(), "reason": "No permission"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_correction_rejects_invalid_timestamps_and_recalculates(self):
        check_in = timezone.now() - timedelta(hours=9)
        record = AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=check_in)
        self.client.force_authenticate(self.ceo)
        invalid = self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_out_at": (check_in - timedelta(minutes=1)).isoformat(), "reason": "Invalid order"}, format="json")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        corrected = self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_out_at": (check_in + timedelta(hours=8)).isoformat(), "reason": "Approved missed checkout"}, format="json")
        self.assertEqual(corrected.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertEqual(record.total_work_minutes, 480)
        self.assertFalse(record.early_checkout)
        correction = AttendanceCorrection.objects.get(record=record)
        self.assertIsNone(correction.original_values["check_out_at"])
        self.assertIsNotNone(correction.updated_values["check_out_at"])

    def test_correction_rejects_cross_date_timestamps(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        record = AttendanceRecord.objects.create(
            employee=self.profile,
            company=self.company,
            branch=self.branch,
            attendance_date=yesterday,
            check_in_at=timezone.make_aware(datetime.combine(yesterday, datetime.min.time())),
        )
        self.client.force_authenticate(self.ceo)
        response = self.client.post(
            reverse("attendance-correct", args=[record.pk]),
            {
                "check_out_at": timezone.make_aware(datetime.combine(timezone.localdate(), datetime.min.time())).isoformat(),
                "reason": "Cross-date correction",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_service_rejects_inconsistent_employee_tenant_relationships(self):
        other_company = Company.objects.create(name="Invalid Relationship Realty")
        other_branch = Branch.objects.create(company=other_company, name="Other HQ", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        mismatched_user = User.objects.create_user(username="mismatched_user", company=other_company)
        mismatched_profile = EmployeeProfile.objects.create(
            user=mismatched_user,
            branch=self.branch,
            department=self.department,
            employee_code="ATT-MISMATCH-USER",
        )
        self.client.force_authenticate(mismatched_user)
        self.assertEqual(self.client.post(reverse("attendance-check-in")).status_code, status.HTTP_400_BAD_REQUEST)
        mismatched_department_user = User.objects.create_user(username="mismatched_department", company=self.company)
        EmployeeProfile.objects.create(
            user=mismatched_department_user,
            branch=self.branch,
            department=other_department,
            employee_code="ATT-MISMATCH-DEPT",
        )
        self.client.force_authenticate(mismatched_department_user)
        self.assertEqual(self.client.post(reverse("attendance-check-in")).status_code, status.HTTP_400_BAD_REQUEST)

    def test_ceo_cannot_correct_other_company_attendance(self):
        other_company = Company.objects.create(name="Protected Other Realty")
        other_branch = Branch.objects.create(company=other_company, name="Other HQ", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        other_user = User.objects.create_user(username="protected_other", company=other_company)
        other_profile = EmployeeProfile.objects.create(user=other_user, branch=other_branch, department=other_department, employee_code="ATT-PROTECTED")
        record = AttendanceRecord.objects.create(employee=other_profile, company=other_company, branch=other_branch, attendance_date=timezone.localdate(), check_in_at=timezone.now() - timedelta(hours=1))
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_out_at": timezone.now().isoformat(), "reason": "Cross tenant"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ceo_filters_cannot_bypass_company_scope(self):
        other_company = Company.objects.create(name="Filter Other Realty")
        other_branch = Branch.objects.create(company=other_company, name="Other HQ", city="Delhi")
        other_department = Department.objects.create(branch=other_branch, name="Sales")
        other_user = User.objects.create_user(username="filter_other", company=other_company)
        other_profile = EmployeeProfile.objects.create(user=other_user, branch=other_branch, department=other_department, employee_code="ATT-FILTER")
        AttendanceRecord.objects.create(employee=other_profile, company=other_company, branch=other_branch, attendance_date=timezone.localdate(), check_in_at=timezone.now() - timedelta(hours=1))
        self.client.force_authenticate(self.ceo)
        for parameter, value in (("employee", other_profile.pk), ("branch", other_branch.pk), ("department", other_department.pk)):
            response = self.client.get(reverse("attendance-list"), {parameter: value})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 0)

    def test_manager_only_sees_direct_reports(self):
        manager_user = User.objects.create_user(username="attendance_manager", role=User.Role.MANAGER, company=self.company)
        manager = EmployeeProfile.objects.create(user=manager_user, branch=self.branch, department=self.department, employee_code="ATT-MANAGER")
        self.profile.reporting_manager = manager
        self.profile.save()
        unrelated_user = User.objects.create_user(username="unrelated_employee", company=self.company)
        unrelated = EmployeeProfile.objects.create(user=unrelated_user, branch=self.branch, department=self.department, employee_code="ATT-UNRELATED")
        AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=timezone.now() - timedelta(hours=1))
        AttendanceRecord.objects.create(employee=unrelated, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=timezone.now() - timedelta(hours=1))
        self.client.force_authenticate(manager_user)
        response = self.client.get(reverse("attendance-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["employee_code"] for item in response.data], [self.profile.employee_code])

    def test_correction_can_reopen_with_null_checkout(self):
        check_in = timezone.now() - timedelta(hours=2)
        record = AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=check_in, check_out_at=timezone.now() - timedelta(hours=1), total_work_minutes=60)
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_out_at": None, "reason": "Checkout entered by mistake"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        record.refresh_from_db()
        self.assertIsNone(record.check_out_at)
        self.assertEqual(record.total_work_minutes, 0)
        self.assertFalse(record.early_checkout)

    def test_missing_employee_profile_is_rejected_without_leakage(self):
        user = User.objects.create_user(username="no_attendance_profile", company=self.company)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post(reverse("attendance-check-in")).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse("attendance-current")).status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_date_filters_are_rejected(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("attendance-list"), {"date_from": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(reverse("attendance-list"), {"date_from": "2026-01-02", "date_to": "2026-01-01"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(reverse("attendance-list"), {"page_size": "101"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_correction_rolls_back_when_audit_logging_fails(self):
        check_in = timezone.now() - timedelta(hours=2)
        record = AttendanceRecord.objects.create(employee=self.profile, company=self.company, branch=self.branch, attendance_date=timezone.localdate(), check_in_at=check_in)
        self.client.force_authenticate(self.ceo)
        with patch("attendance.views.log_action", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaisesMessage(RuntimeError, "audit unavailable"):
                self.client.post(reverse("attendance-correct", args=[record.pk]), {"check_out_at": (check_in + timedelta(hours=1)).isoformat(), "reason": "Audit transaction test"}, format="json")
        record.refresh_from_db()
        self.assertIsNone(record.check_out_at)
        self.assertFalse(AttendanceCorrection.objects.filter(record=record).exists())

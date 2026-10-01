from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Branch, Company, Department, EmployeeProfile

from .models import FollowUp, FollowUpActivity, ReminderEvent, ReminderPreference, Task
from .services import prepare_reminder_events


class WorkspaceAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Workspace Realty")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Bengaluru")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="workspace_ceo", password="TestPassword123!", role=User.Role.CEO, company=self.company)
        self.manager_user = User.objects.create_user(username="workspace_manager", password="TestPassword123!", role=User.Role.MANAGER, company=self.company)
        self.manager = EmployeeProfile.objects.create(user=self.manager_user, branch=self.branch, department=self.department, employee_code="WORK-MGR")
        self.employee_user = User.objects.create_user(username="workspace_employee", password="TestPassword123!", role=User.Role.EMPLOYEE, company=self.company)
        self.employee = EmployeeProfile.objects.create(user=self.employee_user, branch=self.branch, department=self.department, employee_code="WORK-EMP", reporting_manager=self.manager)
        self.unrelated_user = User.objects.create_user(username="workspace_unrelated", password="TestPassword123!", role=User.Role.EMPLOYEE, company=self.company)
        self.unrelated = EmployeeProfile.objects.create(user=self.unrelated_user, branch=self.branch, department=self.department, employee_code="WORK-OTHER")
        self.other_company = Company.objects.create(name="Other Workspace Realty")
        self.other_branch = Branch.objects.create(company=self.other_company, name="Other HQ", city="Delhi")
        self.other_department = Department.objects.create(branch=self.other_branch, name="Sales")
        self.other_user = User.objects.create_user(username="workspace_other", password="TestPassword123!", role=User.Role.EMPLOYEE, company=self.other_company)
        self.other_employee = EmployeeProfile.objects.create(user=self.other_user, branch=self.other_branch, department=self.other_department, employee_code="WORK-X")

    def future(self, minutes=60):
        return timezone.now() + timedelta(minutes=minutes)

    def follow_up_payload(self, **overrides):
        data = {"title": "Call prospective buyer", "follow_up_type": "CALL", "description": "Confirm site visit", "scheduled_at": self.future().isoformat(), "status": "PENDING", "priority": "HIGH", "assigned_to": self.employee.pk}
        data.update(overrides)
        return data

    def task_payload(self, **overrides):
        data = {"title": "Prepare listing brochure", "description": "Use approved floor plan", "due_date": (timezone.localdate() + timedelta(days=1)).isoformat(), "priority": "MEDIUM", "assigned_to": self.employee.pk}
        data.update(overrides)
        return data

    def test_unauthenticated_workspace_access_is_rejected(self):
        self.assertEqual(self.client.get(reverse("follow-up-list")).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(reverse("task-list")).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employee_can_create_own_follow_up_and_payload_company_is_ignored(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.post(reverse("follow-up-list"), self.follow_up_payload(assigned_to=self.employee.pk, company=self.other_company.pk, branch=self.other_branch.pk), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        follow_up = FollowUp.objects.get(pk=response.data["id"])
        self.assertEqual(follow_up.company_id, self.company.id)
        self.assertEqual(follow_up.branch_id, self.branch.id)
        self.assertEqual(follow_up.created_by, self.employee_user)
        self.assertEqual(follow_up.follow_up_type, FollowUp.Type.CALL)
        self.assertEqual(follow_up.status, FollowUp.Status.PENDING)
        self.assertEqual(follow_up.priority, "HIGH")
        self.assertEqual(FollowUpActivity.objects.filter(follow_up=follow_up, activity_type=FollowUpActivity.Type.CREATED).count(), 1)

    def test_follow_up_choice_labels_are_rejected_but_choice_codes_are_accepted(self):
        self.client.force_authenticate(self.employee_user)
        invalid = self.client.post(
            reverse("follow-up-list"),
            self.follow_up_payload(follow_up_type="Call", status="Pending", priority="High"),
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("follow_up_type", invalid.data)
        valid = self.client.post(reverse("follow-up-list"), self.follow_up_payload(), format="json")
        self.assertEqual(valid.status_code, status.HTTP_201_CREATED)
        self.assertEqual(valid.data["follow_up_type"], "CALL")
        self.assertEqual(valid.data["status"], "PENDING")
        self.assertEqual(valid.data["priority"], "HIGH")

    def test_follow_up_delete_preserves_its_linked_lead_and_tasks(self):
        from leads.models import Lead
        lead = Lead.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.ceo, phone="9876543210", normalized_phone="919876543210")
        follow_up = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.ceo, lead=lead, title="Unwanted callback", scheduled_at=self.future())
        task = Task.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.ceo, related_follow_up=follow_up, lead=lead, title="Related task", due_date=timezone.localdate())
        FollowUpActivity.objects.create(company=self.company, follow_up=follow_up, performed_by=self.ceo, activity_type=FollowUpActivity.Type.CREATED)
        self.client.force_authenticate(self.ceo)
        response = self.client.delete(reverse("follow-up-detail", args=[follow_up.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Lead.objects.filter(pk=lead.pk).exists())
        task.refresh_from_db()
        self.assertIsNone(task.related_follow_up)
        self.assertFalse(FollowUp.objects.filter(pk=follow_up.pk).exists())

    def test_cross_company_assignment_and_tenant_reads_are_rejected(self):
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("follow-up-list"), self.follow_up_payload(assigned_to=self.other_employee.pk), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        foreign = FollowUp.objects.create(company=self.other_company, branch=self.other_branch, assigned_to=self.other_employee, created_by=self.other_user, title="Private follow up", scheduled_at=self.future())
        self.assertEqual(self.client.get(reverse("follow-up-detail", args=[foreign.pk])).status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_access_or_update_unrelated_work(self):
        follow_up = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.unrelated, created_by=self.manager_user, title="Private team follow up", scheduled_at=self.future())
        task = Task.objects.create(company=self.company, branch=self.branch, assigned_to=self.unrelated, created_by=self.manager_user, title="Private team task", due_date=timezone.localdate())
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.get(reverse("follow-up-detail", args=[follow_up.pk])).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(reverse("task-detail", args=[task.pk]), {"title": "Changed"}, format="json").status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_sees_direct_report_and_can_assign_but_not_unrelated_employee(self):
        direct = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.manager_user, title="Direct report", scheduled_at=self.future())
        FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.unrelated, created_by=self.manager_user, title="Unrelated", scheduled_at=self.future())
        self.client.force_authenticate(self.manager_user)
        listed = self.client.get(reverse("follow-up-list"))
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 1)
        self.assertEqual(listed.data["results"][0]["id"], direct.id)
        created = self.client.post(reverse("task-list"), self.task_payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        denied = self.client.post(reverse("task-list"), self.task_payload(assigned_to=self.unrelated.pk), format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_completion_postponement_and_history_are_atomic(self):
        follow_up = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.manager_user, title="Timeline", scheduled_at=self.future())
        self.client.force_authenticate(self.manager_user)
        postponed = self.client.post(reverse("follow-up-postpone", args=[follow_up.pk]), {"scheduled_at": self.future(120).isoformat(), "note": "Client requested a later call"}, format="json")
        self.assertEqual(postponed.status_code, status.HTTP_200_OK)
        reassigned = self.client.post(reverse("follow-up-reassign", args=[follow_up.pk]), {"assigned_to": self.manager.pk, "note": "Manager will take this call"}, format="json")
        self.assertEqual(reassigned.status_code, status.HTTP_200_OK)
        complete = self.client.post(reverse("follow-up-complete", args=[follow_up.pk]), {"note": "Completed call"}, format="json")
        self.assertEqual(complete.status_code, status.HTTP_200_OK)
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUp.Status.COMPLETED)
        self.assertIsNotNone(follow_up.completed_at)
        activities = self.client.get(reverse("follow-up-activities", args=[follow_up.pk]))
        self.assertEqual(activities.status_code, status.HTTP_200_OK)
        self.assertEqual(activities.data["count"], 3)
        self.assertEqual({row["activity_type"] for row in activities.data["results"]}, {"POSTPONED", "REASSIGNED", "COMPLETED"})

    def test_task_completion_and_cross_company_follow_up_reference_validation(self):
        self.client.force_authenticate(self.ceo)
        foreign = FollowUp.objects.create(company=self.other_company, branch=self.other_branch, assigned_to=self.other_employee, created_by=self.other_user, title="Foreign", scheduled_at=self.future())
        invalid = self.client.post(reverse("task-list"), self.task_payload(related_follow_up=foreign.pk), format="json")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        created = self.client.post(reverse("task-list"), self.task_payload(), format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        completed = self.client.post(reverse("task-complete", args=[created.data["id"]]), {}, format="json")
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        task = Task.objects.get(pk=created.data["id"])
        self.assertEqual(task.status, Task.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)

    def test_filters_pagination_summary_and_overdue_are_real(self):
        for number in range(3):
            FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.manager_user, title=f"Searchable {number}", scheduled_at=self.future(60 + number), priority="HIGH")
        overdue = Task.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.manager_user, title="Overdue task", due_date=timezone.localdate() - timedelta(days=1))
        self.client.force_authenticate(self.manager_user)
        listed = self.client.get(reverse("follow-up-list"), {"search": "Searchable", "priority": "HIGH", "page": 1, "page_size": 2})
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["count"], 3)
        self.assertEqual(len(listed.data["results"]), 2)
        summary = self.client.get(reverse("workspace-summary"))
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data["scope"], "team")
        self.assertEqual(summary.data["tasks"]["overdue"], 1)
        overdue_response = self.client.get(reverse("workspace-overdue"))
        self.assertEqual([row["id"] for row in overdue_response.data["tasks"]], [overdue.id])

    def test_preference_is_tenant_scoped_unique_and_reminder_preparation_is_idempotent(self):
        self.client.force_authenticate(self.employee_user)
        initial = self.client.get(reverse("reminder-preferences"))
        self.assertEqual(initial.status_code, status.HTTP_200_OK)
        self.assertEqual(ReminderPreference.objects.filter(company=self.company, user=self.employee_user).count(), 1)
        update = self.client.patch(reverse("reminder-preferences"), {"reminder_lead_minutes": 45, "daily_summary_enabled": True}, format="json")
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        follow_up = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.manager_user, title="Reminder", scheduled_at=self.future(30))
        first = prepare_reminder_events(now=timezone.now())
        second = prepare_reminder_events(now=timezone.now())
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(ReminderEvent.objects.filter(follow_up=follow_up).count(), 1)

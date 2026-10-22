from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Branch, Company, Department, EmployeeProfile
from workspace.models import FollowUp, Task

from .models import Lead, LeadActivity, LeadAssignment, LeadSource
from .services import create_or_enrich_lead


class LeadAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Lead Realty")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Noida")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="lead_ceo", password="TestPassword123!", role=User.Role.CEO, company=self.company)
        self.manager_user = User.objects.create_user(username="lead_manager", password="TestPassword123!", role=User.Role.MANAGER, company=self.company)
        self.manager = EmployeeProfile.objects.create(user=self.manager_user, branch=self.branch, department=self.department, employee_code="LEAD-MGR")
        self.employee_user = User.objects.create_user(username="lead_employee", password="TestPassword123!", company=self.company)
        self.employee = EmployeeProfile.objects.create(user=self.employee_user, branch=self.branch, department=self.department, employee_code="LEAD-EMP", reporting_manager=self.manager)
        self.unrelated_user = User.objects.create_user(username="lead_unrelated", password="TestPassword123!", company=self.company)
        self.unrelated = EmployeeProfile.objects.create(user=self.unrelated_user, branch=self.branch, department=self.department, employee_code="LEAD-OTHER")
        self.other_company = Company.objects.create(name="Other Lead Realty")
        self.other_branch = Branch.objects.create(company=self.other_company, name="Other HQ", city="Delhi")
        self.other_department = Department.objects.create(branch=self.other_branch, name="Sales")
        self.other_user = User.objects.create_user(username="other_lead_employee", password="TestPassword123!", company=self.other_company)
        self.other_employee = EmployeeProfile.objects.create(user=self.other_user, branch=self.other_branch, department=self.other_department, employee_code="LEAD-OTHER-CO")

    def create_lead(self, actor=None, **data):
        actor = actor or self.employee_user
        self.client.force_authenticate(actor)
        body = {"phone": "9876543210", **data}
        response = self.client.post(reverse("lead-list"), body, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return Lead.objects.get(pk=response.data["id"])

    def test_employee_access_and_tenant_scope(self):
        own = self.create_lead(name="Own")
        other = self.create_lead(self.unrelated_user, phone="9876543211", name="Other")
        self.client.force_authenticate(self.employee_user)
        listing = self.client.get(reverse("lead-list"))
        self.assertEqual([item["id"] for item in listing.data["results"]], [own.pk])
        self.assertEqual(self.client.get(reverse("lead-detail", args=[other.pk])).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.manager_user)
        self.assertEqual(self.client.get(reverse("lead-detail", args=[own.pk])).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse("lead-detail", args=[other.pk])).status_code, status.HTTP_404_NOT_FOUND)
        self.client.force_authenticate(self.ceo)
        self.assertEqual(self.client.get(reverse("lead-detail", args=[other.pk])).status_code, status.HTTP_200_OK)

    def test_overview_analytics_and_site_visits_obey_lead_scope(self):
        requested = self.create_lead(name="Requested visit", status=Lead.Status.SITE_VISIT_REQUESTED)
        done = self.create_lead(phone="9876543211", name="Done visit", status=Lead.Status.SITE_VISIT_DONE)
        private = self.create_lead(self.unrelated_user, phone="9876543212", name="Private visit", status=Lead.Status.SITE_VISIT_REQUESTED)
        foreign = self.create_lead(self.other_user, phone="9876543213", name="Foreign visit", status=Lead.Status.SITE_VISIT_REQUESTED)
        scheduled_at = timezone.now() + timedelta(days=1)
        FollowUp.objects.create(
            company=self.company, branch=self.branch, assigned_to=self.employee,
            created_by=self.employee_user, lead=requested, title="Site visit",
            follow_up_type=FollowUp.Type.SITE_VISIT, scheduled_at=scheduled_at,
        )

        self.client.force_authenticate(self.employee_user)
        analytics = self.client.get(reverse("lead-overview-analytics"), {"days": 14})
        self.assertEqual(analytics.status_code, status.HTTP_200_OK, analytics.data)
        self.assertEqual(analytics.data["scope"], "personal")
        self.assertEqual(next(row["value"] for row in analytics.data["pipeline"] if row["key"] == Lead.Status.SITE_VISIT_REQUESTED), 1)
        requested_rows = self.client.get(reverse("site-visit-list"), {"status": "requested"})
        self.assertEqual(requested_rows.status_code, status.HTTP_200_OK, requested_rows.data)
        self.assertEqual([row["id"] for row in requested_rows.data["results"]], [requested.pk])
        self.assertIsNotNone(requested_rows.data["results"][0]["site_visit_at"])
        done_rows = self.client.get(reverse("site-visit-list"), {"status": "done"})
        self.assertEqual([row["id"] for row in done_rows.data["results"]], [done.pk])

        self.client.force_authenticate(self.ceo)
        company_rows = self.client.get(reverse("site-visit-list"), {"status": "requested"})
        self.assertEqual({row["id"] for row in company_rows.data["results"]}, {requested.pk, private.pk})
        self.assertNotIn(foreign.pk, {row["id"] for row in company_rows.data["results"]})

    def test_cross_company_lead_and_search_are_isolated(self):
        own = self.create_lead(name="Company A")
        other = self.create_lead(self.other_user, phone="9876543210", name="Company B")
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(reverse("lead-list"), {"search": "9876543210"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data["results"]], [own.pk])
        self.assertEqual(self.client.get(reverse("lead-detail", args=[other.pk])).status_code, status.HTTP_404_NOT_FOUND)

    def test_phone_is_immutable_for_every_role(self):
        lead = self.create_lead()
        for actor in (self.employee_user, self.manager_user, self.ceo):
            self.client.force_authenticate(actor)
            response = self.client.patch(reverse("lead-detail", args=[lead.pk]), {"phone": "9999999999"}, format="json")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            lead.refresh_from_db()
            self.assertEqual(lead.phone, "9876543210")

    def test_incomplete_lead_enriches_without_erasing_existing_values(self):
        self.client.force_authenticate(self.employee_user)
        first = self.client.post(reverse("lead-list"), {"phone": "+91 9876543210", "source": "WHATSAPP", "property_type": "3 BHK", "preferred_location": "Noida", "budget_maximum": "12000000"}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(reverse("lead-list"), {"phone": "0919876543210", "source": "FACEBOOK", "name": "Rahul Sharma", "email": "rahul@example.com", "external_lead_id": "fb-1"}, format="json")
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Lead.objects.count(), 1)
        lead = Lead.objects.get()
        self.assertEqual(lead.name, "Rahul Sharma")
        self.assertEqual(lead.email, "rahul@example.com")
        self.assertEqual(lead.property_type, "3 BHK")
        self.assertEqual(lead.preferred_location, "Noida")
        self.assertEqual(LeadSource.objects.filter(lead=lead).count(), 2)
        self.assertTrue(LeadActivity.objects.filter(lead=lead, field_name="name").exists())
        self.client.post(reverse("lead-list"), {"phone": "9876543210", "source": "WEBSITE", "name": "", "email": ""}, format="json")
        lead.refresh_from_db()
        self.assertEqual(lead.name, "Rahul Sharma")
        self.assertEqual(lead.email, "rahul@example.com")

    def test_manual_create_requires_phone_and_allows_other_blanks(self):
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.post(reverse("lead-list"), {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(reverse("lead-list"), {"phone": "9876543210"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "")

    def test_status_temperature_note_and_assignment_history(self):
        lead = self.create_lead()
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.post(reverse("lead-status", args=[lead.pk]), {"status": "CONTACTED", "note": "Reached customer"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(reverse("lead-temperature", args=[lead.pk]), {"temperature": "HOT"}, format="json").status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.manager_user)
        self.assertEqual(self.client.post(reverse("lead-assign", args=[lead.pk]), {"assigned_to": self.manager.pk, "note": "Manager takeover"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        response = self.client.post(reverse("lead-assign", args=[lead.pk]), {"assigned_to": self.manager.pk, "note": "CEO takeover"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_to, self.manager)
        self.assertTrue(LeadAssignment.objects.filter(lead=lead, previous_assignee=self.employee, assigned_to=self.manager).exists())
        self.assertEqual(self.client.get(reverse("lead-assignments", args=[lead.pk])).status_code, status.HTTP_200_OK)

    def test_employee_cannot_reassign_or_assign_cross_tenant(self):
        lead = self.create_lead()
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.post(reverse("lead-assign", args=[lead.pk]), {"assigned_to": self.unrelated.pk}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        self.assertEqual(self.client.post(reverse("lead-assign", args=[lead.pk]), {"assigned_to": self.other_employee.pk}, format="json").status_code, status.HTTP_400_BAD_REQUEST)

    def test_round_robin_skips_inactive_and_is_deterministic(self):
        first_user = User.objects.create_user(username="round_one", company=self.company)
        first = EmployeeProfile.objects.create(user=first_user, branch=self.branch, department=self.department, employee_code="ROUND-1")
        second_user = User.objects.create_user(username="round_two", company=self.company)
        second = EmployeeProfile.objects.create(user=second_user, branch=self.branch, department=self.department, employee_code="ROUND-2")
        self.unrelated.is_active = False
        self.unrelated.save()
        created = [
            create_or_enrich_lead(actor=self.ceo, data={"phone": f"987650000{number}", "branch": self.branch}).lead
            for number in range(1, 4)
        ]
        assigned = [lead.assigned_to_id for lead in created]
        self.assertEqual(assigned, [self.employee.pk, first.pk, second.pk])
        self.assertNotIn(self.unrelated.pk, assigned)

    def test_paused_employee_is_skipped_automatically_but_ceo_can_assign_manually(self):
        self.employee.can_receive_leads = False
        self.employee.save(update_fields=["can_receive_leads"])
        automatic = create_or_enrich_lead(actor=self.ceo, data={"phone": "9876500091", "branch": self.branch}).lead
        self.assertNotEqual(automatic.assigned_to_id, self.employee.pk)
        self.client.force_authenticate(self.ceo)
        manual = self.client.post(reverse("lead-list"), {"phone": "9876500092", "branch": self.branch.pk, "assigned_to": self.employee.pk}, format="json")
        self.assertEqual(manual.status_code, status.HTTP_201_CREATED, manual.data)
        self.assertEqual(manual.data["assigned_to"], self.employee.pk)

    def test_lead_related_phase_four_records_are_tenant_safe_and_timeline_logged(self):
        lead = self.create_lead()
        self.client.force_authenticate(self.employee_user)
        follow = self.client.post(reverse("follow-up-list"), {"title": "Call Rahul", "assigned_to": self.employee.pk, "lead": lead.pk, "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat()}, format="json")
        self.assertEqual(follow.status_code, status.HTTP_201_CREATED, follow.data)
        task = self.client.post(reverse("task-list"), {"title": "Prepare options", "assigned_to": self.employee.pk, "lead": lead.pk, "due_date": (timezone.localdate() + timedelta(days=1)).isoformat()}, format="json")
        self.assertEqual(task.status_code, status.HTTP_201_CREATED, task.data)
        self.assertTrue(FollowUp.objects.filter(lead=lead).exists())
        self.assertTrue(Task.objects.filter(lead=lead).exists())
        self.assertTrue(LeadActivity.objects.filter(lead=lead, activity_type="FOLLOW_UP_CREATED").exists())
        self.assertTrue(LeadActivity.objects.filter(lead=lead, activity_type="TASK_CREATED").exists())
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(reverse("lead-activities", args=[lead.pk])).status_code, status.HTTP_403_FORBIDDEN)

    def test_move_lead_to_follow_up_is_scoped_idempotent_and_auditable(self):
        lead = self.create_lead(name="Follow-up customer")
        self.client.force_authenticate(self.employee_user)
        payload = {
            "title": "Call about shortlisted homes",
            "description": "Customer requested a callback.",
            "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
            "follow_up_type": "CALL",
            "priority": "HIGH",
        }
        first = self.client.post(reverse("lead-move-to-follow-up", args=[lead.pk]), payload, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        second = self.client.post(reverse("lead-move-to-follow-up", args=[lead.pk]), payload, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertFalse(second.data["created"])
        self.assertEqual(FollowUp.objects.filter(lead=lead).count(), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.FOLLOW_UP_NEEDED)
        self.assertEqual(first.data["follow_up"]["assigned_to"], self.employee.pk)
        self.assertTrue(LeadActivity.objects.filter(lead=lead, activity_type="FOLLOW_UP_CREATED").exists())
        self.assertTrue(LeadActivity.objects.filter(lead=lead, field_name="status", new_value="FOLLOW_UP_NEEDED").exists())
        # The persisted workflow state, rather than browser-only filtering,
        # keeps a moved lead out of the active Leads inbox after refresh.
        active_leads = self.client.get(reverse("lead-list"))
        self.assertNotIn(lead.pk, [item["id"] for item in active_leads.data["results"]])

        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.post(reverse("lead-move-to-follow-up", args=[lead.pk]), payload, format="json").status_code, status.HTTP_403_FORBIDDEN)

    def test_move_to_follow_up_returns_a_useful_validation_error_for_invalid_schedule(self):
        lead = self.create_lead(name="Schedule validation")
        self.client.force_authenticate(self.employee_user)
        response = self.client.post(
            reverse("lead-move-to-follow-up", args=[lead.pk]),
            {"scheduled_at": "not-a-date", "follow_up_type": "CALL", "priority": "MEDIUM"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scheduled_at", response.data)
        self.assertFalse(FollowUp.objects.filter(lead=lead).exists())

    def test_pagination_filters_and_safe_hard_delete(self):
        self.create_lead(name="Rahul", status="NEW")
        self.create_lead(phone="9876543211", name="Aman", status="CONTACTED")
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(reverse("lead-list"), {"page": 1, "page_size": 1, "status": "CONTACTED", "search": "Aman"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        lead = Lead.objects.get(name="Aman")
        self.assertEqual(self.client.delete(reverse("lead-detail", args=[lead.pk])).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        blocked = self.client.delete(reverse("lead-detail", args=[lead.pk]))
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("protected", str(blocked.data))
        self.assertTrue(Lead.objects.filter(pk=lead.pk).exists())
        # A record with no protected dependent history may still be deleted.
        deletable = Lead.objects.create(company=self.company, branch=self.branch, phone="9876543299", normalized_phone="919876543299")
        self.assertEqual(self.client.delete(reverse("lead-detail", args=[deletable.pk])).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lead.objects.filter(pk=deletable.pk).exists())

    def test_not_pick_call_recovery_is_scoped_idempotent_and_restorable(self):
        lead = self.create_lead(name="No answer", status=Lead.Status.CONTACTED)
        original_created_at = lead.created_at
        self.client.force_authenticate(self.employee_user)
        endpoint = reverse("lead-mark-not-picked", args=[lead.pk])
        self.assertEqual(self.client.post(endpoint, {"note": "Tried twice"}, format="json").status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post(endpoint, {"note": "Tried twice"}, format="json").status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertEqual(lead.recovery_category, Lead.RecoveryCategory.NOT_PICK_CALL)
        self.assertEqual(lead.recovery_previous_status, Lead.Status.CONTACTED)
        self.assertEqual(LeadActivity.objects.filter(lead=lead, activity_type=LeadActivity.Type.RECOVERY_MARKED).count(), 1)
        self.assertNotIn(lead.pk, [row["id"] for row in self.client.get(reverse("lead-list")).data["results"]])
        recovery = self.client.get(reverse("lead-recovery-list"), {"category": "NOT_PICK_CALL", "search": "answer", "page_size": 1})
        self.assertEqual(recovery.status_code, status.HTTP_200_OK, recovery.data)
        self.assertEqual(recovery.data["count"], 1)
        self.assertEqual(recovery.data["results"][0]["id"], lead.pk)
        self.assertIsNotNone(recovery.data["results"][0]["last_activity"])
        self.assertEqual(self.client.post(reverse("lead-restore", args=[lead.pk]), {}, format="json").status_code, status.HTTP_200_OK)
        lead.refresh_from_db()
        self.assertIsNone(lead.recovery_category)
        self.assertEqual(lead.status, Lead.Status.CONTACTED)
        self.assertEqual(lead.created_at, original_created_at)

    def test_not_interested_enters_recovery_from_patch_and_status_endpoint(self):
        for index, endpoint_name in enumerate(("lead-detail", "lead-status"), start=1):
            lead = self.create_lead(phone=f"987654328{index}", name=f"Not interested {index}", status=Lead.Status.SITE_VISIT_DONE)
            self.client.force_authenticate(self.employee_user)
            endpoint = reverse(endpoint_name, args=[lead.pk])
            method = self.client.patch if endpoint_name == "lead-detail" else self.client.post
            response = method(endpoint, {"status": Lead.Status.NOT_INTERESTED}, format="json")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            lead.refresh_from_db()
            self.assertEqual(lead.recovery_category, Lead.RecoveryCategory.NOT_INTERESTED)
            self.assertEqual(lead.recovery_previous_status, Lead.Status.SITE_VISIT_DONE)
            self.assertNotIn(lead.pk, [row["id"] for row in self.client.get(reverse("lead-list")).data["results"]])

    def test_recovery_follow_up_and_ceo_reassignment_restore_active_owner(self):
        lead = self.create_lead(name="Recovery workflow", status=Lead.Status.CONTACTED)
        self.client.force_authenticate(self.employee_user)
        self.client.post(reverse("lead-mark-not-picked", args=[lead.pk]), {}, format="json")
        payload = {"scheduled_at": (timezone.now() + timedelta(days=1)).isoformat()}
        moved = self.client.post(reverse("lead-move-to-follow-up", args=[lead.pk]), payload, format="json")
        self.assertEqual(moved.status_code, status.HTTP_201_CREATED, moved.data)
        lead.refresh_from_db()
        self.assertIsNone(lead.recovery_category)
        self.assertEqual(lead.status, Lead.Status.FOLLOW_UP_NEEDED)

        handoff = self.create_lead(phone="9876543279", name="Recovery handoff", status=Lead.Status.CONTACTED)
        self.client.force_authenticate(self.employee_user)
        self.client.post(reverse("lead-mark-not-picked", args=[handoff.pk]), {}, format="json")
        self.assertEqual(self.client.post(reverse("lead-assign", args=[handoff.pk]), {"assigned_to": self.manager.pk}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        reassigned = self.client.post(reverse("lead-assign", args=[handoff.pk]), {"assigned_to": self.manager.pk, "note": "Recovery handoff"}, format="json")
        self.assertEqual(reassigned.status_code, status.HTTP_200_OK, reassigned.data)
        handoff.refresh_from_db()
        self.assertIsNone(handoff.recovery_category)
        self.assertEqual(handoff.assigned_to, self.manager)
        self.assertTrue(LeadAssignment.objects.filter(lead=handoff, previous_assignee=self.employee, assigned_to=self.manager).exists())
        self.client.force_authenticate(self.manager_user)
        self.assertIn(handoff.pk, [row["id"] for row in self.client.get(reverse("lead-list")).data["results"]])

    def test_list_filters_use_backend_values_and_preserve_scope(self):
        hot = self.create_lead(
            self.ceo,
            phone="9876543220",
            name="Noida hot lead",
            email="noida@example.com",
            preferred_location="Noida Sector 62",
            source=Lead.Source.WHATSAPP,
            status=Lead.Status.CONTACTED,
            temperature=Lead.Temperature.HOT,
            assigned_to=self.employee.pk,
        )
        cold = self.create_lead(
            self.ceo,
            phone="9876543221",
            name="Delhi cold lead",
            email="delhi@example.com",
            preferred_location="Delhi",
            source=Lead.Source.FACEBOOK,
            status=Lead.Status.NEW,
            temperature=Lead.Temperature.COLD,
            assigned_to=self.manager.pk,
        )
        follow_up = self.create_lead(
            self.ceo,
            phone="9876543222",
            name="Follow up lead",
            status=Lead.Status.FOLLOW_UP_NEEDED,
            assigned_to=self.employee.pk,
        )
        other = self.create_lead(
            self.other_user,
            phone="9876543223",
            name="Other company Noida lead",
            preferred_location="Noida",
            status=Lead.Status.CONTACTED,
            temperature=Lead.Temperature.HOT,
        )
        self.client.force_authenticate(self.ceo)

        def ids(**params):
            response = self.client.get(reverse("lead-list"), params)
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            return response.data["count"], {row["id"] for row in response.data["results"]}

        self.assertEqual(ids(search="noida@example.com"), (1, {hot.pk}))
        self.assertEqual(ids(search=hot.phone), (1, {hot.pk}))
        self.assertEqual(ids(search=str(hot.pk)), (1, {hot.pk}))
        self.assertEqual(ids(status="CONTACTED"), (1, {hot.pk}))
        self.assertEqual(ids(status="FOLLOW_UP_NEEDED"), (1, {follow_up.pk}))
        self.assertEqual(ids(temperature="HOT"), (1, {hot.pk}))
        self.assertEqual(ids(source="WHATSAPP"), (1, {hot.pk}))
        self.assertEqual(ids(assigned_to=str(self.employee.pk)), (1, {hot.pk}))
        self.assertEqual(
            ids(assigned_to=str(self.employee.pk), status="FOLLOW_UP_NEEDED"),
            (1, {follow_up.pk}),
        )
        self.assertEqual(ids(location="sector 62"), (1, {hot.pk}))
        self.assertEqual(
            ids(
                search="Noida",
                status="CONTACTED",
                temperature="HOT",
                source="WHATSAPP",
                assigned_to=str(self.employee.pk),
                location="Noida",
                date_from=timezone.localdate().isoformat(),
                date_to=timezone.localdate().isoformat(),
            ),
            (1, {hot.pk}),
        )
        count, returned = ids(page="1", page_size="1", status="CONTACTED")
        self.assertEqual(count, 1)
        self.assertEqual(returned, {hot.pk})
        self.assertNotIn(other.pk, returned)
        self.assertNotIn(cold.pk, returned)
        invalid = self.client.get(reverse("lead-list"), {"status": "Follow Up Needed"})
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

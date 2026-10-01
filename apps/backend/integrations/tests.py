import hashlib
import hmac
import json
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, override_settings

from accounts.models import User
from core.models import AuditLog
from leads.models import Lead
from organizations.models import Branch, Company, Department, EmployeeProfile
from workspace.models import FollowUp, Task

from .models import IntegrationConfiguration, IntegrationEvent


@override_settings(NIPRIX_META_WEBHOOK_SECRET="meta-test-secret", NIPRIX_WEBSITE_WEBHOOK_SECRET="website-test-secret")
class IntegrationAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Integration Realty")
        self.branch = Branch.objects.create(company=self.company, name="HQ", city="Noida")
        self.department = Department.objects.create(branch=self.branch, name="Sales")
        self.ceo = User.objects.create_user(username="integration_ceo", password="TestPassword123!", role=User.Role.CEO, company=self.company)
        self.manager_user = User.objects.create_user(username="integration_manager", password="TestPassword123!", role=User.Role.MANAGER, company=self.company)
        self.manager = EmployeeProfile.objects.create(user=self.manager_user, branch=self.branch, department=self.department, employee_code="INT-MGR")
        self.employee_user = User.objects.create_user(username="integration_employee", password="TestPassword123!", company=self.company)
        self.employee = EmployeeProfile.objects.create(user=self.employee_user, branch=self.branch, department=self.department, employee_code="INT-EMP", reporting_manager=self.manager)
        self.other_company = Company.objects.create(name="Integration Other")
        self.other_branch = Branch.objects.create(company=self.other_company, name="HQ", city="Delhi")
        self.other_department = Department.objects.create(branch=self.other_branch, name="Sales")
        self.other_user = User.objects.create_user(username="integration_other", password="TestPassword123!", role=User.Role.CEO, company=self.other_company)
        self.other_employee = EmployeeProfile.objects.create(user=self.other_user, branch=self.other_branch, department=self.other_department, employee_code="INT-OTHER")
        self.whatsapp = IntegrationConfiguration.objects.create(company=self.company, branch=self.branch, provider="WHATSAPP", external_account_id="wa-account", is_enabled=True, status="CONFIGURED")
        self.facebook = IntegrationConfiguration.objects.create(company=self.company, branch=self.branch, provider="FACEBOOK", external_account_id="fb-page", is_enabled=True, status="CONFIGURED")
        self.instagram = IntegrationConfiguration.objects.create(company=self.company, branch=self.branch, provider="INSTAGRAM", external_account_id="ig-account", is_enabled=True, status="CONFIGURED")
        self.website = IntegrationConfiguration.objects.create(company=self.company, branch=self.branch, provider="WEBSITE", external_account_id="website-form", is_enabled=True, status="CONFIGURED")

    def signed_post(self, name, payload, secret, header):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return self.client.post(reverse(name), data=raw, content_type="application/json", **{header: signature})

    def test_invalid_or_unsigned_webhooks_are_rejected(self):
        payload = {"account_id": "wa-account", "event_id": "evt-1", "phone": "9876543210"}
        self.assertEqual(self.client.post(reverse("webhook-whatsapp"), payload, format="json").status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.post(reverse("webhook-whatsapp"), json.dumps(payload), content_type="application/json", HTTP_X_HUB_SIGNATURE_256="sha256=invalid")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_provider_webhooks_create_one_lead_and_preserve_sources(self):
        events = [
            ("webhook-whatsapp", {"account_id": "wa-account", "event_id": "wa-1", "phone": "+91 98765 43210", "property_type": "2 BHK", "location": "Noida", "message": "Need apartment"}),
            ("webhook-facebook", {"account_id": "fb-page", "event_id": "fb-1", "external_lead_id": "lead-1", "phone": "919876543210", "name": "Rahul Sharma", "email": "rahul@example.com", "campaign_id": "campaign-1"}),
            ("webhook-instagram", {"account_id": "ig-account", "event_id": "ig-1", "phone": "09876543210", "message": "Interested"}),
        ]
        for name, payload in events:
            response = self.signed_post(name, payload, "meta-test-secret", "HTTP_X_HUB_SIGNATURE_256")
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Lead.objects.count(), 1)
        lead = Lead.objects.get()
        self.assertEqual(lead.name, "Rahul Sharma")
        self.assertEqual(lead.email, "rahul@example.com")
        self.assertEqual(lead.sources.count(), 3)
        self.assertEqual(IntegrationEvent.objects.filter(status="PROCESSED", lead=lead).count(), 3)

    def test_duplicate_event_is_idempotent(self):
        payload = {"account_id": "wa-account", "event_id": "wa-repeat", "phone": "9876543210"}
        first = self.signed_post("webhook-whatsapp", payload, "meta-test-secret", "HTTP_X_HUB_SIGNATURE_256")
        second = self.signed_post("webhook-whatsapp", payload, "meta-test-secret", "HTTP_X_HUB_SIGNATURE_256")
        self.assertFalse(first.data["duplicate"])
        self.assertTrue(second.data["duplicate"])
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(IntegrationEvent.objects.count(), 1)
        self.assertEqual(Lead.objects.get().activities.filter(metadata__has_key="integration_event_id").count(), 1)

    def test_paramshiv_questionnaire_payload_preserves_requirement_and_assignment(self):
        payload = {
            "account_id": "wa-account", "event_id": "paramshiv-location-1", "external_lead_id": "paramshiv-location-1",
            "external_contact_id": "919876543210", "external_conversation_id": "paramshiv-start-1",
            "phone": "919876543210", "name": "Rahul", "property_type": "Builder Floor",
            "preferred_location": "Ghaziabad", "budget_minimum": 5000000, "budget_maximum": 30000000,
            "requirement_notes": "Paramshiv WhatsApp questionnaire: Property type: Builder Floor.",
            "metadata": {"questionnaire_version": "1", "source": "whatsapp"},
        }
        response = self.signed_post("webhook-whatsapp", payload, "meta-test-secret", "HTTP_X_HUB_SIGNATURE_256")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        lead = Lead.objects.get()
        self.assertEqual(lead.requirement_notes, payload["requirement_notes"])
        self.assertEqual(lead.budget_minimum, 5000000)
        self.assertEqual(lead.budget_maximum, 30000000)
        self.assertEqual(lead.assigned_to, self.employee)
        source = lead.sources.get(source="WHATSAPP")
        self.assertEqual(source.external_conversation_id, "paramshiv-start-1")
        self.assertEqual(source.metadata["questionnaire_version"], "1")

    def test_website_signature_and_no_phone_handling(self):
        payload = {"account_id": "website-form", "event_id": "web-ignored", "name": "No Phone"}
        response = self.signed_post("website-intake", payload, "website-test-secret", "HTTP_X_NIPRIX_SIGNATURE_256")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "IGNORED")
        self.assertEqual(Lead.objects.count(), 0)
        self.assertEqual(IntegrationEvent.objects.get().status, "IGNORED")

    def test_admin_configuration_and_event_visibility_are_tenant_scoped(self):
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.get(reverse("integration-list")).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.ceo)
        response = self.client.get(reverse("integration-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("raw_payload", response.data["results"][0])
        self.signed_post("webhook-whatsapp", {"account_id": "wa-account", "event_id": "visible-1", "phone": "9876543210"}, "meta-test-secret", "HTTP_X_HUB_SIGNATURE_256")
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(reverse("integration-events")).data["count"], 0)

    def test_manager_hard_deletes_authorized_lead_with_safe_relations(self):
        lead = Lead.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, phone="9876543210", normalized_phone="919876543210")
        task = Task.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.employee_user, title="Task", due_date="2026-10-01", lead=lead)
        follow = FollowUp.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, created_by=self.employee_user, title="Follow", scheduled_at="2026-10-01T10:00:00Z", lead=lead)
        IntegrationEvent.objects.create(company=self.company, configuration=self.whatsapp, provider="WHATSAPP", idempotency_key="delete-event", lead=lead)
        self.client.force_authenticate(self.manager_user)
        response = self.client.delete(reverse("lead-detail", args=[lead.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lead.objects.filter(pk=lead.pk).exists())
        task.refresh_from_db(); follow.refresh_from_db()
        self.assertIsNone(task.lead_id); self.assertIsNone(follow.lead_id)
        self.assertIsNone(IntegrationEvent.objects.get(idempotency_key="delete-event").lead_id)
        self.assertTrue(AuditLog.objects.filter(action="lead.deleted", target_id=str(lead.pk)).exists())

    def test_employee_cannot_delete_and_manager_cannot_delete_unrelated(self):
        assigned = Lead.objects.create(company=self.company, branch=self.branch, assigned_to=self.employee, phone="9876543210", normalized_phone="919876543210")
        unrelated_user = User.objects.create_user(username="integration_unrelated", company=self.company)
        unrelated = EmployeeProfile.objects.create(user=unrelated_user, branch=self.branch, department=self.department, employee_code="INT-UNRELATED")
        unrelated_lead = Lead.objects.create(company=self.company, branch=self.branch, assigned_to=unrelated, phone="9876543211", normalized_phone="919876543211")
        self.client.force_authenticate(self.employee_user)
        self.assertEqual(self.client.delete(reverse("lead-detail", args=[assigned.pk])).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.manager_user)
        self.assertEqual(self.client.delete(reverse("lead-detail", args=[unrelated_lead.pk])).status_code, status.HTTP_404_NOT_FOUND)

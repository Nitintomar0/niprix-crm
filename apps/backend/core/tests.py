from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from organizations.models import Company

from .models import Notification
from .notifications import create_notification


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.company = Company.objects.create(name="NIPRIX One")
        self.other_company = Company.objects.create(name="NIPRIX Two")
        self.user = User.objects.create_user(
            username="notification_user",
            password="TestPassword123!",
            company=self.company,
        )
        self.other_user = User.objects.create_user(
            username="notification_other",
            password="TestPassword123!",
            company=self.other_company,
        )

    def notification(self, **overrides):
        values = {
            "company": self.company,
            "recipient": self.user,
            "notification_type": Notification.Type.SYSTEM,
            "title": "Workspace update",
            "body": "A real system update is available.",
            "href": "/leads",
        }
        values.update(overrides)
        return Notification.objects.create(**values)

    def test_notifications_are_private_to_user_and_company(self):
        own = self.notification()
        self.notification(recipient=self.other_user, company=self.other_company, title="Other tenant")
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("notification-list"), {"page": 1, "page_size": 20})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], own.id)
        self.assertEqual(self.client.get(reverse("notification-unread-count")).data["count"], 1)

    def test_read_and_mark_all_only_update_current_users_notifications(self):
        first = self.notification()
        second = self.notification(title="Second update")
        foreign = self.notification(recipient=self.other_user, company=self.other_company, title="Other tenant")
        self.client.force_authenticate(self.user)

        read = self.client.post(reverse("notification-read", args=[first.pk]), {}, format="json")
        self.assertEqual(read.status_code, status.HTTP_200_OK)
        self.assertTrue(read.data["is_read"])
        marked = self.client.post(reverse("notification-mark-all-read"), {}, format="json")
        self.assertEqual(marked.status_code, status.HTTP_204_NO_CONTENT)
        second.refresh_from_db()
        foreign.refresh_from_db()
        self.assertTrue(second.is_read)
        self.assertFalse(foreign.is_read)

    def test_delivery_service_rejects_cross_company_recipient(self):
        notification = create_notification(
            company=self.company,
            recipient=self.other_user,
            notification_type=Notification.Type.SYSTEM,
            title="Should not cross tenants",
        )

        self.assertIsNone(notification)
        self.assertFalse(Notification.objects.exists())

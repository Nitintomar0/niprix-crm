"""Small, explicit notification delivery primitives.

The product does not yet expose a notification Channels consumer.  Durable API
records are therefore the source of truth; clients may safely poll without
receiving data for another company or user.
"""

from django.db import transaction

from .models import Notification


def create_notification(*, company, recipient, notification_type, title, body="", href="", metadata=None):
    """Create a notification only for an active user in the same tenant."""
    if not company or not recipient:
        return None
    if recipient.company_id != company.id or not recipient.is_active:
        return None
    return Notification.objects.create(
        company=company,
        recipient=recipient,
        notification_type=notification_type,
        title=title[:160],
        body=body,
        href=href[:255],
        metadata=metadata or {},
    )


def notify_company_roles(*, company, roles, notification_type, title, body="", href="", metadata=None, exclude_user_id=None):
    """Deliver a company event to active users in the requested roles."""
    from accounts.models import User

    recipients = User.objects.filter(company=company, is_active=True, role__in=roles)
    if exclude_user_id:
        recipients = recipients.exclude(pk=exclude_user_id)
    with transaction.atomic():
        return [
            create_notification(
                company=company,
                recipient=recipient,
                notification_type=notification_type,
                title=title,
                body=body,
                href=href,
                metadata=metadata,
            )
            for recipient in recipients
        ]

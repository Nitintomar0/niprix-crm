# Generated manually for safe additive deployment.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0005_reminderpreference_overdue_follow_up_reminders_enabled_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="followup",
            name="customer_name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="followup",
            name="customer_phone",
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name="followup",
            name="customer_progress",
            field=models.CharField(choices=[("CONTACTED", "Contacted"), ("CONTACT_ATTEMPTED", "Contact attempted"), ("INTERESTED", "Interested"), ("FOLLOW_UP_REQUIRED", "Follow-up required"), ("SITE_VISIT_REQUESTED", "Site visit requested"), ("SITE_VISIT_SCHEDULED", "Site visit scheduled"), ("SITE_VISIT_DONE", "Site visit done"), ("NEGOTIATION", "Negotiation"), ("BOOKING_IN_PROGRESS", "Booking in progress"), ("CONVERTED", "Converted / closed won"), ("NOT_INTERESTED", "Not interested"), ("POSTPONED", "Postponed"), ("CANCELLED", "Cancelled"), ("INVALID_CONTACT", "Invalid contact")], default="FOLLOW_UP_REQUIRED", max_length=32),
        ),
        migrations.AddField(
            model_name="followup",
            name="interaction_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="followup",
            name="outcome_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="followup",
            name="next_action",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="followup",
            name="next_action_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

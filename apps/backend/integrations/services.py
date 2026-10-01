"""Signed, idempotent omnichannel intake built on the Phase 5 lead service."""

import hashlib
import hmac
import json
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from leads.models import Lead
from leads.services import create_or_enrich_lead, log_lead_activity

from .models import IntegrationConfiguration, IntegrationEvent


class InvalidWebhook(ValueError):
    pass


def _secret_for(provider):
    return getattr(settings, "NIPRIX_WEBSITE_WEBHOOK_SECRET", "") if provider == "WEBSITE" else getattr(settings, "NIPRIX_META_WEBHOOK_SECRET", "")


def verify_signature(*, provider, raw_body, signature):
    secret = _secret_for(provider)
    if not secret:
        raise InvalidWebhook("Webhook verification is not configured.")
    if not signature:
        raise InvalidWebhook("Webhook signature is required.")
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise InvalidWebhook("Webhook signature is invalid.")


def _first(payload, *paths):
    for path in paths:
        value = payload
        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit() and len(value) > int(part):
                value = value[int(part)]
            else:
                value = None
            if value is None:
                break
        if value not in (None, ""):
            return value
    return ""


def normalize_payload(provider, payload):
    """Extract a deliberately small canonical shape from provider or local fixtures."""
    canonical = payload.get("lead", payload) if isinstance(payload, dict) else {}
    if not isinstance(canonical, dict):
        raise InvalidWebhook("Webhook payload must be a JSON object.")
    account_id = _first(canonical, "account_id", "page_id", "phone_number_id", "recipient_id")
    if provider == "WHATSAPP":
        account_id = account_id or _first(payload, "entry.0.changes.0.value.metadata.phone_number_id")
        phone = _first(canonical, "phone", "from") or _first(payload, "entry.0.changes.0.value.contacts.0.wa_id")
        message = _first(canonical, "message", "text", "requirement_notes") or _first(payload, "entry.0.changes.0.value.messages.0.text.body")
    elif provider == "INSTAGRAM":
        account_id = account_id or _first(payload, "entry.0.messaging.0.recipient.id")
        phone, message = _first(canonical, "phone"), _first(canonical, "message", "text")
    else:
        phone, message = _first(canonical, "phone"), _first(canonical, "message", "requirement_notes")
    event_id = _first(canonical, "event_id", "id", "message_id") or _first(payload, "entry.0.id")
    external_lead_id = _first(canonical, "external_lead_id", "lead_id", "leadgen_id")
    metadata = canonical.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    known_metadata = {
        key: canonical[key] for key in ("campaign_id", "campaign_name", "ad_id", "ad_name", "ad_set_id", "form_id", "form_name", "landing_page", "utm_source", "utm_medium", "utm_campaign") if canonical.get(key) not in (None, "")
    }
    metadata = {**metadata, **known_metadata}
    return {
        "account_id": str(account_id), "event_id": str(event_id), "external_lead_id": str(external_lead_id),
        "external_contact_id": str(_first(canonical, "external_contact_id", "contact_id")),
        "external_conversation_id": str(_first(canonical, "external_conversation_id", "conversation_id", "message_id")),
        "event_type": str(_first(canonical, "event_type", "type") or "lead.received"),
        "phone": str(phone), "name": str(_first(canonical, "name", "full_name")),
        "email": str(_first(canonical, "email")), "property_type": str(_first(canonical, "property_type")),
        "preferred_location": str(_first(canonical, "preferred_location", "location")),
        "budget_minimum": canonical.get("budget_minimum"), "budget_maximum": canonical.get("budget_maximum", canonical.get("budget")),
        "bhk": str(_first(canonical, "bhk")), "purpose": str(_first(canonical, "purpose")),
        "requirement_notes": str(message), "source_details": str(_first(canonical, "source_details", "landing_page")),
        "metadata": metadata,
    }


def _configuration(provider, account_id):
    if not account_id:
        raise InvalidWebhook("Webhook account identifier is missing.")
    config = IntegrationConfiguration.objects.select_related("company", "branch").filter(
        provider=provider, external_account_id=account_id, is_enabled=True,
    ).first()
    if not config:
        raise InvalidWebhook("Webhook account is not configured.")
    return config


def _idempotency_key(provider, normalized, raw_body):
    return normalized["event_id"] or normalized["external_lead_id"] or hashlib.sha256(provider.encode() + raw_body).hexdigest()


@dataclass
class IntakeResult:
    event: IntegrationEvent
    duplicate: bool


def process_webhook(*, provider, raw_body, payload):
    normalized = normalize_payload(provider, payload)
    config = _configuration(provider, normalized["account_id"])
    key = _idempotency_key(provider, normalized, raw_body)
    try:
        with transaction.atomic():
            event, created = IntegrationEvent.objects.get_or_create(
                company=config.company, provider=provider, idempotency_key=key,
                defaults={
                    "configuration": config, "event_type": normalized["event_type"],
                    "external_event_id": normalized["event_id"], "external_lead_id": normalized["external_lead_id"],
                    "raw_payload": payload,
                },
            )
    except IntegrityError:
        event = IntegrationEvent.objects.get(company=config.company, provider=provider, idempotency_key=key)
        return IntakeResult(event=event, duplicate=True)
    if not created and event.status in (IntegrationEvent.Status.PROCESSED, IntegrationEvent.Status.IGNORED):
        return IntakeResult(event=event, duplicate=True)

    with transaction.atomic():
        event = IntegrationEvent.objects.select_for_update().get(pk=event.pk)
        if event.status in (IntegrationEvent.Status.PROCESSED, IntegrationEvent.Status.IGNORED):
            return IntakeResult(event=event, duplicate=True)
        event.status, event.retry_count, event.error_message = IntegrationEvent.Status.PROCESSING, event.retry_count + (0 if created else 1), ""
        event.save(update_fields=["status", "retry_count", "error_message"])
        if not normalized["phone"]:
            event.status, event.processed_at, event.error_message = IntegrationEvent.Status.IGNORED, timezone.now(), "No reliable phone identity was supplied."
            event.save(update_fields=["status", "processed_at", "error_message"])
            return IntakeResult(event=event, duplicate=False)
        lead_data = {key: value for key, value in normalized.items() if key in {
            "phone", "name", "email", "property_type", "preferred_location", "budget_minimum", "budget_maximum", "bhk", "purpose", "requirement_notes", "source_details",
        }}
        lead_data.update({
            "branch": config.branch, "source": provider, "source_metadata": normalized["metadata"],
            "external_lead_id": normalized["external_lead_id"], "external_contact_id": normalized["external_contact_id"],
            "external_conversation_id": normalized["external_conversation_id"], "received_at": timezone.now(),
        })
        try:
            mutation = create_or_enrich_lead(actor=None, company=config.company, data=lead_data)
        except Exception as error:
            event.status, event.error_message = IntegrationEvent.Status.FAILED, str(error)[:500]
            event.save(update_fields=["status", "error_message"])
            config.status, config.last_failure_at, config.last_failure_message = IntegrationConfiguration.Status.ERROR, timezone.now(), event.error_message
            config.save(update_fields=["status", "last_failure_at", "last_failure_message", "updated_at"])
            raise
        event.lead, event.status, event.processed_at = mutation.lead, IntegrationEvent.Status.PROCESSED, timezone.now()
        event.save(update_fields=["lead", "status", "processed_at"])
        config.status, config.last_success_at, config.last_failure_message = IntegrationConfiguration.Status.CONFIGURED, timezone.now(), ""
        config.save(update_fields=["status", "last_success_at", "last_failure_message", "updated_at"])
        log_lead_activity(
            lead=mutation.lead, actor=None, activity_type="SOURCE_RECEIVED",
            note=f"Lead {'received' if mutation.created else 'enriched'} from {provider}.",
            metadata={"integration_event_id": event.pk, "provider": provider},
        )
        return IntakeResult(event=event, duplicate=False)

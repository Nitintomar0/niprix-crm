# Phase 6 — Lead Integrations and Omnichannel Intake

## Implemented architecture

Phase 6 adds an `integrations` app around the existing Phase 5 Lead domain. Provider-specific webhook views do only boundary work: validate a signed raw request, parse a small provider-neutral payload, resolve a configured external account to a company and branch, create an idempotent `IntegrationEvent`, then call Phase 5 `create_or_enrich_lead`.

No integration view creates a `Lead` directly. Phone normalization, canonical field enrichment, source history, assignment, tenant safety, and activity history remain in the lead service layer.

Supported intake boundaries:

- `POST /api/integrations/webhooks/whatsapp/`
- `POST /api/integrations/webhooks/facebook/`
- `POST /api/integrations/webhooks/instagram/`
- `POST /api/integrations/website/`

Manual intake remains `POST /api/leads/` and continues to use the same lead service.

## Configuration and tenant mapping

`IntegrationConfiguration` maps a provider's external account/page/form/phone-number identifier to one company and active branch. An inbound payload never supplies a company, owner, role, or assignment target. A configuration must be enabled before intake is accepted.

Configuration and health APIs are CEO-only:

- `GET`, `POST /api/integrations/`
- `GET`, `PATCH /api/integrations/{id}/`
- `GET /api/integrations/events/`

The health UI at `/integrations` shows actual configuration, signing-secret presence, last event results, and failed-event counts. It never claims an unconfigured provider is connected and does not return raw payloads, idempotency keys, or secrets.

## Signing and local testing

Every webhook verifies an HMAC SHA-256 over the exact raw body using constant-time comparison. Meta-family providers use `X-Hub-Signature-256`; website intake uses `X-Niprix-Signature-256`.

Local fixture tests use `override_settings` with test-only secrets. There is no DEBUG bypass and no unauthenticated development endpoint. Configure placeholders in `apps/backend/.env`:

```env
NIPRIX_META_WEBHOOK_SECRET=replace-with-meta-webhook-signing-secret
NIPRIX_WEBSITE_WEBHOOK_SECRET=replace-with-website-webhook-signing-secret
```

Actual WhatsApp, Meta/Facebook, and Instagram production connections still require each provider's credentials, verified webhook registration, configured external account identifiers, and operational deployment configuration. This phase does not claim live provider connectivity.

## Events, deduplication, enrichment, and sources

`IntegrationEvent` persists safe raw payload data server-side and tracks `RECEIVED`, `PROCESSING`, `PROCESSED`, `FAILED`, and `IGNORED` states, timestamps, retry count, safe error text, provider external identifiers, and an optional resolved lead.

Database constraints enforce company/provider idempotency keys and, where supplied, external event IDs. Repeated callbacks return an idempotent response without duplicate leads or duplicate integration timeline entries. Failed processing remains visible to CEO users through event health data.

The existing company + normalized-phone lead constraint is still the primary CRM identity guard. Common Indian forms including `+91 98765 43210`, `919876543210`, `09876543210`, and `9876543210` normalize to one identity. Phone stays immutable after lead creation.

When a matching lead is found, incoming non-empty canonical fields can enrich it. Blank/null values never clear existing values. The existing `LeadSource` model preserves multiple sources and provider external IDs; source metadata retains only supplied campaign, form, ad, landing-page, and UTM information.

Phone-less webhook events are retained as `IGNORED`, not converted into unsafe name-only matches or silently discarded.

## Assignment and timeline

New integration leads reuse Phase 5's deterministic, locked company/branch round-robin assignment. Only active, lead-eligible employee profiles participate. With no eligible employee, a valid lead remains unassigned rather than being lost.

Processing writes normal source/field/assignment activity using the existing lead timeline. A duplicate event does not create extra timeline entries.

## Hard deletion

`DELETE /api/leads/{id}/` is now a transactional, real hard delete.

- Employees are denied.
- Managers may delete leads in their existing direct-report scope.
- CEOs may delete company leads.
- Cross-company and out-of-scope paths are not retrievable/deletable.
- Lead activities, source records, and assignment history cascade with the lead because their purpose is intrinsic record history.
- Existing Phase 4 tasks/follow-ups and integration events survive with `lead_id` set to null, preserving their independent operational/audit history without dangling foreign keys.
- `AuditLog` retains only actor, company, target label/identifier, action, and timestamp for `lead.deleted`; no contact details are copied into the deletion audit.

The lead detail UI shows a strong confirmation dialog only for managers and CEOs.

## Limitations and production prerequisites

Webhook processing is synchronous but model/service boundaries are retry-ready through event state and retry count. A production asynchronous worker may later claim and retry `FAILED` events with bounded scheduling; this phase does not add a second queue system or infinite retry loop. PostgreSQL is the intended production database for row-level locking behavior.

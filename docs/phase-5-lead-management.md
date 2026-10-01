# Phase 5 — Lead Management

## Scope

Phase 5 adds the internal, tenant-safe NIPRIX lead-management core. It deliberately does **not** implement WhatsApp Cloud API, Meta/Facebook/Instagram APIs, webhooks, messaging, email/SMS delivery, AI scoring, inventory, or deals.

## Architecture

The `leads` Django app owns canonical lead data and lead-specific history:

- `Lead` holds normalized CRM properties: identity, requirements, ownership, branch, source, status, and temperature.
- `LeadSource` records every source contribution, its external identifiers, received time, and bounded source-specific metadata. Canonical CRM properties are never buried in metadata.
- `LeadActivity` is the immutable timeline for creation, source receipt, field/status/temperature changes, notes, assignments, and linked Phase 4 work.
- `LeadAssignment` retains full ownership history.
- `LeadAssignmentCursor` stores a company-scoped round-robin position under a database lock.

All business operations are in `leads.services`, rather than views or signals. They use transactions for creation/deduplication, enrichment, assignment, reassignment, and activity/audit records.

## Tenant access and roles

Every lead query begins with the authenticated user’s company and never accepts company ownership from the client.

- Employees can see and update only leads assigned to them; they cannot reassign or delete.
- Managers can see their own and direct reports’ assigned leads, and can reassign only inside that scope.
- CEOs can see and update all company leads, reassign within the company, inspect history, and archive records.

Detail, activity, source, assignment, linked task, and linked follow-up paths independently apply this server-side scope. A missing/out-of-scope lead is never returned through search or a URL identifier.

## Phone identity, duplication, and enrichment

Manual creation requires a phone number; all other standard identity and requirement fields are optional. The phone is normalized for common Indian representations (`9876543210`, `+91 9876543210`, and `0919876543210`) and a partial unique database constraint enforces `(company, normalized_phone)` uniqueness.

The original display phone is retained, but normal editing rejects any changed normalized value for every role. The frontend shows the phone as read-only; the API remains authoritative.

Creation is an atomic create-or-enrich operation:

1. Lock an existing company-local normalized-phone match when present.
2. Record its source event.
3. Fill only provided, genuinely changed canonical values.
4. Never replace an existing value with a blank/null incoming value.
5. Record field-level timeline/audit history.

A unique constraint plus retry path prevents two concurrent same-company requests from creating duplicate phones. The same normalized phone is valid in separate companies. Name-only and email-only matching are intentionally not automatic.

## Sources and future integrations

Supported source codes are `WHATSAPP`, `FACEBOOK`, `INSTAGRAM`, `META_LEAD_AD`, `WEBSITE`, `MANUAL`, `REFERRAL`, and `OTHER`. `LeadSource` supports external lead/contact/conversation IDs, source details, metadata, and received time so future integration adapters can call the same `create_or_enrich_lead` operation. No external integration is implemented here.

## Assignment

Automatic assignment considers only active, lead-eligible `EMPLOYEE` profiles in the same company and branch. It skips inactive profiles and uses a locked, deterministic company cursor ordered by profile ID. Managers and CEOs may manually reassign only to an active employee in their permitted scope; every change has assignment and timeline history.

## APIs

- `GET`, `POST /api/leads/` — scoped paginated list and manual/source-aware create-or-enrich.
- `GET`, `PATCH`, `DELETE /api/leads/{id}/` — retrieve/update; delete is CEO-only archive.
- `GET /api/leads/summary/` — scoped KPI cards.
- `POST /api/leads/{id}/assign/`, `/status/`, `/temperature/`.
- `GET`, `POST /api/leads/{id}/activities/` — timeline and notes.
- `GET /api/leads/{id}/sources/`, `/assignments/`.

List filtering supports server-side pagination, search (name, normalized phone, email, ID, location), status, temperature, source, owner, branch, property type, location, date range, and approved ordering.

## Phase 4 integration

`workspace.FollowUp` and `workspace.Task` now have nullable, protected `lead` relations. Creation/update verifies that the referenced lead belongs to the caller’s visible tenant scope, and successful creation adds a lead timeline event. Existing unlinked Phase 4 records continue to work unchanged.

## UI

`/leads` contains role-scoped metrics, server-side filters/search/pagination, and an incomplete-friendly manual creation form. `/leads/{id}` shows overview, immutable contact identity, requirements, assignment/source/history, timeline notes, and linked Phase 4 work. The normal edit form intentionally has no editable phone input.

## Validation and known limits

Phase 5 tests cover scope, cross-company isolation, normalized deduplication/enrichment, immutable phone enforcement for every role, source history, status/temperature history, round robin, reassignment, pagination/filtering, archive behavior, and task/follow-up links.

The project’s existing attendance test module has three clock-sensitive failures when its fixed fixtures are later than the runtime clock; Phase 5 does not modify attendance. PostgreSQL is the production target for the row-locking concurrency guarantees; SQLite’s test database validates the unique constraint and service behavior but does not model all production lock semantics.

# Magicbricks webhook intake

The CRM accepts `POST https://niprix.onrender.com/api/integrations/webhooks/magicbricks/`.
The current implementation expects the server-side API key in the `X-API-Key`
header. Set `NIPRIX_MAGICBRICKS_API_KEY` in the backend service environment;
never place it in the frontend or source control. `NIPRIX_MAX_WEBHOOK_PAYLOAD_BYTES`
defaults to 262144 bytes and bounds accepted JSON bodies.

## Internal readiness diagnostic

`POST /api/integrations/diagnostics/magicbricks/readiness/` accepts the same
`X-API-Key` and returns `200` only when this application's configured-key
comparison succeeds. It does not read a payload or create an integration event,
lead, activity, or configuration record. Missing or invalid keys receive the
same generic `403` response as the webhook.

This endpoint is an internal diagnostic only. A successful response verifies
the application's key-validation path; it does not prove Magicbricks can reach
the service, uses this authentication scheme, or sends a compatible payload.

## Configuration and routing

A CEO must create an enabled `MAGICBRICKS` integration configuration for the
correct company and active branch. Its `external_account_id` must match an
account/integration/project identifier in the incoming payload. That mapping,
not a company ID sent by the caller, selects the tenant. The identifier is
unique per provider, so ambiguous mappings are rejected at configuration time.

## Supported JSON shape

The endpoint accepts a JSON object either at the top level, under `lead`, or
under `data.lead`. The account identifier is read from `account_id`,
`accountId`, `integration_id`, `integrationId`, `project_id`, or `projectId`.
Common lead aliases accepted today include:

- phone: `phone`, `mobile`, `mobile_number`, `mobileNumber`,
  `customer_phone`, `contact_number`
- name: `name`, `full_name`, `customer_name`, `customerName`
- enquiry/event ID: `event_id`, `eventId`, `id`, `enquiry_id`, `enquiryId`,
  `lead_id`, or `leadId`
- requirement: `message`, `requirement_notes`, `requirement`, `remarks`, or
  `enquiry_remarks`
- project/source detail: `source_details`, `project_name`, `projectName`,
  `property_name`, or `propertyName`

Name and email are optional. A usable phone number is the current minimum for
lead creation; an event without one is recorded as `IGNORED`, not converted to
a lead. The original JSON is stored only in the server-side integration event
record and is not returned by the administrator API.

These aliases are defensive compatibility assumptions, not an asserted
Magicbricks contract. Confirm exact field names, stable delivery IDs, response
timeout/retry behaviour, signature/IP requirements, and any verification
handshake with Magicbricks before production rollout.

## Event lifecycle and recovery

Each configured event is deduplicated by provider, company, and an external
event/lead ID (or a body fingerprint when no ID is supplied). Successful
processing creates or enriches the CRM lead through the existing lead service,
then marks the event `PROCESSED`. This preserves the project’s existing
round-robin assignment behaviour when eligible employees exist; the webhook
does not introduce a separate assignment policy.

Lead-mutation failures roll back the lead changes and persist the event as
`FAILED`, including a safe error summary and attempt count. A CEO can inspect
events at `GET /api/integrations/events/?provider=MAGICBRICKS` and explicitly
retry a failed event with `POST /api/integrations/events/<id>/retry/`.

Automatic retry is not enabled: the repository has no configured Celery worker,
broker, or scheduler. If automatic recovery is required, provision and verify
those deployment components, then add bounded backoff and monitoring before
claiming it is operational. Sender-side retry support remains unverified.

## Safe local verification and rollout

Use a fake API key and synthetic phone data only. Create an enabled
Magicbricks configuration, send a small JSON request with `X-API-Key`, then
verify the lead source filter `source=MAGICBRICKS`, event status, branch, and
tenant-scoped CEO event list. Run migrations before deployment. Configure the
public HTTPS route, `ALLOWED_HOSTS`, backend key, body-size limit, and any
reverse proxy so it forwards `X-API-Key` unchanged. Do not send real payloads
or credentials until the external delivery contract has been confirmed.

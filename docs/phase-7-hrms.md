# Phase 7: HRMS and Employee 360

## Architecture

Phase 7 extends `organizations.EmployeeProfile` for presentation and lifecycle data only. Attendance, leads, tasks, and follow-ups remain owned by their Phase 2, 5/6, and 4 applications. The `hrms` application owns company-scoped leave types, per-employee balances, requests, holidays, and document metadata.

## APIs

- `GET /api/employees/{id}/overview/`, `/performance/`, `/attendance/`, and `/activity/` provide employee-scoped operational data.
- `GET|POST /api/hrms/leave-types/`, `GET /api/hrms/leave-balances/`, and `GET|POST /api/hrms/leave-requests/` support leave workflows.
- `POST /api/hrms/leave-requests/{id}/cancel|approve|reject/` performs state changes.
- `GET|POST /api/hrms/holidays/` and detail update/delete are CEO-only mutations.
- Employee documents use an authenticated download endpoint. File storage URLs are deliberately omitted from normal JSON responses.

## Employee directory and 360 workspace

`/employees` is an authorized employee directory with server-side search/status filters and responsive table/card layouts. Selecting a record opens `/employees/{id}`. The Employee 360 workspace lazy-loads attendance, leads, work records, leave requests, and activity only when their tabs are selected. Its overview and performance values are derived from existing CRM records; no duplicate operational tables or fabricated trends are used. The personal-profile drawer supports permitted text fields, photo upload/replacement, and photo removal.

## Permissions and security

Employee scope is centralized in `organizations.services.visible_employee_profiles`: employees see themselves, managers see themselves and direct reports, and CEOs see their company only. The self-service serializer has an explicit allow-list and rejects every other request key to prevent mass assignment. HR balances cannot be client-edited; leave approval locks the request and balance in one transaction. Cross-tenant objects are filtered before any response or mutation.

## Lifecycle and documents

Lifecycle values are Onboarding, Active, Notice Period, Inactive, and Offboarded. Offboarding requires a last working date and never removes historical CRM data. Profile photos accept JPG, PNG, and WebP up to 5 MB. HR documents accept PDF/image/Office formats up to 10 MB and are only downloadable after scope authorization.

## Known limitations / extension points

Current leave duration uses inclusive calendar days; regional working-day and holiday exclusion can be added at the service boundary. Documents use Django storage; production should configure private object storage and malware scanning. Targets are not represented because no existing target engine is present, so the UI does not fabricate target metrics.

## Validation

The Phase 7 security suite covers self-only profile updates, strict rejected mass assignment, manager direct-report scope, cross-company access rejection, overlapping leave prevention, atomic approval/balance updates, CEO-only holiday management, and authenticated document access. Full Django, pytest, frontend lint, frontend production build, Django check, and migration-drift checks are part of the release validation workflow.

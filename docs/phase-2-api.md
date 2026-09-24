# Phase 2 API contract

All endpoints require a JWT bearer token. API permissions are enforced by the
backend; UI visibility must follow the same rules but is not an authorization
mechanism.

## Employees

- `GET /api/employees/` returns the caller's permitted employee scope. CEOs
  receive company scope, managers receive direct reports, and employees receive
  only their own record. Supported filters: `search`, `branch`, `department`,
  `role`, `is_active`, `ordering`, `page`, and `page_size`.
- `POST /api/employees/create/` is CEO-only. The branch and department must
  belong to the CEO's company; the server sets the new user's company.
- `GET /api/employees/{id}/` returns a CEO-scoped record or the caller's own
  record. `PATCH` is CEO-only for management fields; employees can change only
  `phone`, `email`, `first_name`, and `last_name` on their own profile.

When `page` or `page_size` is supplied, list responses use DRF's paginated
shape (`count`, `next`, `previous`, `results`). Without either parameter, the
legacy list response remains an array for Phase 1 compatibility.

## Attendance

- `POST /api/attendance/check-in/` starts the caller's daily session and
  returns `201`. A duplicate active or completed session returns `400`.
- `POST /api/attendance/check-out/` completes the caller's active daily
  session. Checkout without a current check-in returns `400`.
- `GET /api/attendance/current/` returns today's record or
  `{ "status": "NOT_CHECKED_IN" }`.
- `GET /api/attendance/` returns the caller's permitted attendance scope;
  supports `employee`, `branch`, `department`, `date_from`, `date_to`, `page`,
  and `page_size`.
- `POST /api/attendance/{id}/correct/` is CEO-only and requires a `reason`
  plus at least one of `check_in_at` or `check_out_at`. It retains the original
  values in a correction record and emits an audit event.

The application has no global cross-tenant attendance administrator. Django
superusers may use the same correction flow only when their `User.company`
matches the target record; a superuser without company context is denied.

Attendance is a same-day Phase 2 workflow: check-in and check-out timestamps
must fall on `attendance_date`; overnight shifts are not supported. A CEO may
set `check_out_at` to `null` to reopen a record after a correction. The record
then has no working duration and is treated as an active session until it is
checked out again. `workday_end` is retained as policy configuration for future
schedule validation; Phase 2 early checkout is based on `minimum_work_minutes`.

Location relay is intentionally deferred. A future client must request clear
user consent, only relay while an attendance session is active, and avoid
persisting route history or precise locations beyond a documented retention
period.

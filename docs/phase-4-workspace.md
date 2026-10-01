# Phase 4: Follow-ups, tasks, and reminders

`workspace` adds tenant-owned follow-ups, their immutable activity records, tasks, per-user reminder preferences, and prepared reminder events. There is no Lead app yet, so `FollowUp` deliberately has no speculative lead foreign key. A future Lead model can add a nullable, tenant-validated relation in its own migration.

## API

- `GET, POST /api/follow-ups/`; `GET, PATCH, DELETE /api/follow-ups/<id>/`
- `POST /api/follow-ups/<id>/complete/`, `postpone/`, `reassign/`; `GET /activities/`
- `GET, POST /api/tasks/`; `GET, PATCH, DELETE /api/tasks/<id>/`
- `POST /api/tasks/<id>/complete/`, `reassign/`
- `GET /api/workspace/summary/`, `upcoming/`, and `overdue/`
- `GET, PATCH /api/reminder-preferences/`

All list endpoints paginate by default (20, maximum 100) and only support explicit filters. Company, branch, creator, and completion values are server controlled.

## Access and transitions

Employees work only on their assigned records and can only self-assign. Managers access themselves plus direct reports and can assign within that scope. CEOs access active employees in their company. Completed and cancelled work is terminal; completion timestamps are set by services and protected by database constraints. Follow-up activity is appended transactionally with each material change.

## Reminders

`prepare_reminder_events()` creates idempotent, tenant-scoped database events for eligible upcoming follow-ups and overdue tasks. It does **not** send email, WhatsApp, SMS, or push notifications. Celery and Redis packages are present, but this project has no worker/broker/scheduler configuration; invoke that service from a configured periodic worker when infrastructure is approved.

# Project state

## Current phase

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **final corrective implemented, awaiting final acceptance**

PHASE 20 — Flutter client: **accepted / closed** (manual Linux smoke completed by user)

PHASE 19.5 — auth, connections, manual capture: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–20: (prior phases, PHASE 20 closed)
- PHASE 21:
  - Task-proposal Accept → confirmed task (`result_object_id` idempotency); invalid accept → 422
  - `GET /today` with `day_start`, tasks, calendar events, important notifications
  - Terminal task exclusion in SQL before limit; overdue via `due_at < day_start`
  - `GET /notifications?status=unresolved` pseudo-filter
  - Flutter Inbox / Today / Object Detail; dispose-safe async screens
  - Manual capture context from Object Detail; session isolation preserved
  - Backend + client tests; Android debug APK verified
  - VDS deployed at `78aaa28` (Alembic `0015`); live health/notifications/today → 200

## Not done

- PHASE 22 (not started)
- Search UI, Assistant, voice, graph editor

## Next phase

PHASE 22 — not started.

# Current task — Unified Week A / A-R1

## Status

Unified Week A / A-R1:

**CODE ACCEPTED / DEPLOYED / AWAITING HUMAN PRODUCT/UX ACCEPTANCE**

Do **not** mark PRODUCTION ACCEPTED from technical smoke.
Do **not** begin Availability A.

## Production / lineage

- Production application SHA: `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`
- Before this deploy: `4945f19e6f6c134b435066d099d9b84d21612ce2`
- Unified Week A: `e7d1b2086009840ca654a6b920e780220bdf2d58`
- Unified Week A-R1 parent: `e7d1b2086009840ca654a6b920e780220bdf2d58`
- Branch: `review/unified-week-a`
- Role-boundary hygiene included in this production advance
- Inbox Quick Actions — Swipe to Remove A / A-R1: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Design Quality Pass C: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## What A is

Read-only Monday–Sunday projection of already-materialized `google_calendar` and `yandex_calendar` event Objects. Not a third calendar, not a new event store, not Availability/free-busy.

## Out of this phase

Availability / free-busy, conflict warnings, event mutation, tasks/deadlines as occupied time, temporal hints, RRULE expansion, provider sync changes.

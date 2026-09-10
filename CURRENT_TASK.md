# Current task — Unified Week A — Read-only unified calendar projection

## Status

Unified Week A-R1: **implemented / awaiting Architect review** on `review/unified-week-a`.

Client-only temporal correctness: day-local timed-event labels, DST-safe calendar-date arithmetic, failed-week retry. Backend Week projection unchanged.

Do **not** deploy Unified Week A until Architect accepts.
Do **not** begin Availability A.

## Production / lineage

- Production application remains: `4945f19e6f6c134b435066d099d9b84d21612ce2`
- Implementation branch: `review/unified-week-a`
- Role-boundary hygiene base: `a62d204c9fc3b08bbb6b6c3cb5e53aa123828012`
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

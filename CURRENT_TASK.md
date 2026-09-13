# Current task — Pre-Voice UI Corrective A

## Status

**Pre-Voice UI Corrective A: IMPLEMENTED / AWAITING ARCHITECT REVIEW** on `review/pre-voice-ui-corrective-a`.

Not CODE ACCEPTED. Not deployed. Do not start Voice Assistant A.

Canonical base: `review/teams-a` docs tip after the Teams external-blocker transition:

`999f3668468826585e965c27488db2ea49f83cb9`

Teams A remains **CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e`. Alembic **0040 / 0040**. This corrective does not reopen Teams A.

## Scope

Client-only. No DB migration. No backend feature work. No Teams redesign. No Voice A.

1. Inbox wide/tablet timestamp pinned to the right of the usable card header.
2. Consecutive touch swipe-delete of adjacent Inbox items.
3. Phone Week shows three adjacent day columns (kalender 0.29.1 `MultiDayViewConfiguration.custom(numberOfDays: 3)`). Tablet/desktop >= 600dp keep the seven-day Week.

## Stop

Implementation + widget tests + docs are done. Push `review/pre-voice-ui-corrective-a` and wait for Architect review. Do not deploy. Do not start Voice Assistant A.

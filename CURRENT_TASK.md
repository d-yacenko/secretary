# Current task — Pre-Voice UI Corrective A

## Status

**Pre-Voice UI Corrective A: CODE ACCEPTED / MANUALLY VERIFIED** on `review/pre-voice-ui-corrective-a`.

CODE ACCEPTED application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

User manually verified all three fixes:

- Inbox timestamp placement
- consecutive adjacent swipe-delete
- phone Week 3-day presentation

Client-only. No backend/schema changes. No migration. No standalone production server deploy. The accepted client tree remains in the canonical lineage for the next client release.

Voice Assistant A is **unblocked**. Do not start Voice Assistant A in this record.

This ledger transition is docs-only. Do not change application code. Do not deploy docs commits.

Canonical base: `review/teams-a` docs tip after the Teams external-blocker transition:

`999f3668468826585e965c27488db2ea49f83cb9`

Teams A remains **CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e`. Alembic **0040 / 0040**. Production application SHA is unchanged. This corrective does not reopen Teams A.

## Scope (accepted)

1. Inbox wide/tablet timestamp pinned to the right of the usable card header.
2. Consecutive touch swipe-delete of adjacent Inbox items.
3. Phone Week shows three adjacent day columns (kalender 0.29.1 `MultiDayViewConfiguration.custom(numberOfDays: 3)`). Tablet/desktop >= 600dp keep the seven-day Week.

## Stop

Docs-only CODE ACCEPTED / MANUALLY VERIFIED record. Push `review/pre-voice-ui-corrective-a`. Do not deploy. Do not start Voice Assistant A.

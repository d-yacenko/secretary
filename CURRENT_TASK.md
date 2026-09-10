# Current task — Unified Week B — Calendar time-grid

## Status

Unified Week A / A-R1: **CODE ACCEPTED / DEPLOYED / HUMAN UX NOT ACCEPTED** at `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`.

Unified Week B: **in progress** on `review/unified-week-b`.

Do **not** deploy Week B until Architect accepts.
Do **not** begin Availability A.
Do **not** mark Week A PRODUCTION ACCEPTED.

## Production / lineage

- Production application SHA: `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`
- Branch: `review/unified-week-b`
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## Spike (before UI)

Checked `kalender` 0.29.1, `calendar_view`, and Syncfusion as commercial reference.

**Chosen package: `kalender` 0.29.1 (MIT, pinned exact version).**

- 7-day week, Monday start
- start/end positioning, height by duration
- `EventLayoutStrategy.sideBySide()`
- all-day / multi-day header; overnight `<24h` stays on the timeline
- current-time indicator + `initialTimeOfDay`
- phone: `singleDay` + horizontal paging
- tap → existing Object Detail
- provider glyph via custom `tileBuilder` (no library fork)
- read-only: `CalendarInteraction` all false + `EventInteraction.allowNone()`

`calendar_view`: weaker overnight/date handling — not used.
`syncfusion_flutter_calendar`: commercial/community license — not used in this OSS repo.

Adapter: `/week` repeats an Object on every overlapping local day. Feed kalender each Object **once** with original `startAt`/`dueAt`.

## What B is

Read-only week **calendar time-grid** over the existing `/week` projection. Not a new calendar store. Not Availability.

## Out of this phase

Availability / free-busy, calendar/provider mutation, swipe-delete, new capture/editing flows, custom time-grid engine.

## After this cycle

**Do not deploy.** Stop for Architect review of Week B.

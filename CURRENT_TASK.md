# Current task — Unified Week B-R1 — Overlap, bookmarks, copy contract

## Status

Unified Week A / A-R1: **CODE ACCEPTED / DEPLOYED / HUMAN UX NOT ACCEPTED** at `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`.

Unified Week B: code at `14cd6b86f5fddb7c0d5fc669950afe9453e069f5`.

Unified Week B-R1: **implemented / awaiting Architect review** on `review/unified-week-b` (not deployed).

Do **not** deploy Week B / B-R1 until Architect accepts.
Do **not** begin Availability A.
Do **not** mark Week A or Week B PRODUCTION ACCEPTED.

## Production / lineage

- Production application SHA: `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`
- Branch: `review/unified-week-b`
- Parent of B-R1: `860076de012a5911e84ce9eb86bd3fdf129ba3d1`
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched
- kalender pin: **0.29.1** (exact)

## What B-R1 is

Read-only visual/correctness corrective on the kalender week grid: overlap layout, display-only bookmark markers, copyWithData isAllDay.

Depth hue variation is **deferred**: kalender 0.29.1 does not expose stable overlap depth to tileBuilder.

## Out of this phase

Availability / free-busy, calendar/provider mutation, custom overlap engine, label strips on tiles, deploy.

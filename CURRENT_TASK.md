# Current task — Temporal Signals A — exact-time hints + calendar-first dedup + Week projection

## Status

Temporal Signals A: **implemented / awaiting Architect review** on `review/temporal-signals-a` (not deployed).

Checkpoints on the same branch:

- A1 `bd51f01` — extraction / persistence / dedup / reconciliation / settings / tests
- A2 — Week API + Flutter presentation / tests

Do **not** deploy this phase.
Do **not** enable `temporal_signals_enabled` on production.
Do **not** run historical backfill.
Do **not** begin Temporal Signals B, Availability, Recurring Calendar Actions, Scheduled Work, or Telegram.

Unified Week B-R7 is the production base of this phase at `99658a6f893483317dcecaf15d886cd1ed8d692b`.

## Production / lineage

- Production application SHA: `99658a6f893483317dcecaf15d886cd1ed8d692b`
- Review branch: `review/temporal-signals-a`
- Merge-base with production: `99658a6f893483317dcecaf15d886cd1ed8d692b`
- Alembic: review **0035**; production remains **0034** until Architect deploys
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- `temporal_signals_enabled` default **FALSE** (no silent opt-in)
- Encrypted Architect context: untouched
- kalender pin: **0.29.1** (exact)

## What Temporal Signals A is

Exact DATE + exact START TIME temporal hints from already ingested Gmail / Yandex Mail / Mattermost sources.

Hints are derived Secretary Objects (`kind=temporal_hint`). They are visible on Week, are not busy time, do not mutate providers, and do not become tasks or calendar events.

Calendar remains the visual authority when a high-confidence semantic match exists.

## Out of this phase

Approximate time, date-only hints, Availability / free-busy, scheduled work, task projection onto Week, accepting a hint into a calendar event, provider mutation, Telegram, native notifications, historical backfill, production enable, deploy.

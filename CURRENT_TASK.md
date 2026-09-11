# Current task — Temporal Signals A-R1 — revision-aware source evidence

## Status

Temporal Signals A at `3bcf0f94ff138df900615f130bacd04dc1afaa32` is **NOT YET ARCHITECT-ACCEPTED**.

A-R1: **implemented / awaiting Architect review** on `review/temporal-signals-a` (not deployed).

Do **not** deploy this phase.
Do **not** enable `temporal_signals_enabled` on production.
Do **not** run historical backfill.
Do **not** begin Temporal Signals B, Availability, Recurring Calendar Actions, Scheduled Work, or Telegram.

## Production / lineage

- Production application SHA: `99658a6f893483317dcecaf15d886cd1ed8d692b`
- Review branch: `review/temporal-signals-a`
- A parent: `3bcf0f94ff138df900615f130bacd04dc1afaa32`
- Alembic: review **0035** (unchanged); production remains **0034** until Architect deploys
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- `temporal_signals_enabled` default **FALSE**
- Encrypted Architect context: untouched
- kalender pin: **0.29.1** (exact)
- Flutter / Week API contract: **unchanged / inherited from A2**

## What A-R1 is

Corrective: temporal evidence is idempotent per source revision/signature, not merely per source Object id.

Mattermost in-place edits that enqueue a new `embed_object` re-evaluate Temporal Signals. Stale evidence from a previous signature cannot keep an unresolved Week hint alive.

## Out of this phase

Approximate time, date-only hints, Availability / free-busy, scheduled work, accepting a hint into a calendar event, provider mutation, Telegram, historical backfill, production enable, deploy, Week visual redesign.

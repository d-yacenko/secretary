# Current task — Temporal Signals A / A-R1

## Status

**Temporal Signals A / A-R1: implemented / awaiting Architect review** on `review/temporal-signals-a` (not deployed).

Temporal Signals A at `3bcf0f94ff138df900615f130bacd04dc1afaa32` is **NOT YET ARCHITECT-ACCEPTED**.

Do **not** deploy this phase.
Do **not** enable `temporal_signals_enabled` on production.
Do **not** run historical backfill.
Do **not** begin Temporal Signals B, Availability, Recurring Calendar Actions, Scheduled Work, or Telegram.

## Production / lineage

- Production application SHA: `99658a6f893483317dcecaf15d886cd1ed8d692b`
- Review branch: `review/temporal-signals-a`
- A parent: `3bcf0f94ff138df900615f130bacd04dc1afaa32`
- Alembic: review **0035** (unchanged); production remains **0034** until Architect deploys
- Android `minSdk`: **23** (source, merged manifest, APK)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- `temporal_signals_enabled` default **FALSE**
- Encrypted Architect context: untouched
- kalender pin: **0.29.1** (exact)

## What A-R1 is

Narrow correctness corrective on Temporal Signals A:

- calendar reconcile `event_signature` fence before/after the judge
- source-revision-aware temporal evidence (`source_signature` + `extractor_version`)
- no lossy pending-job cap; signature idempotency kept
- fail-closed exact local times (source reference required; reject nonexistent/ambiguous DST)
- extract from bounded source title/body; semantic summary is supporting context only
- low reasoning/verbosity Temporal model profile; max 1 extract + 1 match per source revision; one late-calendar reconcile judge; AI-audit operations `temporal_extract` / `temporal_match` / `temporal_reconcile_match`
- Week empty state includes hints; `/week` does not project hints when the opt-in is off

## Out of this phase

Approximate time, date-only hints, Availability / free-busy, scheduled work, accepting a hint into a calendar event, provider mutation, Telegram, historical backfill, production enable, deploy, OpenAI cost audit / model selection, Week visual redesign.

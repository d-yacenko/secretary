# Current task — Temporal Signals A / A-R2

## Status

**Temporal Signals A / A-R2: implemented / awaiting Architect review** on `review/temporal-signals-a` (not deployed).

Temporal Signals A is **NOT YET ARCHITECT-ACCEPTED**.

Do **not** deploy this phase.
Do **not** enable `temporal_signals_enabled` on production.
Do **not** run historical backfill.
Do **not** begin Temporal Signals B, Availability, Recurring Calendar Actions, Scheduled Work, or Telegram.

## Production / lineage

- Production application SHA: `99658a6f893483317dcecaf15d886cd1ed8d692b`
- Review branch: `review/temporal-signals-a`
- A-R1 parent: `a6cbe55869f7e04ea1a6dfb73eeb334dba7817dc`
- Alembic: review **0035** (unchanged); production remains **0034** until Architect deploys
- Android `minSdk`: **23** (inherited unchanged from A-R1)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- `temporal_signals_enabled` default **FALSE**
- Encrypted Architect context: untouched
- kalender pin: **0.29.1** (exact)

## What A-R2 is

Late-calendar reconciliation copies `temporal_evidence` using the active hint evidence edge's `source_signature` and `extractor_version`. It does not recompute the current mutable source Object signature. An unprocessed source revision B cannot become calendar evidence until that revision itself completes Temporal extraction.

## Out of this phase

Approximate time, date-only hints, Availability / free-busy, scheduled work, accepting a hint into a calendar event, provider mutation, Telegram, historical backfill, production enable, deploy, OpenAI model selection, Week visual redesign.

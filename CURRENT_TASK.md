# Current task — OpenAI Cost Guard C — per-user daily OpenAI token hard cap

## Status

**OpenAI Cost Guard C: implemented / awaiting Architect review**

Branch: `hotfix/openai-cost-guard-c`
Exact base / parent: `cefe358063095d6d11a63e753f910c7b146851a1`
Production application SHA remains: `04f20f21d5460c9901d811ebd53863a370f85eda`
Alembic in this branch: **0036 / 0036** (`user_settings.openai_daily_token_limit`)
Production Alembic until deploy: **0035 / 0035**

Do **not** deploy this phase.
Do **not** merge/rebase Temporal Signals A; its unpublished 0035 still conflicts with production 0035 and will be renumbered later.
Do **not** enable `temporal_signals_enabled`.
Do **not** begin Cost Guard D.
Do **not** add dollar pricing, anomaly detection, percentage warnings, per-workload limits, or historical backfill.

## Production / lineage

- Production application SHA: `04f20f21d5460c9901d811ebd53863a370f85eda`
- Cost Guard B: **CLOSED / PRODUCTION ACCEPTED** at that SHA
- Cost Guard A: **CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED** at `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Encrypted Architect context: untouched

## What C does

Per-user nullable `openai_daily_token_limit`. NULL disables the fuse. Otherwise a positive integer cap of actual OpenAI tokens per the user's local calendar day.

Once today's actual usage from AI audit (`input_tokens + output_tokens` on `model_round` / `model_round_failed`) reaches the cap:

- no further paid OpenAI API calls for that user
- interactive Assistant returns typed `openai_daily_budget_exhausted` (HTTP 429) with `reset_at`
- Flutter Account shows usage and the exhausted message; Assistant/voice render the local message, not a generic network error
- ordinary Inbox / Today / Week / Search / profile / objects continue
- background AI jobs park until local-day reset (or until the user raises/clears the limit); source sync continues
- at most one user-visible warning notification per local day

## Out of this phase

Cost Guard D, Temporal Signals, dollar pricing, model-specific monetary budgets, anomaly detection, 80% warnings, separate per-workload limits, adaptive budgets, historical backfill, automatic model downgrade, source cadence changes, Yandex changing-signature investigation.

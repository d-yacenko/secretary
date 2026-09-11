# Current task — OpenAI Cost Guard A — correlation revision idempotency

## Status

**OpenAI Cost Guard A: implemented / awaiting Architect review** on `hotfix/openai-cost-guard-a` (not deployed).

Do **not** deploy until Architect review.
Do **not** merge/rebase Temporal Signals A.
Do **not** enable `temporal_signals_enabled`.
Do **not** change the user's assistant model.
Do **not** redesign Google/Yandex sync.
Do **not** solve general embedding churn.
Do **not** touch Flutter.

## Production / lineage

- Production application SHA: `99658a6f893483317dcecaf15d886cd1ed8d692b`
- Branch: `hotfix/openai-cost-guard-a` (exact parent = production)
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23** (untouched)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## What Cost Guard A is

Job-level `correlation_input_signature` following the auto-label pattern. PENDING/RUNNING/DONE for the same object + signature is idempotent. Stale jobs do not call the model. Background correlation uses explicit LOW reasoning / LOW verbosity and keeps the effective assistant model (`gpt-5.6-luna` on production). The judge may return at most 5 strongest decisions. Permanent OpenAI quota exhaustion does not burn three retries on non-recurring AI jobs.

## Out of this phase

Temporal merge, deploy, assistant model change, Google/Yandex sync rewrite, embedding churn, Flutter, Availability, historical backfill.

# Current task — OpenAI Cost Guard B — embedding revision idempotency

## Status

**OpenAI Cost Guard B: implemented / awaiting Architect review** on `hotfix/openai-cost-guard-b` (not deployed).

Do **not** deploy until Architect review.
Do **not** merge/rebase Temporal Signals A.
Do **not** enable `temporal_signals_enabled`.
Do **not** change the user's assistant model.
Do **not** change source sync intervals.
Do **not** begin a general token/cost circuit breaker.
Do **not** backfill embeddings.
Do **not** touch Flutter.

## Production / lineage

- Production application SHA: `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Branch: `hotfix/openai-cost-guard-b` (exact parent = production)
- Cost Guard A: **CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED** at `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23** (untouched)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## Production evidence (Cost Guard A live-credit window)

Observed `2026-09-11T18:32:10.305527Z` through `2026-09-11T19:05:00.089588Z`:

- Embedding: 403 successful API calls / 28 distinct objects (yandex_calendar/event 400/25; mattermost/chat_message 3/3); 119,106 embedding input tokens
- Correlation: 25 model calls / 25 objects (all Yandex events); no object had >1 correlation model call; ~375 duplicate correlation enqueues suppressed by Cost Guard A

Correlation runaway is fixed. Remaining observed runaway is object-level embedding churn.

## What Cost Guard B is

Canonical object embedding input (`EMBEDDING_INPUT_VERSION` + effective embedding model + exact canonical text). Semantic metadata allowlist only; provider housekeeping is excluded. `embed_object` jobs carry `embedding_input_signature`. PENDING/RUNNING/DONE for the same object + signature is idempotent. Unsigned/stale jobs make zero paid embedding calls and ensure one current signed job. A DONE current-signature job plus `Object.embedding` is durable proof. Correlation and auto-label stay independent of whether a new paid embedding API call happened.

## Out of this phase

Temporal merge, deploy, assistant model change, sync interval change, general token/cost circuit breaker, embedding backfill, Flutter.

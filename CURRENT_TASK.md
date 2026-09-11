# Current task — OpenAI Cost Guard B-R1 — embedding proof/recovery + downstream ordering

## Status

**OpenAI Cost Guard B-R1: corrected / awaiting Architect review** on `hotfix/openai-cost-guard-b` (not deployed).

Do **not** deploy until Architect review.
Do **not** merge/rebase Temporal Signals A.
Do **not** enable `temporal_signals_enabled`.
Do **not** change the user's assistant model.
Do **not** change source sync intervals.
Do **not** begin Cost Guard C / a general token/cost circuit breaker.
Do **not** backfill embeddings.
Do **not** touch Flutter.

## Production / lineage

- Production application SHA: `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Cost Guard B accepted implementation: `1dd5aab3c67adfceb58f9561146a7d029d956371`
- Branch: `hotfix/openai-cost-guard-b` (B-R1 parent = Cost Guard B SHA above)
- Cost Guard A: **CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED** at `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23** (untouched)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## What Cost Guard B-R1 is

DONE is embedding proof only when the current signature matches **and** `Object.embedding` is present. DONE + missing vector enqueues exactly one recovery signed job; PENDING/RUNNING recovery collapses repeats; historical DONE jobs are kept; FAILED is never proof.

Unsigned/stale `embed_object` jobs only ensure the current signed job and return. They do not independently enqueue correlation/auto-label. Cheap downstream signature checks run from `enqueue_embed_object` only when current DONE + vector proof exists, or after the current signed job has stored the object embedding.

## Out of this phase

Temporal merge, deploy, assistant model change, sync interval change, Cost Guard C, embedding backfill, Flutter.

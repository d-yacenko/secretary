# Current task — OpenAI Cost Guard B-R2 — bind stored vector to exact embedding revision

## Status

**OpenAI Cost Guard B-R2: corrected / awaiting Architect review** on `hotfix/openai-cost-guard-b` (not deployed).

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
- Cost Guard B-R1: `547a96b61ec051fd65c1dbb9d004faa0f3378ead` (CLOSED)
- Branch: `hotfix/openai-cost-guard-b` (B-R2 exact parent = B-R1 SHA above)
- Cost Guard A: **CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED** at `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
- Alembic: **0035 / 0035** (`objects.embedding_signature`; production was 0034)
- Android `minSdk`: **23** (untouched)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## What Cost Guard B-R2 is

The vector currently stored on `Object` has Secretary-owned provenance: nullable `Object.embedding_signature` updated atomically with the vector. Proof of a current paid embedding is `Object.embedding IS NOT NULL` AND `Object.embedding_signature == current embedding_input_signature`. Historical DONE jobs are history/dedupe only. Post-call revision fence discards a stale vector if the object revision changed during the provider call.

## Out of this phase

Temporal merge, deploy, assistant model change, sync interval change, Cost Guard C, embedding backfill, Flutter.

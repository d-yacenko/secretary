# Current task — OpenAI Cost Guard B-R3 — close synchronous embedding idempotency bypass

## Status

**OpenAI Cost Guard B-R3: corrected / awaiting Architect review** on `hotfix/openai-cost-guard-b` (not deployed).

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
- Cost Guard B-R2: `b11e373704a8aa0b20716142a5139229921154f5` (ACCEPTED: provenance + ABA + post-call fence)
- Branch: `hotfix/openai-cost-guard-b` (B-R3 exact parent = B-R2 SHA above)
- Cost Guard A: **CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED** at `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
- Alembic: **0035 / 0035** (`objects.embedding_signature`; production was 0034)
- Android `minSdk`: **23** (untouched)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched

## What Cost Guard B-R3 is

Synchronous `refresh_object_embedding()` (GraphService request paths) does not call the embedding provider when `Object.embedding` already has Secretary-owned provenance for the current `embedding_input_signature`. Request-time embedding remains synchronous. B-R2 post-call fence is unchanged.

## Out of this phase

Temporal merge, deploy, assistant model change, sync interval change, Cost Guard C, embedding backfill, Flutter.

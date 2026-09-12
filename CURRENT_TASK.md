# Current task — OpenAI Cost Guard B — CLOSED / PRODUCTION ACCEPTED

## Status

**OpenAI Cost Guard B: CLOSED / PRODUCTION ACCEPTED**

Production application SHA: `04f20f21d5460c9901d811ebd53863a370f85eda`
Alembic: **0035 / 0035** (`objects.embedding_signature`)

Do **not** merge/rebase Temporal Signals A until it is renumbered off production 0035.
Do **not** enable `temporal_signals_enabled`.
Do **not** change the user's assistant model.
Do **not** change source sync intervals.
Do **not** begin Cost Guard C.
Do **not** backfill embeddings.
Do **not** reopen Cost Guard B for the single changing-signature Yandex event.
Do **not** touch Flutter.

## Production / lineage

- Production application SHA: `04f20f21d5460c9901d811ebd53863a370f85eda`
- Previous production: `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Cost Guard A: **CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED** at `f20a68256b2a3061a4aaf9143893d7187a90a3d3`
- Temporal Signals A accepted head (not merged): `a9dc8c9c9e74dc4b8857fface89e803f493d21fd`
  - Its unpublished 0035 now conflicts with production 0035 and must be rebased/renumbered before any future Temporal deploy
- Alembic: **0035 / 0035**
- Android `minSdk`: **23** (untouched)
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Effective assistant model: **gpt-5.6-luna**
- Encrypted Architect context: untouched

## Post-deploy evidence (`2026-09-11T20:42:32Z`–`2026-09-11T21:15:24Z`, ~32m52s)

- pre-B Yandex embeddings: 400 calls / 25 objects
- post-B Yandex embeddings: 51 calls / 25 objects
- 24 objects: exactly 1 call (lazy provenance establishment)
- 1 object: 27 calls with 27 distinct `embedding_input_signature` values (NONBLOCKING connector / canonicalization debt; not Cost Guard B)
- 382 unsigned legacy embed jobs: zero paid embedding calls
- correlation model calls: 0
- all 25 touched Yandex objects ended with vector + `embedding_signature`
- final 15 minutes: remaining embedding activity only from the one changing-signature object

## Out of this phase

Temporal merge/renumber, Cost Guard C, embedding backfill, Flutter, assistant model change, sync interval change, investigation of the single changing-signature Yandex event.

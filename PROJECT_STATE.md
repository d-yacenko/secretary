# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- Live smoke: health 200, Alembic `0017`, Russian + simple FTS/trigram indexes present, retrieval NL phrase OK (`relaxed`), Assistant OpenAI HTTP 200 (~18s), Nornickel hits without newsletter/Linux noise

## Working components

- PHASE 22.5A + 22.5B (closed)
- PHASE 22.5C (closed):
  - Migration `0017` Russian FTS GIN index (additive)
  - Strict → relaxed retrieval; bounded atoms with non-generic preference; weak-strict / relaxed quota split
  - Term-aware ranking; Assistant concise retrieve guidance; telemetry (`retrieval_mode`, atom counts)
  - `ContextService` SQL-limited neighbors

## Next phase

PHASE 23 voice — **not started**

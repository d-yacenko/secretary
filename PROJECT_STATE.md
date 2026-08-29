# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **implemented, awaiting review**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `ab568105ff81316cb58b538970fabcc2abe35833`
- Deployed: 2026-08-29
- Live smoke: health 200, Alembic `0016`, retrieval indexes present, Search 200, Assistant OpenAI smoke 200 (~13.2s), `time_scope=all` retrieve OK
- **PHASE 22.5C not deployed** — production remains on `ab56810` until review

## Working components

- PHASE 22.5A + 22.5B (closed):
  - `Object.occurred_at`, migration `0016`, PostgreSQL FTS/trigram indexes
  - `RetrievalService` two-stage candidates, progressive horizons, match quality vs ranking
  - Assistant `retrieve` tool (max 5 hits), no `search_objects` in OpenAI tools
  - References cap 8, turn telemetry, multi-round OpenAI usage accumulation
- PHASE 22.5C (awaiting review):
  - Migration `0017` Russian FTS GIN index (additive; `simple` index retained)
  - Strict retrieval + bounded relaxed fallback with query atoms and selectivity heuristic
  - Russian/simple/trigram per-atom candidate channels; term-aware ranking
  - Assistant retrieve guidance strengthened; telemetry adds `retrieval_mode`, atom counts
  - `ContextService` uses SQL-limited `get_neighbors(limit=MAX_NEIGHBORS)`

## Next phase

PHASE 23 voice — **not started**

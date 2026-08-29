# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `ab568105ff81316cb58b538970fabcc2abe35833`
- Deployed: 2026-08-29
- Live smoke: health 200, Alembic `0016`, retrieval indexes present, Search 200, Assistant OpenAI smoke 200 (~13.2s), `time_scope=all` retrieve OK

## Working components

- PHASE 22.5A + 22.5B (closed):
  - `Object.occurred_at`, migration `0016`, PostgreSQL FTS/trigram indexes
  - `RetrievalService` two-stage candidates, progressive horizons, match quality vs ranking
  - Assistant `retrieve` tool (max 5 hits), no `search_objects` in OpenAI tools
  - References cap 8, turn telemetry, multi-round OpenAI usage accumulation

## Next phase

PHASE 23 voice — **not started**

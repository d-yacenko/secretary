# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **implemented, awaiting review**

PHASE 23 — voice: **not started**

PHASE 22 — Search and Assistant UI: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–22.5A: (prior phases, 22.5A closed)
- PHASE 22.5B (awaiting review):
  - Assistant tool `retrieve` via `RetrievalService` (max 5 hits, compact output)
  - `search_objects` retained for MCP/internal; removed from OpenAI Assistant tools
  - References capped at 8; bounded retrieve hits only (no candidate pool exposure)
  - Turn telemetry logging (counts/metrics only, no content)
  - Nornickel retrieve → get_context → create_task regression with fake provider
  - `pytest` 440 passed; `ruff check .` passes
  - Flutter analyze/test/debug APK build pass
  - VDS deploy deferred

## Not done

- PHASE 23 voice
- Graph editor, persistent assistant chat DB

## Next phase

PHASE 22.5B review. PHASE 23 not started.

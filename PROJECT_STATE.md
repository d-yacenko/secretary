# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 22.6 — Task Materialization, Reuse & Evidence Binding: **implemented, awaiting review**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- Live smoke: health 200, Alembic `0017`, Russian + simple FTS/trigram indexes present, retrieval NL phrase OK (`relaxed`), Assistant OpenAI HTTP 200 (~18s), Nornickel hits without newsletter/Linux noise
- **PHASE 22.6 not deployed** — awaiting review

## Working components

- PHASE 22.5A + 22.5B + 22.5C (closed)
- PHASE 22.6 (awaiting review):
  - `kind=task` taxonomy decision recorded (`todo_item` reserved for future provider todos)
  - Retrieval hits expose `state` / `status` for Assistant duplicate checks
  - `create_task` / `update_task` accept `evidence_object_ids` (max 8); structural `references` edges
  - Assistant instructions: reuse existing non-terminal tasks; explicit «создай новую» override
  - Tests: evidence edges, reuse flow, explicit duplicate creation, taxonomy guard

## Next phase

PHASE 23 voice — **not started**

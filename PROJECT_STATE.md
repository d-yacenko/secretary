# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 22.6 — Task Materialization, Reuse & Evidence Binding: **closure corrective implemented, awaiting final acceptance**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- Live smoke: health 200, Alembic `0017`, Russian + simple FTS/trigram indexes present, retrieval NL phrase OK (`relaxed`), Assistant OpenAI HTTP 200 (~18s), Nornickel hits without newsletter/Linux noise
- **PHASE 22.6 not deployed** — awaiting final acceptance

## Working components

- PHASE 22.5A + 22.5B + 22.5C (closed)
- PHASE 22.6 closure corrective (awaiting final acceptance):
  - Per-turn evidence allowlist in Assistant tool runner (`seen_object_ids`)
  - `update_task` reports `changed` / `evidence_edges_created`; affected_objects only on real change
  - No embed job for evidence-only updates or no-ops
  - Self-reference rejected on `update_task`
  - Terminal task status guidance in Assistant instructions

## Next phase

PHASE 23 voice — **not started**

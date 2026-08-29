# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 22.6 — Task Materialization, Reuse & Evidence Binding: **final provenance closure implemented, awaiting acceptance**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- **PHASE 22.6 not deployed** — awaiting acceptance

## Working components

- PHASE 22.5A + 22.5B + 22.5C (closed)
- PHASE 22.6 final provenance closure (awaiting acceptance):
  - `serialize_tool_output_for_assistant`: single model-visible JSON + payload
  - Evidence allowlist from exact model-visible output (not intermediate bounded)
  - `UiContextResult`: exposed IDs only if present in final truncated UI context text
  - `update_task` effective field comparison; embed only on real field changes

## Next phase

PHASE 23 voice — **not started**

# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **accepted / closed**

PHASE 22.6 — Task Materialization, Reuse & Evidence Binding: **accepted / closed** (`a1bcb90`)

PHASE 22.7 — Assistant Cost & Latency Optimization: **implemented, awaiting review**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `4607a1800ab2058c62f69b111d00871a48a5d0fb`
- Deployed: 2026-08-29
- **PHASE 22.7 not deployed** — awaiting review

## PHASE 22.7 baseline note

VDS `assistant_turn` logs were not available from the local development environment during implementation. Baseline token/tool-call metrics from the recent testing period could not be recorded here. Continue measuring cost via extended `assistant_turn` telemetry after deploy.

## Working components

- PHASE 22.6 (closed at `a1bcb90`)
- PHASE 22.7 (awaiting review):
  - Separate `OPENAI_ASSISTANT_*` settings (default Luna / low / low / 1600)
  - Explicit Responses profile on every round (`store=False` preserved)
  - Extended usage telemetry (cached, cache_write, reasoning, responses_rounds)
  - `max_output_tokens` incomplete → controlled provider failure (no auto-retry)

## Next phase

PHASE 23 voice — **not started**

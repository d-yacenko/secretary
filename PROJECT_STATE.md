# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **final corrective implemented, awaiting acceptance**

PHASE 23 — voice: **not started**

## Working components

- PHASE 22.5B (awaiting acceptance):
  - Assistant `retrieve` tool (max 5 hits, compact output without candidate_count to model)
  - Multi-round OpenAI usage accumulation across all Responses calls
  - OpenAI provider nornickel multi-round regression (fake Responses API)
  - References cap 8; turn telemetry reads candidate_count from raw tool output only
  - `pytest` passing; VDS deploy deferred

## Next phase

PHASE 22.5B acceptance. PHASE 23 not started.

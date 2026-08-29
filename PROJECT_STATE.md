# Project state

## Current phase

PHASE 22.5A — Local Retrieval Foundation: **accepted / closed**

PHASE 22.5B — Assistant Retrieval Integration: **accepted / closed**

PHASE 22.5C — Natural-language Retrieval Recall: **closure corrective implemented, awaiting acceptance**

PHASE 23 — voice: **not started**

## VDS production

- SHA: `ab568105ff81316cb58b538970fabcc2abe35833`
- Deployed: 2026-08-29
- **PHASE 22.5C not deployed** — production remains on `ab56810` until acceptance

## Working components

- PHASE 22.5A + 22.5B (closed)
- PHASE 22.5C (awaiting acceptance):
  - Migration `0017` Russian FTS GIN index (additive)
  - Strict → relaxed retrieval with bounded query atoms and selectivity probes
  - Closure corrective: non-generic atoms survive long NL prefixes; weak-strict / relaxed quota split
  - Assistant concise retrieve guidance; telemetry atom counts
  - `ContextService` SQL-limited neighbors (`TODO` in `DECISIONS.md` for future graph priority SQL)

## Next phase

PHASE 23 voice — **not started**

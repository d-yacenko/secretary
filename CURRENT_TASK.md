# Current task — PHASE 22.5C awaiting review

## Status

PHASE 22.5A and PHASE 22.5B accepted / closed.

PHASE 22.5C Natural-language Retrieval Recall implemented locally:

- strict + relaxed retrieval with Russian morphology channel (`0017`)
- query atoms, selectivity heuristic, term-aware ranking
- Search/Assistant share `RetrievalService`; NL Nornickel regressions added
- `pytest` + `ruff` green locally

Production remains on `ab568105ff81316cb58b538970fabcc2abe35833` until review.

PHASE 23 not started.

## STOP

Do not deploy PHASE 22.5C or start PHASE 23 until explicitly requested.

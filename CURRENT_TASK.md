# Current task — PHASE 22.5C closure corrective

## Status

PHASE 22.5A and PHASE 22.5B accepted / closed.

PHASE 22.5C closure corrective implemented locally:

- atom extraction scans bounded tokens, prefers non-generic terms (`норникелю` survives long NL)
- weak-strict fallback reserves bounded capacity for relaxed candidates (50/50 split)
- regressions for exact live NL phrase and strict-pool starvation
- `pytest` (456 passed) + `ruff` green

Production remains on `ab568105ff81316cb58b538970fabcc2abe35833`.

PHASE 23 not started. Do not deploy.

## STOP

Await acceptance before deploy or PHASE 23.

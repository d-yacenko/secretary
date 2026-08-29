# Current task — PHASE 22 final corrective

## Status

PHASE 22 final corrective implemented. STOP for acceptance.

PHASE 21 accepted / closed. PHASE 23 not started. VDS deploy deferred.

## Delivered (two-fix corrective)

- `get_neighbors(limit=…)`: SQL union with `LIMIT`, no bulk edge materialization
- `sanitize_canonical_uri_for_assistant`: fail-closed; strips credentials; omits query/fragment

## STOP

Await PHASE 22 acceptance. Do not start PHASE 23. Do not deploy to VDS yet.

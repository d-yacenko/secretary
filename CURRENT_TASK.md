# Current task — PHASE 22 final security/boundedness corrective

## Status

PHASE 22 final security/boundedness corrective implemented. STOP for final acceptance.

PHASE 21 accepted / closed. PHASE 23 not started. VDS deploy deferred.

## Delivered (this corrective)

- `sanitize_canonical_uri_for_assistant`: strip credentials, omit unsafe/local URIs
- Assistant tool arg clamping (`tool_args.py`) before domain execution
- Bounded `list_neighbors` query path (`limit` on graph neighbors)
- Reference IDs from bounded tool view only; cap `MAX_ASSISTANT_REFERENCES = 20`
- Assistant `get_context` OpenAI tool: `object_id` required, no `query`, max_chars ≤ 8000
- Regression tests for URI safety, execution bounds, references, get_context contract

## STOP

Await PHASE 22 final acceptance. Do not start PHASE 23. Do not deploy to VDS yet.

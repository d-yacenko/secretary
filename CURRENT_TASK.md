# Current task — PHASE 22 final corrective

## Status

PHASE 22 final corrective implemented. STOP for final acceptance.

PHASE 21 accepted / closed. PHASE 23 not started. VDS deploy deferred.

## Delivered (corrective)

- Global per-turn tool-call budget (`PerTurnToolBudget`, limit 5)
- `run_assistant_tool`: isolated session, commit/rollback per tool result
- Assistant `create_task` / `update_task`: defer write embeddings, enqueue `embed_object`
- Bounded Assistant tool JSON for model (`tool_output.py`)
- UI context in Responses input as delimited evidence; untrusted-data rule in system instructions
- Flutter: `AssistantChatMessage.affectedObjects`, Proposed changes UI
- Test isolation fixes (provenance context, HTTP search, embedding jobs)
- Full verification green: pytest, ruff, flutter analyze/test/build

## STOP

Await PHASE 22 final acceptance. Do not start PHASE 23. Do not deploy to VDS yet.

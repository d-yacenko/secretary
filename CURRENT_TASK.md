# Current task — PHASE 10

## Goal

Give the Secretary a small stable tool vocabulary.

## Do

Implement domain tools (not raw DB):

- `search_objects`, `get_object`, `get_context`, `create_task`, `update_task`, `link_objects`, `list_neighbors`, `search_calendar`, `propose_calendar_event`, `create_notification`

Separate read tools from write/proposal tools.

## Do not

- Expose raw SQL or arbitrary DB access.
- Build multiple agents.

## Accept

Secretary can call typed tools against existing services; tests cover core read/write tool paths.

## Note

No automatic proposal persistence yet unless specified in phase. Secrets only in `.env`.

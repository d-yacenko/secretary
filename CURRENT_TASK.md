# Current task — PHASE 11

## Goal

Expose the Personal Secretary core to external LLM clients via MCP.

## Do

1. Official Python MCP SDK.
2. Initial tools: search, get_object, get_context, create_task, update_task, link_objects, get_today, list_notifications.
3. Reuse `DomainToolService` — no duplicate business logic.
4. Streamable HTTP for remote access; authenticate MCP.

## Defer external writes

Keep destructive/external write actions out of MCP until approval handling is complete.

## Accept

MCP client can search, read context, create a task, and link it to an existing object.

## Note

Calendar/notification tools may remain stubs until their domain phases. Secrets only in `.env`.

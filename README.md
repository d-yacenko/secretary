# Personal Secretary OS

A personal task and context system that synchronizes mail, calendars, and files; stores a typed object graph in PostgreSQL; uses an LLM secretary to correlate events and propose actions; and exposes the core through REST, MCP, and a Flutter client (Android + Linux).

Single-user first. PostgreSQL is the source of truth.

## Layout

- `backend/` — FastAPI API, worker, MCP, domain services
- `client/` — Flutter app (Android + Linux)
- `infra/` — Docker Compose, Caddy
- `docs/` — architecture and API notes

## Development

See `AGENTS.md` for agent workflow and `PROJECT_STATE.md` for current phase.

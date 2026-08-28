# Project state

## Current phase

PHASE 02 — core database model

## Working components

- Repository skeleton (PHASE 00)
- Docker Compose: `db`, `api`, `worker` (`infra/compose.yaml`)
- PostgreSQL 16 + pgvector (Alembic migration `0001`)
- FastAPI `/health` with DB check
- Worker stub logs alive
- Backend tests: health + DB connection

## Known blockers

- `docker compose` plugin not installed on dev host (`docker compose up` fails). Stack verified via `docker run` + local pytest. Install Compose v2 plugin to use `infra/compose.yaml` directly.

## Next phase

PHASE 02 — `objects` and `edges` tables, indexes, constraints, graph seed tests.

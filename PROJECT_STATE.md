# Project state

## Current phase

PHASE 02 — core database model (waiting for user go-ahead)

## Working components

- Repository skeleton (PHASE 00)
- Docker Compose: `db`, `api`, `worker` (`infra/compose.yaml`)
- PostgreSQL 16 + pgvector (Alembic migration `0001`)
- FastAPI `/health` with DB check
- Worker stub logs alive
- Backend tests: health + DB connection
- VDS deploy: `/opt/secretary`, `infra/compose.deploy.yaml` (API `127.0.0.1:18080`)

## VDS (185.233.107.66)

- Path: `/opt/secretary`
- Domain on host: `web-itx.duckdns.org` (nginx 80/443 — existing site)
- Secretary API: `http://127.0.0.1:18080/health` (localhost only; HTTPS proxy later)
- Update: `cd /opt/secretary && git pull && cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`

## Known blockers

- Dev host: `docker compose` plugin missing; use `docker run` or install Compose v2.
- HTTPS for Secretary API not configured yet (nginx + Certbot on subdomain/path — later).

## Next phase

PHASE 02 — `objects` and `edges` tables, indexes, constraints, graph seed tests.

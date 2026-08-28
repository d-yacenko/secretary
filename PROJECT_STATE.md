# Project state

## Current phase

PHASE 03 — graph CRUD API (waiting for user go-ahead)

## Working components

- PHASE 00–01: repo, Docker Compose, `/health`, worker stub, VDS deploy
- PHASE 02: `objects` + `edges` tables, Alembic `0002`, ORM models, graph schema tests
- Compose uses `${POSTGRES_*}` from `.env` (no hard-coded DB password)

## VDS (185.233.107.66)

- Path: `/opt/secretary`
- API: `http://127.0.0.1:18080/health`
- Update: `cd /opt/secretary && git pull && cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`

## Known blockers

- HTTPS reverse proxy for Secretary not configured yet.

## Next phase

PHASE 03 — REST graph CRUD + service layer + HTTP integration tests.

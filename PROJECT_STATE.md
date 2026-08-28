# Project state

## Current phase

PHASE 04 — views and map persistence (waiting for user go-ahead)

## Working components

- PHASE 00–02: repo, Docker, pgvector, `objects` + `edges` schema
- PHASE 03: REST graph CRUD (`/objects`, `/edges`, neighbors, context), service layer, HTTP tests
- VDS: `/opt/secretary`, API `127.0.0.1:18080`

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

## Known blockers

- HTTPS reverse proxy not configured yet.

## Next phase

PHASE 04 — `views` and `view_items` tables; same object in multiple maps.

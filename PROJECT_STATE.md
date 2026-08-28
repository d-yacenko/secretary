# Project state

## Current phase

PHASE 05 — vector search (waiting for user go-ahead + credentials checkpoint)

## Working components

- PHASE 00–03: infra, graph schema, REST CRUD
- PHASE 04: `views` + `view_items` (Alembic `0003`), `ViewService`, persistence tests
- PATCH rejects null for `kind`/`title`/`origin`/`metadata` (422)
- External object duplicate → 409 on POST/PATCH

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

## Known blockers

- HTTPS reverse proxy not configured.
- PHASE 05 needs embedding provider API key for live tests (fake path available).

## Next phase

PHASE 05 — embeddings + `GET /search`.

# Project state

## Current phase

PHASE 08 — provenance and inference states (waiting for user go-ahead)

## Working components

- PHASE 00–04: infra, graph, views
- PHASE 05: embeddings (`EmbeddingService`, OpenAI + fake), `GET /search`, index on write
- PHASE 06: `representations` table, `RepresentationService`, ingestion for `.txt`/`.md`/`.csv`/`.parquet`
  - re-ingestion replaces prior representations for the same object
- PHASE 07: `ContextService.build_context(object_id, query, max_chars)`
  - bounded neighbors, semantic candidates, chunk ranking, budget trimming
  - typed `ContextItem` / `ContextBuildResult` schemas
- `view_items` XOR constraint
- Env: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`)

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

Put OpenAI credentials only in `/opt/secretary/.env`.

## Known blockers

- HTTPS reverse proxy not configured.
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_embedding_live.py` (requires `.env`).

## Next phase

PHASE 08 — provenance and inference states (`observed`/`proposed`/`confirmed`/`rejected`, `origin`, confidence for inferred items).

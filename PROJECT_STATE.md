# Project state

## Current phase

PHASE 06 — resource representations (waiting for user go-ahead)

## Working components

- PHASE 00–04: infra, graph, views
- PHASE 05: embeddings (`EmbeddingService`, OpenAI + fake), `GET /search`, index on write
- `view_items` XOR constraint (exactly `object_id` or `visual_id`)
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

PHASE 06 — `representations` table and resource policies.

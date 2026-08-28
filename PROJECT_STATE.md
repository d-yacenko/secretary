# Project state

## Current phase

PHASE 09 — Secretary LLM (waiting for user go-ahead)

## Working components

- PHASE 00–04: infra, graph, views
- PHASE 05–07: embeddings, search, representations, context resolver
- PHASE 08: object `state` (migration `0006`), provenance validation
  - `origin` / `state` / `confidence` on objects and API responses
  - agent `proposed` requires confidence in 0..1; confirmation preserves agent origin
  - ContextItem carries provenance; rejected proposals excluded from default context/graph traversal
- Context resolver: target representations, strict `max_chars`, embedding-failure fallbacks
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

PHASE 09 — `SecretaryService` with OpenAI Responses API and structured outputs from bounded context packs.

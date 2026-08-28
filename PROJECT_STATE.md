# Project state

## Current phase

PHASE 11 — MCP server (waiting for user go-ahead)

## Working components

- PHASE 00–09: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM
- PHASE 10: domain tools (`search_objects`, `get_object`, `get_context`, `create_task`, `update_task`, `link_objects`, `list_neighbors`)
  - `DomainToolService` + `ToolExecutor` (max 5 calls per run)
  - agent `proposed` provenance on inferred writes
- Secretary: evidence validation, no fake provider without API key, reference datetime normalization
- Env: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_MODEL`, `SECRETARY_TIMEZONE`

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

Put OpenAI credentials only in `/opt/secretary/.env`.

## Known blockers

- HTTPS reverse proxy not configured.
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 11 — MCP server exposing domain tools via official Python MCP SDK.

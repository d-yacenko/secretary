# Project state

## Current phase

PHASE 10 — domain tools for the agent (waiting for user go-ahead)

## Working components

- PHASE 00–08: infra, graph, views, embeddings, search, representations, context resolver, provenance
- PHASE 09: `SecretaryService` with typed `SecretaryAnalysis` (OpenAI Responses + fake provider)
  - `OPENAI_MODEL`, `SECRETARY_TIMEZONE` env vars
  - offline fixture test for meeting + forecast task from observed email
  - optional live smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`
- Provenance: explicit `origin`/`state` values; immutable object origin; `set_edge_state`
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
- Live OpenAI smoke requires API key with Responses API permission (not embeddings-only).

## Next phase

PHASE 10 — domain tools (`search_objects`, `get_context`, `create_task`, etc.) for the Secretary agent.

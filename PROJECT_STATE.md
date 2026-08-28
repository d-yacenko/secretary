# Project state

## Current phase

PHASE 12 — PostgreSQL job queue (waiting for user go-ahead)

## Working components

- PHASE 00–09: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM
- PHASE 10: domain tools (`search_objects`, `get_object`, `get_context`, `create_task`, `update_task`, `link_objects`, `list_neighbors`)
- PHASE 11: MCP server (Streamable HTTP at `/mcp`, official `mcp>=2,<3` SDK)
  - Thin adapters in `app/mcp/` → `DomainToolService`
  - Tools: `search_objects`, `get_object`, `get_context`, `list_neighbors`, `create_task`, `update_task`, `link_objects`, `get_today`
  - Typed tool output schemas; bounded `get_context` (`max_chars` default 8000, max 12000)
  - Timezone-safe `due_at` via `normalize_tool_datetime`
  - MCP bound to same API port; keep non-public (localhost / SSH tunnel on VDS)
- Secretary: evidence validation, no fake provider without API key, reference datetime normalization
- Env: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_MODEL`, `SECRETARY_TIMEZONE`, `MCP_ENABLED`

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml exec -T api python -c "
import asyncio
from mcp.client import Client
async def main():
    async with Client('http://127.0.0.1:8000/mcp/') as c:
        r = await c.list_tools()
        print(sorted(t.name for t in r.tools))
asyncio.run(main())
"
```

Put OpenAI credentials only in `/opt/secretary/.env`.

## Known blockers

- HTTPS reverse proxy not configured.
- MCP HTTP auth not configured; endpoint must stay non-public until HTTPS/auth.
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 12 — PostgreSQL job queue for async sync and LLM analysis (no Redis).

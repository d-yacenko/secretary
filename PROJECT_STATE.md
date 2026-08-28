# Project state

## Current phase

PHASE 13 — notifications (waiting for user go-ahead)

## Working components

- PHASE 00–09: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM
- PHASE 10: domain tools (`search_objects`, `get_object`, `get_context`, `create_task`, `update_task`, `link_objects`, `list_neighbors`)
- PHASE 11: MCP server (Streamable HTTP at `/mcp`, official `mcp>=2,<3` SDK)
  - Opt-in: `MCP_ENABLED` defaults to `false`; enable only on localhost/private access
  - Typed `due_at` on MCP tools; bounded `get_context` (`max_chars` default 8000, max 12000)
- PHASE 12: PostgreSQL job queue (`jobs` table, `JobQueueService`, worker polling loop)
  - `FOR UPDATE SKIP LOCKED` claiming; bounded retries; stale-lock recovery (15 min)
  - Handler: `embed_object` (regenerates object embedding via `EmbeddingService`)
  - No Redis/Celery; worker in existing Compose stack
- Secretary: evidence validation, no fake provider without API key, reference datetime normalization
- Env: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_MODEL`, `SECRETARY_TIMEZONE`, `MCP_ENABLED`

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

Keep `MCP_ENABLED=true` in `/opt/secretary/.env` only because API binds to localhost.

Enqueue a harmless `embed_object` job (example):

```bash
docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml exec -T api python -c "
from app.db.session import SessionLocal
from app.services.job_queue_service import JobQueueService
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from sqlalchemy import select
from app.db.models import Object, Job
session = SessionLocal()
obj = session.scalar(select(Object).limit(1))
if obj is None:
    raise SystemExit('no objects in db')
job = JobQueueService(session).enqueue(JOB_TYPE_EMBED_OBJECT, {'object_id': str(obj.id)})
session.commit()
print(job.id)
"
```

Put OpenAI credentials only in `/opt/secretary/.env`.

## Known blockers

- HTTPS reverse proxy not configured.
- MCP HTTP auth not configured; endpoint must stay non-public until HTTPS/auth.
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 13 — notifications inbox (`notifications` table, actionable inferred events).

# Project state

## Current phase

PHASE 14 — Google OAuth and Gmail (waiting for user go-ahead; credentials checkpoint unblocked)

## Working components

- PHASE 00–11: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM, domain tools, MCP (opt-in)
- PHASE 12: PostgreSQL job queue (`jobs`, `JobQueueService`, `embed_object` handler, worker polling)
  - Embedding job: short DB tx → embed outside tx → short DB tx
  - Stale running jobs respect `MAX_JOB_ATTEMPTS`
- PHASE 13: notifications inbox
  - `notifications` table with proposal JSONB and object FKs (`ON DELETE SET NULL`)
  - `NotificationService` + REST (`GET/POST /notifications/...`)
  - `create_notifications_from_analysis()` from Secretary proposals (no auto-execution)
  - Read-only domain/MCP tool: `list_notifications`
- Env: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_MODEL`, `SECRETARY_TIMEZONE`, `MCP_ENABLED`

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

Keep `MCP_ENABLED=true` in `/opt/secretary/.env` only because API binds to localhost.

Put OpenAI credentials only in `/opt/secretary/.env`.

## Security notes

- `.env` is gitignored; no API keys in tracked files.
- VDS PostgreSQL password rotated from the development default; real value stored only in `/opt/secretary/.env`.
- Database remains on the private Docker network (not exposed publicly).
- PHASE 14 Google OAuth/Gmail credential checkpoint is unblocked (password rotation complete).

## Known blockers

- HTTPS reverse proxy not configured.
- MCP HTTP auth not configured; endpoint must stay non-public until HTTPS/auth.
- Google OAuth/Gmail credentials not configured (PHASE 14).
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 14 — Google OAuth and Gmail sync (credentials checkpoint; do not proceed without Google Cloud setup).

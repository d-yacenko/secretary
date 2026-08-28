# Project state

## Current phase

PHASE 14 — Google OAuth and bounded Gmail sync (complete; awaiting user review)

PHASE 15 — Google Calendar (not started; do not begin without user go-ahead)

## Working components

- PHASE 00–11: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM, domain tools, MCP (opt-in)
- PHASE 12: PostgreSQL job queue (`jobs`, `JobQueueService`, `embed_object` handler, worker polling)
- PHASE 13: notifications inbox (`notifications`, REST, Secretary → notifications, MCP `list_notifications`)
- PHASE 14: Google OAuth + bounded Gmail sync
  - OAuth client JSON mounted read-only at `/run/secrets/google-oauth-client.json` (not in Git)
  - Fernet encryption for stored tokens (`SECRETARY_CREDENTIAL_KEY` in `.env` only)
  - Tables: `google_accounts`, `oauth_states`
  - Endpoints: `GET /auth/google/start`, `GET /auth/google/callback`, `POST /connectors/google/gmail/sync`
  - Scope: `gmail.readonly` only; redirect `http://localhost:18080/auth/google/callback`
  - Bounded manual sync: default ~50 / 30 days, hard max 100 messages
  - Gmail → `objects(kind=email, provider=gmail, origin=source, state=observed)`; idempotent by `(provider, kind, external_id)`
  - `embed_object` jobs for new/changed emails (payload: `{"object_id": "..."}` only)
  - Connector package: `app/connectors/google/` (no Google calls in routes)
- Env: `OPENAI_*`, `SECRETARY_TIMEZONE`, `MCP_ENABLED`, `GOOGLE_OAUTH_CLIENT_FILE`, `GOOGLE_REDIRECT_URI`, `SECRETARY_CREDENTIAL_KEY`

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

OAuth JSON (never via Git):

```bash
scp secrets/google-oauth-client.json root@<vds>:/opt/secretary/secrets/google-oauth-client.json
ssh root@<vds> 'chmod 600 /opt/secretary/secrets/google-oauth-client.json'
```

Local OAuth via SSH tunnel:

```bash
ssh -L 18080:127.0.0.1:18080 root@185.233.107.66
# browser: http://localhost:18080/auth/google/start
```

After connect, bounded sync:

```bash
curl -X POST http://127.0.0.1:18080/connectors/google/gmail/sync
```

Keep `MCP_ENABLED=true` in `/opt/secretary/.env` only because API binds to localhost.

## Security notes

- `.env` and `secrets/` are gitignored; OAuth client JSON never committed.
- VDS PostgreSQL password rotated; real value only in `/opt/secretary/.env`.
- `SECRETARY_CREDENTIAL_KEY` generated on VDS only.
- Database on private Docker network; API on `127.0.0.1:18080`.

## Known blockers

- HTTPS reverse proxy not configured.
- MCP HTTP auth not configured; endpoint must stay non-public until HTTPS/auth.
- Live OAuth + first Gmail sync require user browser (SSH tunnel); not automated in CI.
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 15 — Google Calendar (readonly sync; do not start automatically).

# Project state

## Current phase

PHASE 14 — Google OAuth and bounded Gmail sync (corrective fixes applied; awaiting user review)

PHASE 15 — Google Calendar (not started; do not begin without user go-ahead)

## Working components

- PHASE 00–13: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM, domain tools, MCP, job queue, notifications
- PHASE 14: Google OAuth + bounded Gmail sync
  - OAuth scope: `gmail.readonly` only (no userinfo/openid/profile)
  - Account email from Gmail API `users/me/profile` (`emailAddress`)
  - Encrypted tokens (`SECRETARY_CREDENTIAL_KEY`); tables `google_accounts`, `oauth_states`
  - Endpoints: `GET /auth/google/start`, `GET /auth/google/callback`, `POST /connectors/google/gmail/sync`
  - Redirect: `http://localhost:18080/auth/google/callback` (SSH tunnel to VDS)
  - Bounded sync: default ~50 / 30 days, max 100 messages
  - Gmail → `objects(kind=email, provider=gmail, origin=source, state=observed)`
  - Email text in `Object.body` (bounded); metadata keeps headers/provenance only
  - Idempotent sync by `(provider, kind, external_id)`; `embed_object` on new/changed body
  - Token refresh: short DB tx → HTTP refresh → short DB tx (no tx held during Google HTTP)
  - Nested `multipart/*` body extraction (plain preferred over HTML)
  - Connector: `app/connectors/google/`

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

Live OAuth + first sync (user browser required):

```bash
ssh -L 18080:127.0.0.1:18080 root@185.233.107.66
# browser: http://localhost:18080/auth/google/start
curl -X POST http://127.0.0.1:18080/connectors/google/gmail/sync
```

## Security notes

- `.env` and `secrets/` gitignored; OAuth JSON never committed
- VDS PostgreSQL password rotated; value only in `/opt/secretary/.env`
- `SECRETARY_CREDENTIAL_KEY` on VDS only
- API on `127.0.0.1:18080`; DB on private Docker network

## Known blockers

- HTTPS reverse proxy not configured
- MCP HTTP auth not configured
- Live OAuth/sync requires user browser via SSH tunnel (not automated)
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 15 — Google Calendar (do not start automatically).

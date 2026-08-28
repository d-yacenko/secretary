# Project state

## Current phase

PHASE 14.5 — User ownership + bounded incremental connector policy (complete; awaiting user review)

PHASE 15 — Google Calendar (not started; do not begin without user go-ahead)

## Architectural invariants (from PHASE 14.5)

- Every personal resource belongs to an explicit Secretary `user_id`.
- User isolation happens **before** retrieval, ranking, and LLM context assembly.
- Initial connector history is bounded; known unchanged source objects are not repeatedly downloaded or processed.
- Incremental synchronization is preferred after initial backfill.
- Bootstrap owner: `00000000-0000-4000-8000-000000000001` (`app/users/bootstrap.py`).
- `CurrentUserContext` resolves bootstrap owner for REST/MCP until real auth exists.

## Working components

- PHASE 00–13: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM, domain tools, MCP, job queue, notifications
- PHASE 14: Google OAuth + bounded Gmail sync
  - OAuth scope: `gmail.readonly` only
  - Account email from Gmail API `users/me/profile`
  - Encrypted tokens; tables `google_accounts`, `oauth_states`
  - Endpoints: `GET /auth/google/start`, `GET /auth/google/callback`, `POST /connectors/google/gmail/sync`
  - Redirect: `http://localhost:18080/auth/google/callback` (SSH tunnel to VDS)
  - Bounded sync: default ~50 / 30 days, max 100 messages
  - Gmail → `objects(kind=email, provider=gmail, origin=source, state=observed)`
  - Email text in `Object.body`; metadata keeps headers/provenance only
  - Token refresh: short DB tx → HTTP refresh → short DB tx
- PHASE 14.5: multi-user-ready ownership + incremental Gmail policy
  - `users` table + bootstrap owner; migration `0010_user_ownership`
  - `user_id` on objects, edges, views, jobs, notifications, google_accounts, oauth_states
  - Source uniqueness: `(user_id, provider, kind, external_id)`
  - Google account uniqueness: `(user_id, email)`
  - OAuth state binds initiating `user_id`; callback does not accept caller-supplied user
  - Graph/search/context/vector/notifications/views/jobs all user-scoped
  - Gmail sync: list IDs → batch known lookup → fetch full message only for unknown IDs
  - Second sync skips known message bodies; no duplicate objects/embed jobs
  - Offline isolation tests: `tests/test_user_isolation.py` (178 tests pass)

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
# second sync should report skipped_known for already-imported messages
```

## Security notes

- `.env` and `secrets/` gitignored; OAuth JSON never committed
- VDS PostgreSQL password rotated; value only in `/opt/secretary/.env`
- `SECRETARY_CREDENTIAL_KEY` on VDS only
- API on `127.0.0.1:18080`; DB on private Docker network
- Application-level tenant isolation (no PostgreSQL RLS yet)

## Known blockers

- HTTPS reverse proxy not configured
- MCP HTTP auth not configured
- Live OAuth/sync requires user browser via SSH tunnel (not automated)
- Live OpenAI smoke: `RUN_LIVE_OPENAI=1 pytest -m live tests/test_secretary_live.py`

## Next phase

PHASE 15 — Google Calendar (user-owned account, bounded history, incremental sync; do not start automatically).

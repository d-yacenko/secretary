# Project state

## Current phase

PHASE 14.5 — User ownership + bounded incremental connector policy (corrective applied; awaiting user review)

PHASE 15 — Google Calendar (not started; do not begin without user go-ahead)

## Architectural invariants

- Every personal resource belongs to an explicit Secretary `user_id`.
- User isolation happens **before** retrieval, ranking, and LLM context assembly.
- `resolve_current_user()` is the single bootstrap identity resolver (REST/MCP); real auth replaces only this layer.
- `external_id` is identity, not a change/version marker — skip fetch/process only when a reliable change signal exists.
- Initial connector history is bounded; incremental sync preferred after backfill.
- Bootstrap owner: `00000000-0000-4000-8000-000000000001` (`app/users/bootstrap.py`).

## Working components

- PHASE 00–13: infra, graph, views, embeddings, search, representations, context, provenance, Secretary LLM, domain tools, MCP, job queue, notifications
- PHASE 14: Google OAuth + bounded Gmail sync (`gmail.readonly`, encrypted tokens, bounded list/fetch)
- PHASE 14.5: multi-user-ready ownership + connector policy
  - `users` table; `user_id` on objects, edges, views, jobs, notifications, google_accounts, oauth_states
  - Source uniqueness: `(user_id, provider, kind, external_id)`
  - Google credentials scoped: `account_id` + `user_id` for load/refresh
  - `RepresentationService(session, user_id, …)` enforces parent object ownership
  - Gmail sync: bounded list → bounded fetch → normalize → user-scoped upsert → compare fields → embed only when new/changed
  - OAuth state binds initiating `user_id`
  - Offline tests: `tests/test_user_isolation.py` (**184 tests pass**)

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

Live OAuth + Gmail sync (user browser required):

```bash
ssh -L 18080:127.0.0.1:18080 root@185.233.107.66
# browser: http://localhost:18080/auth/google/start
curl -X POST http://127.0.0.1:18080/connectors/google/gmail/sync
```

## Security notes

- `.env` and `secrets/` gitignored; deployment OAuth client JSON is not user data
- Application-level tenant isolation (no PostgreSQL RLS yet)
- API on `127.0.0.1:18080`

## Known blockers

- HTTPS reverse proxy not configured
- MCP HTTP auth not configured
- Live OAuth/sync requires user browser via SSH tunnel

## Next phase

PHASE 15 — Google Calendar (user-scoped; do not start automatically).

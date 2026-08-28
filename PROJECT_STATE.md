# Project state

## Current phase

PHASE 15 — Google Calendar sync (complete; awaiting user review)

PHASE 16 — Yandex Mail (not started)

## Architectural invariants

- Every personal resource belongs to an explicit Secretary `user_id`.
- User isolation happens **before** retrieval, ranking, and LLM context assembly.
- `external_id` is identity, not a change/version marker.
- Initial connector history is bounded; upsert compares normalized fields.
- Bootstrap owner: `00000000-0000-4000-8000-000000000001`.

## Working components

- PHASE 00–14.5: (see prior phases)
- PHASE 15: Google Calendar readonly sync
  - OAuth scopes: `gmail.readonly` + `calendar.readonly`
  - `POST /connectors/google/calendar/sync`
  - Bounded window: ~60 days back, ~90 days forward, max 100 events
  - `objects(kind=event, provider=google_calendar, origin=source, state=observed)`
  - `external_id` = `{calendar_id}:{event_id}`; metadata keeps calendar/event ids
  - User-scoped upsert; `embed_object` on new/changed only
  - Credential access: `account_id` + `user_id`
  - Deferred: calendar write, watch channels, missing-meeting flow, `search_calendar` tool
  - Offline tests: `tests/test_google_calendar.py` (**190 tests pass**)

## VDS update

```bash
cd /opt/secretary && git pull
cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

Re-OAuth required if account only has Gmail scope:

```bash
ssh -L 18080:127.0.0.1:18080 root@185.233.107.66
# browser: http://localhost:18080/auth/google/start
curl -X POST http://127.0.0.1:18080/connectors/google/calendar/sync
```

## Next phase

PHASE 16 — Yandex Mail (do not start automatically).

# Project state

## Current phase

PHASE 15 — Google Calendar sync (implemented in `4ce8426`; awaiting review)

PHASE 15 corrective — Gmail known-ID skip policy (pending acceptance after this commit)

PHASE 16 — Yandex Mail (not started; do not start)

## Architectural invariants

- Every personal resource belongs to an explicit Secretary `user_id`.
- User isolation happens **before** retrieval, ranking, and LLM context assembly.
- Initial connector backfill is bounded; after that prefer incremental/new/changed only.
- Known unchanged source content must not be repeatedly downloaded/embedded/analyzed without need.
- `external_id` is identity; for Gmail normal sync, a known ID for the **current user** means skip full body fetch.
- Bootstrap owner: `00000000-0000-4000-8000-000000000001`.

## Connector sync policy

| Connector | Normal sync behavior |
|-----------|---------------------|
| Gmail | `messages.list` → batch known IDs (user-scoped) → `messages.get` only for unknown → embed new only. Known bodies stable until History API reconciliation. |
| Google Calendar | Bounded list (~60d back, ~90d forward, max 100 events) → fetch → user-scoped upsert → embed on new/changed. Future: sync tokens / incremental tracking. |

## Working components

- PHASE 00–14.5: user ownership, scoped credentials, representations, Gmail OAuth
- PHASE 15 (`4ce8426`): Google Calendar readonly sync
  - OAuth: `gmail.readonly` + `calendar.readonly`
  - `POST /connectors/google/calendar/sync`
  - `objects(kind=event, provider=google_calendar)`
  - Deferred: calendar write, watch channels, missing-meeting flow, `search_calendar`
- Offline tests: **189 passed**, 2 skipped

## Not done yet

- Live OAuth / deploy (explicitly deferred until review acceptance)
- PHASE 16

## Next phase

PHASE 16 — Yandex Mail (do not start without user go-ahead).

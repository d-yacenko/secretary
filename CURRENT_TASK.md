# Current task — Universal Object Delete deployed

## Status

PHASE 29A: **ARCHITECT ACCEPTED / CLOSED** at `1562db7a7764e387ce4c9518a7032b801fcf0cdf`.

Universal Intake Iteration A: **ARCHITECT ACCEPTED / CLOSED** at `f5b76856b4c967ef0673798bd6e9334c77fd2522`.

Universal Object Delete: **implemented and deployed**, **awaiting architect review**.

## Branch

`review/universal-object-delete`

## Scope delivered

- Alembic `0027_object_deleted_at` with legacy `task status=deleted` backfill
- `ObjectDeletionService` + `DELETE /objects/{object_id}` tombstone API
- Task delete (`DELETE /tasks/{id}`) and Agent `delete_task` delegate to same service
- Central `deleted_at` visibility filters across search/retrieve/inbox/today/graph/context/open-target
- Passive source sync non-resurrection (Mattermost, Google/Yandex Calendar)
- Explicit re-add restores same `object_id` and clears `deleted_at`
- Background job no-op guards for tombstoned objects
- Flutter universal trash action with provider-aware confirmation copy

## Deploy

Application SHA: `6d026a20cbd9f02525ac292dd66dfd7f3b4d84e1`

Deployed VDS SHA: `6d026a20cbd9f02525ac292dd66dfd7f3b4d84e1` (clean)

Encrypted context blob SHA: `e26256c4cb82e376e6c6217db0bfeb3ff82f2ada`

Alembic current/head: `0027`

`/health`: PASS

Worker: healthy

Production API disposable-note delete: **PASS** — tombstone set; `GET /objects/{id}` → 404; deleted note absent from search results

Production API explicit-web delete/re-add: **not run on VDS** (`example.test` does not resolve in production fetch); covered by backend tests

## Next

STOP — await architect review.

NEXT after acceptance: User Identity Profile / Self Resolution.

Do not start Format Parity B or Safe External Actions.

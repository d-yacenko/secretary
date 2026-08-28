# Current task — PHASE 15 (not started)

## Status

PHASE 14.5 corrective complete. Awaiting user acceptance before starting PHASE 15.

## Global invariants (PHASE 15+)

- Every personal resource/account belongs to `user_id`.
- Connector grants are per-user; deployment OAuth client credentials are not user data.
- Retrieval is user-filtered **before** ranking.
- Workers preserve user ownership; no cross-user graph/context/notification/resource access.
- `external_id` is identity, not a change/version marker.

## Goal (when approved)

Synchronize Google Calendar events into user-scoped graph objects (readonly).

## Prerequisites

- PHASE 14.5 accepted (user ownership, scoped credentials, bounded sync policy).
- Same Google account must belong to the Secretary user (`GoogleAccount.user_id`).
- Calendar objects must be user-scoped with `(user_id, provider, kind, external_id)` idempotency.
- Calendar API scope decision (likely `calendar.readonly`).
- Same OAuth redirect/tunnel pattern as Gmail.

## Do (when approved)

1. Extend Google connector for Calendar transport + normalization (user-scoped).
2. Bounded initial calendar history sync → `objects(kind=event)`.
3. User-scoped upsert by external id; enqueue `embed_object` only for new/changed items.
4. Credential/token access via `account_id` + `user_id` only.

## Defer

- Calendar write / event creation.
- Gmail push, continuous polling.
- Deep historical import without explicit user action.

## Accept

Connected user-owned account can sync recent calendar events as observed source objects with provenance.

## Note

Stop after phase for user review. Do not auto-start PHASE 16.

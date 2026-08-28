# Current task — PHASE 15

## Goal

Synchronize Google Calendar events into graph objects (readonly).

## Prerequisites

- PHASE 14 accepted (OAuth, encrypted credentials, connector boundary).
- Calendar API scope decision (likely `calendar.readonly`).
- Same OAuth redirect/tunnel pattern as Gmail.

## Do (when approved)

1. Extend Google connector for Calendar transport + normalization.
2. Bounded initial calendar sync → `objects(kind=event or calendar_event)`.
3. Idempotent sync by external id; enqueue `embed_object` for new/changed items.

## Defer

- Calendar write / event creation.
- Gmail push, continuous polling (still deferred from PHASE 14).

## Accept

Connected account can sync recent calendar events as observed source objects with provenance.

## Note

Stop after phase for user review. Do not auto-start PHASE 16.

# Current task — PHASE 17 (not started)

## Status

PHASE 16 complete. Awaiting user acceptance before starting PHASE 17.

## Goal (when approved)

Synchronize Yandex Calendar via CalDAV into user-scoped `event` objects.

## Prerequisites

- PHASE 16 accepted.
- Same global ownership/sync invariants as PHASE 14.5+.

## Do (when approved)

1. Add `YandexCalendarConnector` with CalDAV transport + normalization.
2. User-scoped objects; bounded initial history; incremental when supported.
3. Cross-user isolation test.

## Defer

- Calendar write.
- Deep historical import without explicit user request.

## Roadmap note

PHASE 19.5 — Secretary Authentication & Connections must land before PHASE 20 Flutter.

## Note

Stop after phase for user review. Do not auto-start PHASE 18.

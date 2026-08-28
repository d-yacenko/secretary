# Current task — PHASE 16 (not started)

## Status

PHASE 15 complete. Awaiting user acceptance before starting PHASE 16.

## Goal (when approved)

Synchronize Yandex Mail into the same normalized `email` object model as Gmail.

## Prerequisites

- PHASE 15 accepted.
- IMAP or OAuth credentials strategy for Yandex.

## Do (when approved)

1. Add `YandexMailConnector` with UID/UIDVALIDITY incremental sync.
2. Normalize to `objects(kind=email, …)` — same shape as Gmail.
3. User-scoped ownership and bounded initial history.

## Defer

- IMAP IDLE unless easy/reliable.
- Second mail domain model (reuse Gmail email shape).

## Note

Stop after phase for user review.

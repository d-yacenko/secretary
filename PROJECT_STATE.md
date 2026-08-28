# Project state

## Current phase

PHASE 16 — Yandex Mail (accepted: code, live smoke, incremental UID edge fix)

PHASE 17 — Yandex Calendar (not started; do not start)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–15: (prior phases)
- PHASE 16: Yandex Mail IMAP sync
  - Live: `ydv@arenadata.io` on VDS (`main` `f148170+`)
  - MVP auth: encrypted Mail app password per user
  - Incremental UID search filters client-side (`uid > checkpoint`)
  - Initial backfill newest N; incremental oldest N per batch
  - UIDVALIDITY from IMAP response code; no DB tx during IMAP I/O
  - RFC2047 headers; skip attachment parts for body

## Not done

- PHASE 17+

## Next phase

PHASE 17 — Yandex Calendar (await user go-ahead).

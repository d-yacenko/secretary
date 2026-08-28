# Project state

## Current phase

PHASE 17 — Yandex Calendar: **live-smoked, awaiting final acceptance**

Recurrence corrective: two-step query (href discovery + multiget expand) for bounded backfill/reconciliation.

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync — live smoke passed on VDS `185.233.107.66`
  - Account `ydv@arenadata.io` (`db6353cb-1ac6-4478-9f7f-5fd9f31867de`)
  - Two-step bounded read: calendar-query (no expand) + calendar-multiget (expand)
  - Yandex live probe: multiget+expand accepted (207)
  - Initial backfill: 44 objects; recurring corrective deployed for RRULE instance materialization
  - Incremental sync-collection expand unchanged
  - `/health` ok; credentials absent from API responses and logs

## Not done

- PHASE 17 final acceptance
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 final acceptance.

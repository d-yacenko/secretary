# Project state

## Current phase

PHASE 17 — Yandex Calendar deployed (`17fd823`); awaiting live CalDAV connection + smoke

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync (deployed on VDS `185.233.107.66`, migration `0012` applied)
  - API `127.0.0.1:18080`, worker running
  - Existing Gmail (50) + Yandex Mail (50) objects preserved; bootstrap user intact
  - Yandex Calendar account not connected yet — live smoke pending

## Not done

- Yandex Calendar connect + first/second sync live smoke
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 live smoke acceptance.

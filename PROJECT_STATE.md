# Project state

## Current phase

PHASE 19 — local files and huge datasets: **accepted / closed**

PHASE 19.5 — auth, connections, manual capture: **implemented, awaiting review**

PHASE 20 — Flutter client: **not started**

PHASE 18 — resource registration: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 required before PHASE 20 Flutter.

## Working components

- PHASE 00–19: (prior phases, PHASE 19 closed)
- PHASE 19.5:
  - Opaque bearer tokens with hashed storage and operator CLI
  - Authenticated personal APIs (`/me`, `/connections`, capture)
  - Manual task capture with pinned context and dependencies
  - Pinned context priority in context assembly
  - Google OAuth start requires Secretary auth; callback uses state only

## Not done

- PHASE 19.5 review acceptance
- PHASE 20+ (Flutter)

## Next phase

PHASE 20 after PHASE 19.5 acceptance.

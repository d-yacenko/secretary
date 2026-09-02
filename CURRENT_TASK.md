# Current task — PHASE 28C-B2-A awaiting review

## Status

PHASE 28C-B1: **accepted** at `a9896ce68e375a93e4c8b6bf11e3389007060c7b`.

PHASE 28C-B1-R1: **accepted / manual desktop UI PASS** at `b8ee3f889b30a16eea3af663565fa218b9bcf0a2`.

Current: **PHASE 28C-B2-A — Per-User History Preference Foundation** — implemented, awaiting architect review.

Do **not** merge, deploy, or start B2-B until review.

## PHASE 28C-B2-A delivered

- `history_days` column on `user_source_preferences`
- Effective history resolution with deployment hard policy (1–90 days)
- GET/PATCH API extensions (no connector/runtime backfill yet)

## Branch

`review/phase-28c-history-preferences-a` from `b8ee3f889b30a16eea3af663565fa218b9bcf0a2`.

## Next after 28C-B2-A acceptance

1. PHASE 28C-B2-B — Bounded History Runtime: Google sources
2. PHASE 28C-B2-C — Bounded History Runtime: Yandex + Mattermost
3. PHASE 28C-B2-D — History UI

## Not in 28C-B2-A

- Connector fetch window changes
- Runtime backfill / coverage tracking
- Flutter / History UI
- Explicit Intake preference keys

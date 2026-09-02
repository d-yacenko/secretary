# Current task — PHASE 28C-B2-B1 awaiting review

## Status

PHASE 28C-B2-A: **accepted** at `31326d120ba3e02f2478d9fb72edc7baab37ef57`.

Current: **PHASE 28C-B2-B1 — Gmail Bounded History Runtime** — implemented, awaiting architect review.

Do **not** merge, deploy, or start B2-B2 until review.

## PHASE 28C-B2-B1 delivered

- `gmail_sync_state` / `calendar_sync_state` on `google_accounts`
- Gmail transport pagination + bounded history backfill (live pass + one history page per run)
- Recurring handler uses effective `history_days`; direct HTTP sync remains live-only

## Branch

`review/phase-28c-history-gmail-runtime` from `31326d120ba3e02f2478d9fb72edc7baab37ef57`.

## Next after 28C-B2-B1 acceptance

PHASE 28C-B2-B2 — Google Calendar Bounded History Runtime.

## Not in 28C-B2-B1

- Google Calendar runtime changes
- Yandex / Mattermost history runtime
- History UI / public coverage fields
- Flutter changes

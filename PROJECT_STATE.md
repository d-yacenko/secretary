# Project state

## Current phase

PHASE 16 — Yandex Mail (complete; awaiting user review)

PHASE 17 — Yandex Calendar (not started; do not start)

## Global invariants (PHASE 14.5+)

1. Every personal resource belongs to explicit `user_id`.
2. Services use `CurrentUserContext` — no caller-selectable `user_id` as auth.
3. Connector credentials/checkpoints are user-owned; deployment secrets are not user data.
4. Initial history bounded: ~30–60 days, max 90 without explicit request + item limits.
5. After backfill: incremental when possible; do not re-download/process unchanged content.
6. User filter before retrieval, ranking, and LLM context assembly.
7. New connectors include cross-user isolation tests.
8. **PHASE 19.5** (before Flutter): Secretary Authentication & Connections — real auth/session, `/me`, connection APIs.
9. Flutter (PHASE 20+) authenticates; never selects arbitrary user IDs.

## Working components

- PHASE 00–15: (prior phases + Google Calendar readonly)
- PHASE 16: Yandex Mail IMAP sync
  - Table `yandex_mail_accounts` (encrypted app password, `sync_state` with UIDVALIDITY/last UID)
  - `POST /connectors/yandex/mail/connect` — register app password (bootstrap user)
  - `POST /connectors/yandex/mail/sync` — bounded IMAP sync
  - `objects(kind=email, provider=yandex_mail)` — same normalized email shape as Gmail
  - Bounded window (~30 days default, max 100 messages)
  - Batch known external IDs → skip IMAP FETCH for known messages
  - UIDVALIDITY stored for safe checkpointing
  - Offline tests: `tests/test_yandex_mail.py` (**195 tests pass**)

## Connector sync policy

| Connector | Normal sync |
|-----------|-------------|
| Gmail | `messages.list` → batch known IDs → `messages.get` only for unknown |
| Google Calendar | Bounded list/fetch → upsert → embed on new/changed (mutable events) |
| Yandex Mail | IMAP SEARCH SINCE → batch known IDs → FETCH only for unknown |

## Not done

- Live Yandex IMAP smoke (requires user app password)
- Deploy of PHASE 16 (awaiting review)
- PHASE 19.5 auth, PHASE 17 Yandex Calendar

## Next phase

PHASE 17 — Yandex Calendar (do not start without user go-ahead).

# Current task — Voice Assistant A Final Inbox/Source Corrective

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**Lock-screen Launcher A / R1 functional completion remains implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.** Application SHA `319a99e5c2d55750fd9949f8a31fd137c45b703b`.

**Final Inbox/Source Corrective: implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.** Application SHA `f50b56c6d874148963479830ad25af5b65522c20` (parent `319a99e5c2d55750fd9949f8a31fd137c45b703b`).

Do not start Voice B. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED.

## Production diagnosis (read-only)

Production runtime SHA remains `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357` (old backend; R4-R4 receipts not deployed).

Common worker blockage (proved, not assumed identical Gmail/Teams connector bugs):

- Single general worker lane claims all recurring source-sync jobs.
- `sync_yandex_mail` has been `running` since `locked_at=2026-09-14T11:37:18.648892Z` with no further worker logs.
- Yandex IMAP used `imaplib.IMAP4_SSL` with no socket timeout, so a hung IMAP command blocks `claim_next` forever. Stale-lock reclaim cannot run until the handler returns.
- Telegram continues via webhook (not this worker lane). Existing Inbox Yandex/Telegram objects remain visible.

Gmail (real missing-source failure, not noise-label assumption):

- Recurring job `pending`, `last_success_at=2026-09-14T11:37:15.389530Z`.
- Last list query in worker logs: `after:2026/07/16` plus spam/trash/promotions/social/forums exclusions, HTTP 200.
- Newest materialized `provider=gmail kind=email`: `occurred_at=2026-09-14T11:30:22Z`.
- Stage: Gmail list was not re-run after that success; later messages never reached get/materialize/Inbox.

Teams (confirmed post-connection inbound miss, not pre-`sync_start` history):

- Account `8b28a7d5-5558-4ac5-a051-9f3512ba7dee` `auth_status=active`, `created_at=2026-09-15T04:59:55.120706Z`.
- `sync_start_at=2026-09-15T04:59:55.121926Z`. `sync_state.chats` missing. `teams` objects = 0.
- `sync_teams` job created at connect, `pending`, `attempts=0`, empty `last_success_at`, never claimed.
- Token expired `2026-09-15T06:29:53Z` because refresh never ran.
- Stage: Graph `list_chats` was never reached. Not Inbox eligibility. Not assumed channel/meeting exclusion (unproven until a sync actually lists Graph).

Physical marker observation on the new client against this old backend is **not** a client bug proof. R4-R4 `inbox_review_receipt` is not on production. Do not claim marker behavior fixed until the combined new backend is deployed.

## Code delivered (this corrective)

- Per-source worker lanes for every `RECURRING_SOURCE_JOB_TYPES` entry; general lane excludes those plus scheduled-activity.
- Yandex IMAP connect timeout 30s (`OSError` / `IMAP4.error` fail closed).
- Explicit complete-enumeration utterances classify as `purpose=review` in prompt, tool schema, and `inbox_review_purpose_for_utterance` (`перечисли все новые сообщения` contract test). Count/peek utterances remain `inspect`.
- No lock icon. No visual-identity orb redesign.

## Checks

- Focused backend: `test_inbox_review_utterance_purpose.py`, `test_yandex_imap_timeout.py`, `test_worker_lanes.py`, `test_inbox_review_marker_assistant.py`, `test_inbox_review_snapshot_r4r4.py` — **45 passed**.
- `ruff check` on touched backend files: clean.

## Remaining

Architect review of this corrective SHA `f50b56c6d874148963479830ad25af5b65522c20` plus prior Lock-screen Launcher A R1 `319a99e5c2d55750fd9949f8a31fd137c45b703b`. After PASS, Architect issues exact-SHA deploy of the combined tree. Then user physical marker gate A–J from the Architect note (complete enumeration, TTS finish, marker to snapshot_top, interrupt/screenMic/count-only do not move). Do not restart production worker without Architect authorization; a restart without the IMAP timeout would re-hang on Yandex Mail.

## Stop

Wait for Architect. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED. Do not start Voice B.

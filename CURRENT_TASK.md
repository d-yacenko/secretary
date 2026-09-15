# Current task — Voice Assistant A Final Production Corrective R2 deployed

## Status

Voice Assistant A is **CODE ACCEPTED / DEPLOYED / AWAITING FINAL USER MANUAL ACCEPTANCE**.
It is **NOT PRODUCTION ACCEPTED**. Voice B is not started.

Deployed application SHA (runtime): `7610cc1c6ce24764fae73317a6925cdce7bd27b2`.
Previous production SHA: `b0c75eaa5e879ee108afe90f152a29914d28a2f2`.
Production Alembic **0040 → 0041**.

## Deploy facts

- Backup `/opt/secretary/backups/pre-voice-a-r2-20260915T180737Z-b0c75eaa.dump` sha256 `f11def62d051d4d8ee47e8ac9d0754eb95c21e8bd8f4b514664d05d6f3d9737e` (52895759 bytes).
- Env (non-secret): `MICROSOFT_TEAMS_NOTIFICATION_URL=https://web-itx.duckdns.org/secretary/webhooks/teams`, `SOURCE_SYNC_TEAMS_INTERVAL_SECONDS=900`.
- Graph v1.0 `POST /subscriptions` **201**; row `active`; resource `/users/{microsoft-user-id}/chats/getAllMessages`; webhook validation POST echoes `validationToken` as `text/plain` 200 from FastAPI (temporary nginx echo not restored).
- First reconciliation after deploy: 19 `GET /v1.0/me/chats?$expand=lastMessagePreview`, 318 targeted `list_chat_messages` (no watermarks yet / fail-open), Graph **429 count = 0**. Cached chats after run: **319**. Next `sync_teams` `run_after` = last_success + **900s**.
- Debug APK sha256 `e6933829d12ab3ea7f4793c92c00e5a6394c339aca24bbe618b444e1e18305c9`, aapt `sdkVersion:'23'`, installed on SM_T355 (`8430b607`).

## Remaining user-manual gates

Physical Inbox marker completion after «перечисли мне все новые сообщения»; physical Teams inbound via webhook (`process_teams_notification`). Do not mark PRODUCTION ACCEPTED. Do not start Voice B.

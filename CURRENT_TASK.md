# Current task — Voice Assistant A FINAL COMBINED PRODUCTION DEPLOY

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING FINAL USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `b0c75eaa5e879ee108afe90f152a29914d28a2f2`

Previous production SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Docs tip at deploy time: `339d9624375a546ec6fa0e16158f6faa9806cfcd` (not used as runtime).

NOT PRODUCTION ACCEPTED. Do not start Voice B.

## Deploy

Detached on VDS `/opt/secretary`: `git checkout --detach b0c75eaa5e879ee108afe90f152a29914d28a2f2` then `cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`.

Pre-deploy production HEAD matched expected `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`. Working tree clean except untracked `backups/`.

Backup: `/opt/secretary/backups/pre-voice-a-combined-20260915T140527Z-5ef2a2db.dump` (49M, sha256 `0149dd8eac59d963cfaf658069d96af4f76786a1482ee667717dead6edd8d382`). `.env` / secrets not modified.

Alembic **0040 / 0040** before and after. No `0041`.

API and worker containers recreated from `b0c75e` (db volume unchanged). Internal `http://127.0.0.1:18080/health` 200; public `https://web-itx.duckdns.org/secretary/health` 200. Authenticated `/connections`, `/inbox`, `/sources/status` 200. Worker `restartCount=0`, not crash-looping. Provenance: IMAP timeout 30s, per-source lanes, «перечисли все новые сообщения» → `purpose=review`. FAILED `1435` → `1435`.

## Source lanes

Stuck `sync_yandex_mail` (`locked_at=2026-09-14T11:37:18.648892Z`) was reclaimed by existing stale-lock logic. Yandex Mail then succeeded independently (`last_success_at=2026-09-15T14:09:16.483626Z`, status `scheduled`). Gmail and Teams ran in parallel and were not blocked.

Gmail before: `pending`, `last_success_at=2026-09-14T11:37:15.389530Z`, newest Object `2026-09-14T11:30:22Z`, count 839. After: `scheduled`, `last_success_at=2026-09-15T14:09:13.586107Z`, newest `2026-09-15T13:15:03Z`, count 850 (11 newer than the old boundary). `last_error` empty.

Teams before: `pending` `attempts=0`, empty `last_success_at`, token_expiry `2026-09-15T06:29:53Z`, 0 objects, `sync_state` only `sync_start_at`. After: claimed (`running` then success), `last_success_at=2026-09-15T14:09:16.659556Z`, token_expiry `2026-09-15T15:23:59Z`, Graph `/me/chats` 200, `sync_state.chats` 319 keys, 1 `chat_message` Object (`chat_type=group`, `occurred_at=2026-09-15T08:25:29.311Z`, after `sync_start_at`). Channels remain out of scope; the user’s screenshot item is not classified here without Graph channel identity. A fresh oneOnOne/group inbound after this healthy sync is the remaining user gate if that screenshot was a channel post.

## Remaining user physical gates

Inbox complete-enumeration / marker A–J after this combined backend. Do not move the marker from deploy. Not PRODUCTION ACCEPTED.

## Stop

Wait for user physical acceptance. Do not start Voice B. Do not mark PRODUCTION ACCEPTED.

# Current task — Integration A

## Status

**Integration A: CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED**

Branch: `review/unified-communications-a-integration`

Production application: `acf035a8665f0020209b460255156ac0bde5faf6`

Production Alembic: **0038 / 0038**

Migration: **NONE**. No `0039`. No backfill.

Docs-only closure is not deployed.

## Lineage

Design Quality Pass D application: `9b433013c9651a38d1d4f3127e3d44189982d6b5`

Unified Communications A CODE ACCEPTED: `a58c77ad394995067b682157275c5c9026382484`

Integration application (deployed): `acf035a8665f0020209b460255156ac0bde5faf6`

Previous production: `e535adfb9857d2407fac06998a1a5a14c2b73502`

## Production deploy

Exact application SHA `acf035a8665f0020209b460255156ac0bde5faf6` on VDS `/opt/secretary` (detached HEAD). Docs tip `d76c4c84fdada7b96ec7b92a3368258c241dea7f` was not deployed.

Proven procedure: `git fetch` + `git checkout --detach acf035a8665f0020209b460255156ac0bde5faf6` + `cd infra && docker compose --env-file ../.env -f compose.yaml -f compose.deploy.yaml up -d --build`.

Runtime provenance: `acf035a8665f0020209b460255156ac0bde5faf6`.

Alembic before and after: **0038 / 0038**. No `0039` on disk. No schema change. No backfill.

## Production smoke (facts)

API / worker / db healthy. `/health` `{"status":"ok"}`. FAILED `failed=1435` before and after (no unexplained increase). Old FAILED jobs not repaired.

Settings unchanged: `temporal_signals_enabled=true`, `openai_daily_token_limit=1500000`, assistant model `gpt-5.6-luna`, proactive **false** / interval 60, `auto_label_enabled=true`. Source `sync_interval_seconds` unchanged (all 60).

Source sync: Mattermost, Yandex Mail, Yandex Calendar last_success after deploy. Gmail / Google Calendar remain `failed to refresh access token` with last_success **2026-09-13T06:21:28/29Z** (before deploy; pre-existing OAuth; not repaired). No interval changes, no historical backfill, no provider credential rewrites.

Mattermost passive sync: account `c54d71f6-cd7b-4044-8474-08884b9a9166` (`ydv-arenadata.io` @ `https://chat.arenadata.io`) remains connected; sync succeeds. `chat_message` count **1320**; **0** duplicate `(provider,kind,external_id)`; 13 tombstoned. No embedding/job storm. No destructive/tombstone regression.

`send_message` wiring smoke (no approval, zero provider write): Assistant staged frozen COMMUNICATE plan `3e61e42e-f2dc-4260-9f33-1e786b9e716d` from real Mattermost `chat_message` `86e0b94c-0fb2-4f0f-9719-30c3f7562efa` (`reply`/conversation anchor). Provider `mattermost`; account/channel frozen server-side; `operation_id` present in persisted arguments; `pending_post_id` `secretary:848ba8f0c3a54592ad659c0c5e51452b`. Rejected via normal `POST /assistant/action-plans/{id}/reject`. After stage and after reject: **0** `send_message` `external_action_attempts`; no provider POST.

Real Mattermost send: **deferred pending explicit safe target**. Anchor was a colleague DM (channel_type D). Not a deployment failure.

Idempotency (deployed code / proven acceptance only; no fault injection): `ExternalActionAttempt` enabled; `pending_post_id` enabled; uncertain actions are not blindly retried; assistant seen-object anchor guard remains active; MCP remains independent of the interactive per-turn guard.

Client: Linux production client launched from `acf035a8665f0020209b460255156ac0bde5faf6` against `https://web-itx.duckdns.org/secretary`; no startup/runtime exception; authenticated Inbox.

Week: HARD events render; whole-hour cadence (no ordinary `:30` labels/lines); exact timed events keep true position; Today tint present; now-line works; event tap opens Object Detail (`Преподавание ЮФУ`). `scheduled_work` not present in this production week (`GET /week` count 0). Natural temporal hint visible on week **14–20 Sep**: dashed stadium/pill `Встреча 14 сентября`, distinct from HARD blocks. Current week 7–13 `GET /week` `temporal_hints=0`. Week remains read-only except existing task capture.

Account disconnect: Linux/PC — button «Отключить этот клиент» with destructive styling and local-token-only explanation; confirmation dialog opened without disconnecting; user pressed **Отмена**; production auth remained intact; client was **not** disconnected. Android tablet (SM-T355): button and explanation are visible, but tap does not open the dialog. Observed production finding; not repaired in this phase.

`GET /week` 200. `GET /availability` (Sat 2026-09-12 09:00–18:00 Europe/Moscow): HARD busy `53584b6f-…` 09:50–11:20 and `3a7e38ef-…` 13:30–14:00 MSK; `scheduled_work` / temporal hints remain non-blocking. No calendar writes. No remote FreeBusy.

OpenAI: no unexpected background AI/job storm. Cost Guard unchanged. `tokens_used_today` rose only with the authorized Assistant staging turn plus normal later use (`~209411` → `~227775` after staging → `251407` at closure check). No new OpenAI workload introduced by this release.

No unintended external writes. Encrypted Architect context untouched.

## Real Mattermost send

**deferred pending explicit safe target**

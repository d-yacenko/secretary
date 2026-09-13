# Current task — Telegram A

## Status

**Telegram A: implemented / awaiting Architect review**

Branch: `review/telegram-a`

Base / parent: `f0ee2b7045f4fc8459139945d5153e3528f5dfe0` (docs-only closure of Integration A)

Current production application remains: `acf035a8665f0020209b460255156ac0bde5faf6`

Production Alembic remains: **0038 / 0038**

No production deploy. No real Telegram bot configuration, setWebhook, account linking, or send.

## Scope delivered

Telegram Bot API + Business / Secretary Mode via authenticated webhook.

Private 1:1 business chats only. New inbound since active connection. No historical backfill. No mark-read. Ordinary Telegram mute is not mirrored; managed-chat selection in Telegram is the ingestion boundary.

`send_message` remains the only model-facing communication tool. Assistant continues to address conversations by Secretary Object IDs.

## Migration

**0039** parent **0038**. Tables: `telegram_accounts`, `telegram_link_states`. No 0040. No data backfill.

Local Alembic: **0038 → 0039** succeeded; **0039 → 0038** succeeded; re-upgrade to **0039**.

## Stop

Await Architect review. Do not deploy. Do not start the next phase.

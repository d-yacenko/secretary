# Current task — Voice Assistant A Final Production Corrective R2-R1

## Status

Voice Assistant A remains **CODE ACCEPTED / DEPLOYED / AWAITING FINAL USER MANUAL ACCEPTANCE**.
It is **NOT PRODUCTION ACCEPTED**. Voice B is not started.

Production application SHA remains `b0c75eaa5e879ee108afe90f152a29914d28a2f2`.
Production Alembic remains **0040 / 0040**.
Architect review of R2 (`38d1e1a281f4f129cfc3d56924f193d85dd96c90`) accepted marker receipt, client completion observability, and Teams v1.0 change-notification architecture, but **did not CODE ACCEPT** that SHA because reconciliation skipped `list_chat_messages` using `chat.lastUpdatedDateTime` (rename/membership time, not last-message time).

This R2-R1 corrective is **implemented / awaiting Architect review** on `review/voice-assistant-a` at application SHA `30fb7553ec343764dfcd8eb69b8316f9431b0b92` (parent `b51b8ecb3cd955d8c2ae0c6ee93e97396804b1e4`; previous reviewed application `38d1e1a281f4f129cfc3d56924f193d85dd96c90`). It is **not deployed**. No PRODUCTION ACCEPTED.

## Implemented (this branch, not deployed)

- Reconciliation no longer uses `chat.lastUpdatedDateTime` as message freshness.
- Graph v1.0 `GET /me/chats?$expand=lastMessagePreview`. Skip `list_chat_messages` only when a cached `last_created_at` exists, `lastMessagePreview.createdDateTime` parses, and that preview time is `<=` the watermark. Missing/malformed preview, new chat, or no watermark fail open and list messages. Overlap/watermark logic unchanged. Webhook remains the primary realtime path.
- Backend-only review/inspect grammar: review verb + optional filler (`мне` / `пожалуйста` / …) + все новые сообщения, plus «что нового / перечисли всё». Count: сколько + optional «у меня»/«сейчас» + новых сообщений. Review wins if both are present. No Flutter parser, no generic NLP.
- `reauthorizationRequired` marks the subscription `reauthorization_required` and queues Teams sync (no Graph in the webhook). `ensure()` PATCHes that row even when expiry is outside the 15-minute window. PATCH 404 recreates. `subscriptionRemoved` still recreates; `missed` still reconciles.
- Preserved: v1.0 `/users/{microsoft-user-id}/chats/getAllMessages`, `includeResourceData=false`, encrypted `clientState`, exact `validationToken` echo, targeted fetch, channels out of scope, 900s reconciliation, Retry-After, Alembic **0041**, domain snapshot receipt, client completion diagnostics.

## Stop

Push `review/voice-assistant-a` and wait for Architect review of the new application SHA. Do not deploy. Do not mark CODE ACCEPTED or PRODUCTION ACCEPTED. Do not start Voice B.

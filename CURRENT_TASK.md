# Current task — Voice Assistant A Final Production Corrective R2

## Status

Voice Assistant A remains **CODE ACCEPTED / DEPLOYED / AWAITING FINAL USER MANUAL ACCEPTANCE**.
It is **NOT PRODUCTION ACCEPTED**. Voice B is not started.

Production application SHA remains `b0c75eaa5e879ee108afe90f152a29914d28a2f2`.
Production Alembic remains **0040 / 0040**.
This corrective is **implemented / awaiting Architect review** on `review/voice-assistant-a` at application SHA `38d1e1a281f4f129cfc3d56924f193d85dd96c90` (parent `788c7c2f3e62bd5ef935a8a33be0f7c572ef7e9e`).
It is **not deployed**. No PRODUCTION ACCEPTED. Architect review of the exact SHA is required before any deploy.

## Production diagnosis (read-only)

Failed physical turn after combined deploy: «перечисли все новые сообщения» enumerated 18 items and TTS finished; marker did not move; later «сколько новых сообщений?» still 18.

- Marker tuple unchanged: `anchor_object_id=c6260075-ad7b-4e63-a4cb-ec75b09d8328`, `anchor_feed_at=2026-09-15 09:56:38+00`, `updated_at=2026-09-15 11:42:50Z` (before the 14:24Z/14:26Z turns). Marker was not mutated during diagnosis.
- Trace `192d1c3d-f91b-4de0-a9d6-221f2f9d537a` (14:24:13Z): one `list_inbox_since_review_marker`, `purpose=review`, `limit=20`, no cursor, success. Audit `truncated=true` is raw JSON vs model-visible char bound (`raw_result_chars=13564`, `model_visible_chars=6296`), not a second tool page.
- Trace `dbd4e2b2-760c-484c-9ebf-f383267237c6` (14:26:26Z): `purpose=inspect`, `limit=1` (count follow-up).
- Nginx/API: **zero** `POST /inbox/review-marker/complete` after deploy. Completion never reached the server (`advanced` / `already_current` / `conflict` / HTTP error all absent).
- Frozen traversal: one review page, limit 20, 18 items fit; production did not show a follow-up review cursor call. Completeness/receipt was not observable in capture-off traces (no `inbox_review_receipt` field in tool metadata). Client completion is fail-closed and previously swallowed exceptions with no release diagnostics.

## Implemented (this branch, not deployed)

- Deterministic `inbox_review_purpose_for_utterance` bind in `AssistantService` / `PerTurnToolBudget`: explicit enumeration cannot downgrade to `inspect`; count/peek cannot upgrade to `review`. LLM still decides whether to call the tool.
- Verified receipt observes **domain** tool output, not char-truncated model-visible pages. Extra synthetic continuation after a complete frozen snapshot does not drop the receipt.
- Client completion diagnostics (no message content): missing/stored receipt, playback finished, completion requested, `advanced` / `already_current` / `conflict`, network/API/auth/unexpected failure. Fail-closed unchanged.
- Teams Graph Change Notifications: webhook `/webhooks/teams` (challenge echo, encrypted `clientState`, no OAuth in URL), v1.0 `/users/{microsoft-user-id}/chats/getAllMessages`, non-rich notifications, create/renew/delete, reconnect cleanup, restart-safe row, missed/expired → reconciliation. Channels out of scope. Alembic **0041** `teams_subscriptions`.
- After push is proven, polling is conservative reconciliation (default Teams interval 900s, skip `list_messages` when Graph `lastUpdatedDateTime` is not newer than the chat watermark). Manual sync remains. 429 honors `Retry-After`.

## Graph v1.0 probe (sanitized)

Connected production tenant, Graph **v1.0**, resource `/users/{microsoft-user-id}/chats/getAllMessages`, `includeResourceData=false`.

- HTTP **201** create; returned resource matched; probe subscription **DELETE HTTP 204**.
- Temporary HTTPS validation echo was used only for the probe and then removed from production nginx. Production runtime remains `b0c75eaa` without the webhook.
- Do not use beta. Chat.Read delegated was sufficient for this create.

## Stop

Push `review/voice-assistant-a` and wait for Architect review. Do not deploy. Do not mark CODE ACCEPTED or PRODUCTION ACCEPTED. Do not start Voice B.

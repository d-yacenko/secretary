# Current task — Voice Assistant A Final Production Corrective R2-R2

## Status

Voice Assistant A remains **CODE ACCEPTED / DEPLOYED / AWAITING FINAL USER MANUAL ACCEPTANCE**.
It is **NOT PRODUCTION ACCEPTED**. Voice B is not started.

Production application SHA remains `b0c75eaa5e879ee108afe90f152a29914d28a2f2`.
Production Alembic remains **0040 / 0040**.
R2-R1 direction (lastMessagePreview skip, review/inspect grammar, `reauthorizationRequired` PATCH) is Architect-accepted. Application SHA `30fb7553ec343764dfcd8eb69b8316f9431b0b92` was **not CODE ACCEPTED** because `enqueue_once` permanently suppressed `updated` (and later retries after FAILED) for the same Graph message id.

This R2-R2 corrective is **implemented / awaiting Architect review** on `review/voice-assistant-a` at application SHA `7610cc1c6ce24764fae73317a6925cdce7bd27b2` (parent `acdff76dc86cfe5bd4ed82e1a5c619f480030afe`). It is **not deployed**. No PRODUCTION ACCEPTED.

## Implemented (this branch, not deployed)

- Teams targeted notifications enqueue a new `process_teams_notification` job for every validated `created`/`updated` event. No historical DONE/FAILED `enqueue_once` key. Duplicate Graph deliveries in one webhook batch are collapsed in memory; later webhooks enqueue again.
- Job payload carries sanitized `change_type` (`created` or `updated`). Unexpected `changeType` (including `deleted`) is ignored. Processing is still targeted GET + idempotent `upsert_message`.
- `JobQueueService.enqueue_once` remains for Gmail history; Teams no longer calls it.
- R2-R1 behavior preserved. Alembic **0041**. Client Dart unchanged in this SHA; debug APK rebuilt from the final application tree: `client/build/app/outputs/flutter-apk/app-debug.apk` sha256 `e6933829d12ab3ea7f4793c92c00e5a6394c339aca24bbe618b444e1e18305c9`, aapt `sdkVersion:'23'`.

## Stop

Push `review/voice-assistant-a` and wait for Architect review. Do not deploy. Do not mark CODE ACCEPTED or PRODUCTION ACCEPTED. Do not start Voice B.

# Current task — PHASE 28A awaiting architect review

## Status

PHASE 28A — User Profile & Per-User Settings Foundation: **implementation complete, awaiting architect review**.

Yandex Account UX corrective: **accepted / closed** at `70117058ce6472f2d1e3d11015a09137f8a2d047`.

Do **not** merge, deploy, or start 28B until review.

## PHASE 28A delivered

- Migration `0020_user_settings`: `user_settings` + `user_openai_credentials`
- `EffectiveUserSettingsService`: typed effective settings with deployment fallbacks
- Profile/settings APIs: `GET/PATCH /me`, `GET/PATCH /me/settings`, `PUT/DELETE /me/credentials/openai`
- Assistant message path uses per-user AI settings and OpenAI credential (deployment fallback)
- Account UI: sections **Профиль**, **ИИ**, **Подключения**; local file/folder intake removed from Account (Inbox only)
- `OPENAI_ALLOWED_ASSISTANT_MODELS` deployment policy for Assistant model choice

## Architectural rule (from 28A)

`.env` describes deployment. User Profile (database) describes the user. Provider connection credentials remain typed encrypted DB records, not a generic JSON settings blob.

## Branch

`review/phase-28a-user-profile-settings` from `70117058ce6472f2d1e3d11015a09137f8a2d047`.

## Not in 28A

- Embedding / transcription / background AI migration (28B)
- Source sync preferences (28C)
- Scheduler interval / sync depth migration
- Google Drive 403 corrective

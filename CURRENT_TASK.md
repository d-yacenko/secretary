# Current task — Voice Assistant A

## Status

**Voice Assistant A: implemented / awaiting Architect review** on `review/voice-assistant-a`.

Application SHA: `1391ce4c339f81a3c12cb65be0552dd7bc5eea10`

Canonical base (docs tip named by Architect): `54f14a86b4c6de3c29b2f14c8a8a14b4db5ddf8c`

Inherited accepted application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

Not CODE ACCEPTED. Not deployed. Do not start Voice B. Do not deploy.

## Inherited accepted phases

**Pre-Voice UI Corrective A: CODE ACCEPTED / MANUALLY VERIFIED**

Application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

User manually verified Inbox timestamp placement, consecutive adjacent swipe-delete, and phone Week 3-day presentation. Client-only. No backend/schema changes. No migration. No standalone production server deploy.

**Teams A remains: CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e`. Alembic **0040 / 0040**. The Teams external blocker does not block Voice Assistant A.

## Scope delivered

First real hands-busy turn-based voice loop over the existing Secretary Assistant.

- Server-side TTS `POST /assistant/speech`
- Same Assistant / tools / Policy Gateway / frozen Pending Action Plan / approval / Execution Gateway
- Strict fail-closed voice confirmation for `send_email` / `send_message` only
- Android + Linux playback dependency `audioplayers`; Android minSdk remains 23

## Verification (Executor)

- Backend ruff on Voice/TTS files: PASS
- `tests/test_assistant_speech.py` + Cost Guard A/B/C/C-R1: 106 passed, no live OpenAI
- `tests/test_assistant_transcribe.py` + speech: 24 passed
- Existing `test_assistant.py` / `test_assistant_action_plans.py` on this local Postgres: 29 failed with pre-existing `ai_traces_user_id_fkey` (uncommitted test users). Not introduced by Voice A; speech tests use the bootstrap user and pass.
- Client: `dart format` on changed files; `flutter analyze` 0 errors on Voice A files (pre-existing warnings in `assistant_screen.dart` / `record_voice_recorder.dart`)
- `voice_assistant_a_test.dart`: 23 passed
- Focused Assistant/Voice/API client tests: 105 passed
- Inbox/Capture voice regression + timeout: 29 passed
- Android debug APK built; `aapt dump badging` `sdkVersion:'23'`
- Linux `flutter build linux --debug`: CMake failed on this host — `audioplayers_linux` requires `gstreamer-1.0` devel (`gstreamer` runtime 1.26.7 is present; `gstreamer-devel` is not installed and sudo is unavailable)
- Live mic/TTS smoke against production was not run. Voice A is not deployed. No real external send.

## Stop

Wait for Architect review. Do not deploy. Do not mark CODE ACCEPTED. Do not start Voice B.

# Current task — Voice Assistant A R1

## Status

**Voice Assistant A R1: implemented / awaiting Architect review** on `review/voice-assistant-a`.

Application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

Parent SHA: `c35c7f73053c9f024fea8a71bc3e23c19a1391bf`

Prior application SHA: `1391ce4c339f81a3c12cb65be0552dd7bc5eea10`

Canonical base: `54f14a86b4c6de3c29b2f14c8a8a14b4db5ddf8c`

Inherited accepted application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

Architecture/safety direction PASS. **Not CODE ACCEPTED.** Not deployed. Do not start Voice B. Do not deploy.

## Inherited accepted phases

**Pre-Voice UI Corrective A: CODE ACCEPTED / MANUALLY VERIFIED**

Application SHA: `7ae954aa186ee211e6640753e384de6e1c75a93d`

User manually verified Inbox timestamp placement, consecutive adjacent swipe-delete, and phone Week 3-day presentation. Client-only. No backend/schema changes. No migration. No standalone production server deploy.

**Teams A remains: CODE ACCEPTED / DEPLOYED / PRODUCTION ACTIVATION DEFERRED — EXTERNAL ENTRA ADMIN CONSENT REQUIRED** at application SHA `eb3af922f804e6faf1d895fd14c0973981ce515e`. Alembic **0040 / 0040**. The Teams external blocker does not block Voice Assistant A.

## R1 delivered

- R1-A: `/assistant/speech` validates/prepares text before resolving the paid provider. Blank → typed 422 `speech_text_empty`. Over-limit → typed 422 `speech_text_too_long`. Invalid input does not construct the provider and makes zero OpenAI calls. Valid text with missing credential still → safe 502.
- R1-B: Linux `flutter build linux --debug` compiled successfully in a temporary openSUSE Tumbleweed container with GStreamer devel (not production VDS). `client/README.md` documents Flutter Linux toolchain, `libsecret` for existing secure-storage plugin, GStreamer devel for `audioplayers_linux`, and separate microphone runtime deps. No claim that this host lacks CMake.
- R1-C: same `test_assistant.py` + `test_assistant_action_plans.py` command on canonical base `54f14a86` and this R1 tree: **29 failed / 67 passed** both sides, same `ai_traces_user_id_fkey` signature. Recorded as **PRE-EXISTING BASELINE / NONBLOCKING**. Not repaired.

## Verification (Executor)

- Backend ruff on touched speech files: PASS
- `tests/test_assistant_speech.py` + `tests/test_assistant_transcribe.py` + Cost Guard A/B/C/C-R1: 119 passed, no live OpenAI
- A/B Assistant tests above: 29 failed / 67 passed at A and B
- Client: `dart format` on Voice A files; `flutter analyze` 0 errors (pre-existing warnings in `assistant_screen.dart` / `record_voice_recorder.dart`)
- `voice_assistant_a_test.dart`: 23 passed
- Focused Assistant/Voice/API + Inbox/Capture + timeout: 132 passed
- Android debug APK built; `aapt dump badging` `sdkVersion:'23'`
- Linux `flutter build linux --debug`: PASS in Tumbleweed builder (`gstreamer-devel` 1.28.7, `libsecret-devel`, clang 19.1.7). Linked `libaudioplayers_linux_plugin.so` / `libgstreamer-1.0.so.0`. Host still has GStreamer **runtime** 1.26.7 without `gstreamer-devel`; CMake/clang are present.
- Live mic/TTS smoke against production was not run. Voice A is not deployed. No real external send.

## Stop

Wait for Architect review. Do not deploy. Do not mark CODE ACCEPTED. Do not start Voice B.

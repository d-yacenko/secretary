# Current task — Voice Assistant A R4-R1

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4-R1 (keyguard callback + repeated lock-screen invoke + cold-start gate + ACK vs recording-ready + role-picker refresh + Linux host RUNPATH): implemented / awaiting Architect review and user physical gates. NOT CODE ACCEPTED.**

R4-R1 application SHA: `e097069dad8bcb0066e531a63f5f668e786e62ab`

R4-R1 parent (docs tip / branch tip at R4-R1 start): `638223ac07ce4d0c90c4f97596c6b542eb753f34`

R4 application SHA (rejected): `a4bb618c69ff170f223bef13dd5303d8b5961b67`

**R4 / R3 / R3-R1: not CODE ACCEPTED.**

R3-R1 application SHA: `f20c0e4bcc55bbb9e6a4b79cf052d17f8daf637b`

R3 application SHA (rejected by user-manual evidence): `fe496d23358fc3bd0b0cd407fc72258ceeec0022`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS. R2-R1 reference hygiene PASS.

Not PRODUCTION ACCEPTED. Do not start Voice B. Do not redeploy production. Do not mark R3, R4, or R4-R1 CODE ACCEPTED.

## R4-R1 facts

Client-only. No backend API. No DB migration. No production deploy.

Keyguard: `SecretaryVoiceInteractionService` overrides public `onLaunchVoiceAssistFromKeyguard()` and launches `VoiceSessionActivity` via the existing show-when-locked path. `VoiceInteractionSession.onShow()` is not the locked entry callback. Native contract tests in `VoiceAssistContractTest`.

Repeated lock-screen invoke: launch intent carries `secretary.voice_trigger`. `VoiceSessionActivity` consumes it on cold create and `onNewIntent`, queues until the plugin is ready, and emits one Flutter assist per trigger. Overlay `_started` one-shot auto-start is gone; later assists reuse `handleVoiceTrigger`.

Cold-start gate: `VoiceSessionApp` waits for auth initialization, authenticated user id, that user's `lock_screen_voice_enabled` pref, and keyguard state before the overlay can start a voice turn. Locked + pref false: no recording. Locked + pref true: start once. Regression: delayed auth + delayed pref.

ACK vs ready: native hardware / keyguard play only a short acknowledgement (haptic + tiny tone). Flutter `playReady` (`voice_start.wav`) runs only after `startRecording()` succeeds and state is `recording`. Mic start failure: no ready cue. System-assistant path does not play a ready cue in `VoiceInteractionSession`.

Assistant role: `startActivityForResult` for API 29+ `ROLE_ASSISTANT` and API 23–28 `VOICE_INPUT_SETTINGS`. Account / app resume and `onRoleResult` refresh the actual default-assistant status. Flutter does not claim ACTIVE when the picker Activity returns immediately.

Linux: host `flutter build linux --debug` still needs `gstreamer-devel` (build-time, classification C). User-visible launch failure without `LD_LIBRARY_PATH` was packaging (classification A): plugin `.so` files kept container build-tree RUNPATH, so `libduckdb.so` was `not found` (exit 127). Install now rewrites bundled libraries to `RUNPATH=$ORIGIN`. Relocatable bundle launched on this host without `LD_LIBRARY_PATH`; window appeared; authenticated Today/Inbox shell loaded. Exact launch: `env -u LD_LIBRARY_PATH /tmp/secretary-linux-r4r1-bundle/personal_secretary`.

Physical Android 3-turn latency, Volume Up ACK/ready, TTS interrupt, and Samsung system-assistant items A–I are left to the user (no remote device control this round).

## Checks

- `dart format` on R4-R1 Dart files: clean.
- `flutter analyze` on R4-R1 Dart files: no issues.
- Flutter Voice A / hardware / lock-screen / system-assistant / bootstrap / shell tests: passed.
- Android `HardwareVoiceEngineTest`: **15/15**. `VoiceAssistContractTest`: **4/4**.
- `flutter build apk --debug`; `aapt dump badging` → `sdkVersion:'23'`.
- Linux debug bundle built in Tumbleweed container; host launch as above.

## Stop

Wait for **Architect review of R4-R1** and **user physical gates**. Do not mark R3, R4, or R4-R1 CODE ACCEPTED. Do not mark PRODUCTION ACCEPTED. Do not deploy. Do not start Voice B.

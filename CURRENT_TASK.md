# Current task — Voice Assistant A R4

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R4 (immediate local feedback + Volume Up calibration + public system-assistant lock-screen entry + Linux build recovery): implemented / awaiting Architect review. NOT CODE ACCEPTED.**

R4 application SHA: `a4bb618c69ff170f223bef13dd5303d8b5961b67`

R4 parent (docs tip / branch tip at R4 start): `8a390d3fc8b8306e76ee404e5eb8a88874a1eeda`

R4 application base (R3-R1): `f20c0e4bcc55bbb9e6a4b79cf052d17f8daf637b`

**R3 / R3-R1: not CODE ACCEPTED.**

R3-R1 application SHA: `f20c0e4bcc55bbb9e6a4b79cf052d17f8daf637b`

R3 application SHA (rejected by user-manual evidence): `fe496d23358fc3bd0b0cd407fc72258ceeec0022`

R3 docs tip: `03cb692d0a032f2e069d3f5718dcc95bfeb41f03`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS. R2-R1 reference hygiene PASS.

Not PRODUCTION ACCEPTED. Do not start Voice B. Do not redeploy production. Do not mark R3 or R4 CODE ACCEPTED.

## R4 facts

Client-only. No backend API. No DB migration. No production deploy.

Immediate feedback: accepted hardware trigger plays a native `ToneGenerator` start earcon + short haptic before the Flutter recorder starts. Stop/process plays a distinct native stop earcon. Flutter also has local WAV assets (`voice_start.wav` / `voice_stop.wav`) for on-screen mic. No OpenAI/TTS/network call for these cues. Nothing persisted. Debug tag `SecretaryVoiceTiming` records monotonic marks only (no transcript/body/token/audio).

Volume Up double-press window: **500 ms** (was 350 ms). Chosen as one fixed window in the 450–550 ms band after user evidence that 350 ms felt non-obvious while successful doubles already worked. No extra user setting. Failed single still raises volume exactly once; flags are `FLAG_SHOW_UI | FLAG_REMOVE_SOUND_AND_VIBRATE`. Successful double: one Voice trigger, no volume change. Hold: volume, no Voice. Native log `doubleDeltaMs` uses `KeyEvent.eventTime`.

Foreground Volume Up double remains a foreground fallback. It is not promised while Secretary is backgrounded.

Public Android assistant path (user opt-in): `VoiceInteractionService` + session, `supportsAssist` / `supportsLaunchVoiceAssistFromKeyguard`, `ROLE_ASSISTANT` via `RoleManager` on API 29+, else `Settings.ACTION_VOICE_INPUT_SETTINGS`. minSdk remains **23**. Account shows default-assistant status, a button to open the OS assistant picker, and a per-user lock-screen Voice switch default **off** (`lock_screen_voice_enabled.$userId`). System assistant invocation reuses `AssistantController.handleVoiceTrigger()`. Unlocked: `MainActivity` extra `secretary.voice_trigger`. Locked: `VoiceSessionActivity` over keyguard with route `/voice_session` — status only, no Inbox/history.

Lock-screen safety: ordinary voice runs only when lock-screen Voice is enabled. External write approve is blocked while `lockScreenSession && keyguardLocked`; spoken line is «Нужно разблокировать устройство, чтобы подтвердить отправку.» Frozen send_email/send_message bodies are not narrated over the lock. Exact «Нет» still rejects. After unlock, visual approve remains the existing Pending Action Plan path.

Linux voice hardware remains out of scope. Linux `flutter build linux --debug` succeeded in the documented Tumbleweed container with GTK / libsecret-devel / gstreamer-devel. Host still lacks `gstreamer-devel` (not an application regression). First container miss was `libsecret-1` devel (package, not app). CMake 4.x left `CMAKE_INSTALL_PREFIX=/usr/local`; `client/linux/CMakeLists.txt` now always installs into the Flutter bundle dir and creates an empty `native_assets/linux` directory. Runnable bundle: `/tmp/secretary-linux-r4-bundle`.

## Checks

- `flutter analyze` on R4 Dart files: no errors (pre-existing warnings only).
- Flutter Voice A / hardware / lock-screen / system-assistant tests: **124/124**.
- Android `HardwareVoiceEngineTest`: **15/15**.
- `flutter build apk --debug`; `aapt dump badging` → `sdkVersion:'23'`.
- Linux debug bundle built in container as above.

## Physical (SM-T355 `8430b607`, Android 7.1.1 / API 25, no One UI, no Side/Bixby)

Fresh debug APK, cold start: `plugin created protocol=secretary.hardware_voice.v1`, `SystemAssistantPlugin attached`, `MainActivity plugin attached`. Binding armed. Single Volume Up: one `raise-volume` after the 500 ms window. Batched `input keyevent 24 24` accepted doubles: `doubleDeltaMs=35` then `25`, window 500; native `cue=start` then `cue=stop`; Flutter `feedback t_ms=28`, `recording_ready t_ms=1710`, stop `audio_ready t_ms=244`. Native start cue latency on that trigger ≈ 92 ms elapsedRealtime; stop cue ≈ 6 ms. Full network turn (transcription / Assistant / speech RTT) was not completed on this tablet this session. Current default assistant remains Google `GsaVoiceInteractionService`. Executor did not adb-force Secretary as the system assistant. Samsung Side/Bixby long-press was not testable on SM-T355. User’s other Samsung with Side button was not connected.

## Stop

Wait for **Architect review of R4**. Do not mark R3 or R4 CODE ACCEPTED. Do not mark PRODUCTION ACCEPTED. Do not deploy. Do not start Voice B.

# Current task — Voice Assistant A Lock-screen Launcher A / R1 UI polish

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**Lock-screen Launcher A / R1 UI polish: implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.**

Lock-screen Launcher A R1 UI polish application SHA: `b99bbad50c7d0d8a8edbef8d05781a2c7fb9de23`

Lock-screen Launcher A parent application SHA: `6688a2319369e3280b1b86223ada50119878f3c6`

Lock-screen Launcher A R1 parent / previous docs tip: `b7df1d301d15bde0f0ae778b3ff0bc11e32f46c8`

**R4-R4-R2 is Architect scope-accepted** (on-screen microphone strictly silent-output). Application SHA: `276fe709527a7d300660cbe444ae40ee520e7e05`

R4-R4-R1 application SHA (chronological Inbox review; backend unchanged; do not deploy yet): `0ab2cb6f1ae2a373f8b719314777824434c9adda`

R4-R4 application SHA (not deployed; do not deploy): `dc3568d2cb2e4808f4a736933b0ce615553a11eb`

R4-R3 application SHA (capture corrective physically validated by Architect): `d121cf90e351612275663c6845a76e9dd80ed587`

**Lock-screen Launcher A / R1 UI polish / R4-R4-R2 / R4-R4-R1 / R4-R4 / R4-R3 / R4-R2 / R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R1 PASS. R2 marker architecture PASS (auto-move refined in R4-R4). R2-R1 reference hygiene PASS. R4-R2 output policy refined in R4-R4-R2: screen mic is dictation-only. R4-R3 capture physically validated. Inbox Conversation Compaction A remains backlog / not started.

Do not start Voice B. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED.

## Lock-screen Launcher A / R1 UI polish facts

Client-only. Google / Gemini remains the Android system/default assistant. Account no longer invites the user to «Выбрать Секретарь помощником…» and does not call `requestAssistantRole` from ordinary Profile UI or when opening driving mode. Dormant `VoiceInteractionService` / `ROLE_ASSISTANT` native code remains unused as the product path.

Product path: explicit lock-screen / driving launcher. Per-user pref `lock_screen_voice_enabled.<userId>` stays default OFF. When enabled, Account shows «Открыть режим вождения», which starts `VoiceSessionActivity` in `launcher` mode (no `EXTRA_VOICE_TRIGGER`, no auto-record). Existing `assistInvoke` + `secretary.voice_trigger` auto-record path is preserved for dormant system-assistant code.

`VoiceInvocationSource.lockScreenLauncher`: `isVoiceInput=true`, `isHandsFree=true`, frozen for the whole turn. Under R4-R4-R2, `handsFreeEnabled` auto-speaks; `never` does not. Screen mic remains silent-output.

`VoiceSessionActivity` keeps `showWhenLocked` / `turnScreenOn` (API 23 window flags without `FLAG_KEEP_SCREEN_ON`). `onStart` re-applies those flags. The device may sleep. If Android kills the activity/process entirely, Launcher A does **not** resurrect it; the user reopens driving mode. No AccessibilityService, no always-listening microphone, no SCREEN_ON relaunch, no ongoing foreground service, no lock-screen notification fallback.

Unauthenticated overlay never shows `AuthSetupScreen` / password fields; only «Откройте Секретарь после разблокировки и войдите в аккаунт.» plus Close.

Existing `lockScreenSession` fail-closed writes remain: while keyguard is locked, EXTERNAL_WRITE / COMMUNICATE does not execute. Inbox R4-R4 verified complete review + completed TTS may advance the marker; interrupted TTS does not. Backend R4-R4-R1 is untouched. No DB migration. Production not mutated.

R1 UI polish (client-only; ordinary Secretary `MaterialApp` stays light-only):

- Dedicated `VoiceSessionApp` uses light + dark `ThemeData` and `ThemeMode.system`. System dark mode must not show a white driving overlay.
- Large driving button keeps its touch target; two concentric `BoxShadow` halos with 220 ms state transitions. IDLE primary; RECORDING `0xFFE53935`; transcribing/thinking muted `surfaceContainerHighest`; SPEAKING tertiary. No looping animation. Quiet «Завершить режим вождения» remains.
- Android Account order: Profile / Owner → «Голос с экрана блокировки» → interface text scale → remaining sections. Section is not duplicated lower. Hidden where unsupported.
- Device-local UI text scale: min `0.50`, default `1.00`, max `1.30`, slider 5% steps (`divisions=16`). Existing stored `0.90`–`1.30` unchanged; new `0.50`–`0.85` persist; invalid values clamp. No server/DB setting. Android system font untouched.
- Inbox «Просмотрено досюда» uses canonical `kInboxReviewMarkerAccent = Color(0xFFFF4D2E)`, ~2 px divider, semibold label. Marker tuple / backend APIs unchanged.
- Review rail availability (`inboxUsesReviewRail`) is Android + iOS + Linux + Windows + macOS. Swipe-to-Remove (`inboxUsesSwipeToRemove` / `inboxUsesTouchReviewRail`) stays Android/iOS. Linux click on the rail persists the marker without opening the card; top rail still resets; hover cursor/emphasis on desktop. Draggable marker remains as a secondary desktop affordance.

## Checks

- Focused Flutter Voice + launcher + theme + Account + Inbox rail/swipe + text-scale regressions: **154 passed**.
- Android unit tests (`VoiceAssistContractTest`, `HardwareVoiceEngineTest`): passed.
- `flutter analyze` on touched Dart: clean.
- Android debug APK rebuilt: `sdkVersion:'23'`.
- APK: `client/build/app/outputs/flutter-apk/app-debug.apk` sha256 `596377593febc67de5dead7c2bcd7eb0d7137c48071dc93cca6d7d46025e066c`.
- Linux: host `gstreamer-devel` still missing (classification C); no Linux rebuild/launch on this host.

## Remaining

Architect review of Lock-screen Launcher A R1 UI polish application SHA `b99bbad50c7d0d8a8edbef8d05781a2c7fb9de23`. After PASS, Architect issues the exact-SHA deploy of the combined accepted backend/client tree. Physical user gate (Samsung, not Executor): Google still default; enable lock-screen voice; open driving mode; idle large button; Power off ~5–10s; Power wake; **dark overlay if system dark mode**; button visible without PIN; tap → ready cue → speak → tap stop → spoken answer; second turn; locked send must not execute; exit; screen mic silent; «Окей Google» still Google. If Samsung hides/kills the activity after sleep: stop and report; do not add a notification/FGS workaround without Architect review.

## Stop

Wait for Architect. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED. Do not start Voice B.

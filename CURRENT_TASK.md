# Current task — Voice Assistant A Lock-screen Launcher A / R1 functional completion

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**Lock-screen Launcher A / R1 functional completion + accepted UI polish: implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.**

Lock-screen Launcher A R1 functional application SHA: `319a99e5c2d55750fd9949f8a31fd137c45b703b`

Lock-screen Launcher A R1 UI polish parent (ACCEPTED): `b99bbad50c7d0d8a8edbef8d05781a2c7fb9de23`

Lock-screen Launcher A R1 parent / previous docs tip: `489eb9c1300fac11e6766a9cc155d129cb9cfd2a`

**R4-R4-R2 is Architect scope-accepted** (on-screen microphone strictly silent-output). Application SHA: `276fe709527a7d300660cbe444ae40ee520e7e05`

R4-R4-R1 application SHA (chronological Inbox review; backend unchanged; do not deploy yet): `0ab2cb6f1ae2a373f8b719314777824434c9adda`

R4-R4 application SHA (not deployed; do not deploy): `dc3568d2cb2e4808f4a736933b0ce615553a11eb`

R4-R3 application SHA (capture corrective physically validated by Architect): `d121cf90e351612275663c6845a76e9dd80ed587`

**Lock-screen Launcher A / R1 / R4-R4-R2 / R4-R4-R1 / R4-R4 / R4-R3 / R4-R2 / R4-R1 / R4 / R3 / R3-R1: not CODE ACCEPTED.**

R1 PASS. R2 marker architecture PASS (auto-move refined in R4-R4). R2-R1 reference hygiene PASS. R4-R2 output policy refined in R4-R4-R2: screen mic is dictation-only. R4-R3 capture physically validated. Inbox Conversation Compaction A remains backlog / not started.

Do not start Voice B. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED.

## Lock-screen Launcher A / R1 facts

Client-only. Google / Gemini remains the Android system/default assistant. Account no longer invites the user to «Выбрать Секретарь помощником…» and does not call `requestAssistantRole` from ordinary Profile UI or when opening driving mode. Dormant `VoiceInteractionService` / `ROLE_ASSISTANT` native code remains unused as the product path.

Product path: explicit lock-screen / driving launcher. Per-user pref `lock_screen_voice_enabled.<userId>` stays default OFF. When enabled, Account shows «Открыть режим вождения», which starts `VoiceSessionActivity` in `launcher` mode (no `EXTRA_VOICE_TRIGGER`, no auto-record). Existing `assistInvoke` + `secretary.voice_trigger` auto-record path is preserved for dormant system-assistant code.

`VoiceInvocationSource.lockScreenLauncher`: `isVoiceInput=true`, `isHandsFree=true`, frozen for the whole turn. Under R4-R4-R2, `handsFreeEnabled` auto-speaks; `never` does not. Screen mic remains silent-output.

`VoiceSessionActivity` keeps `showWhenLocked` / `turnScreenOn` (API 23 window flags without `FLAG_KEEP_SCREEN_ON`). `onStart` re-applies those flags. The device may sleep. If Android kills the activity/process entirely, Launcher A does **not** resurrect it; the user reopens driving mode. No AccessibilityService, no always-listening microphone, no SCREEN_ON relaunch, no ongoing foreground service, no lock-screen notification fallback.

Unauthenticated overlay never shows `AuthSetupScreen` / password fields; only «Откройте Секретарь после разблокировки и войдите в аккаунт.» plus Close.

### Ephemeral driving session authorization

Opening «Открыть режим вождения» from the authenticated unlocked Secretary UI arms an in-memory `DrivingVoiceSessionRegistry` nonce, puts it on the launcher intent (`secretary.driving_voice_session_id`), and `VoiceSessionActivity` re-validates it against the live registry. Not SharedPreferences. Not server state. Does not survive process death/reboot (stale extra validates false). Cleared on «Завершить режим вождения», `VoiceSessionActivity` finish, and auth loss. `assistInvoke` / locked open / default process state do not arm.

Voice is **not** biometric identity. The security boundary is the explicit Driving Mode launch while authenticated and unlocked.

### Locked voice approval

`blocksExternalWrite` remains `lockScreenSession && keyguardLocked`. Generic visual approve while locked stays blocked.

Canonical helper `mayVoiceApproveLockedPendingPlan` is the only locked voice-approval bypass. It requires all of: valid driving authorization; pending plan bound to the same session id, `lockScreenLauncher` source, and plan id; exactly one pending plan; `PendingAction.planIsVoiceApprovable` (still only `send_email` / `send_message`; mixed/unsupported/destructive stay blocked). Binding is in-memory and is cleared when the plan ends, the session changes, Driving Mode exits, or auth is lost. Typed / screenMic / previous-session plans cannot leak into driving approval.

Eligible locked driving communication uses the existing frozen deterministic preview (full body + «Отправить?»), not «Нужно разблокировать устройство». Approval arms only on successful TTS `onFinished`. Interrupted/error narration stays unarmed. Exact «Да» executes the frozen plan through the normal approval / Execution Gateway while still locked. Exact «Нет» rejects. Ambiguous speech keeps the existing retry/fail-closed path. After execute, existing resume/final-result speech is used.

R1 UI polish from `b99bbad` is preserved. Inbox R4-R4 marker semantics are unchanged. Backend unchanged. No DB migration. Production not mutated.

## Checks

- Focused Flutter Voice + driving session + launcher + theme + Account + Inbox rail/swipe + text-scale + Voice A regressions: **178 passed**.
- Android unit tests (`VoiceAssistContractTest`, `DrivingVoiceSessionTest`, `HardwareVoiceEngineTest`): passed.
- `flutter analyze` on touched Dart: clean.
- Android debug APK rebuilt: `sdkVersion:'23'`.
- APK: `client/build/app/outputs/flutter-apk/app-debug.apk` sha256 `6b546c63721023af4eda54983e4e5e82f6979abc847b3cbfaedddfca1ce7fa11`.
- Linux: host `gstreamer-devel` still missing (classification C); no Linux rebuild/launch on this host.

## Remaining

Architect review of Lock-screen Launcher A R1 functional application SHA `319a99e5c2d55750fd9949f8a31fd137c45b703b`. After PASS, Architect issues the exact-SHA deploy of the combined accepted backend/client tree. Physical user gate (Samsung, not Executor): Google still default; enable lock-screen voice; open driving mode while unlocked; idle large button; Power off ~5–10s; Power wake; dark overlay if system dark mode; button visible without PIN; tap → ready cue → speak → tap stop → spoken answer; second turn; **locked send_email/send_message: full narration then exact «Да» executes while still locked**; unsupported locked writes remain blocked; exit; screen mic silent; «Окей Google» still Google. If Samsung hides/kills the activity after sleep: stop and report; do not add a notification/FGS workaround without Architect review.

## Stop

Wait for Architect. Do not deploy. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED. Do not start Voice B.

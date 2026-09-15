# Current task — Voice Assistant A Final Client Shortcut Completion

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**Final Inbox/Source Corrective: Architect CODE REVIEW PASS. NOT DEPLOYED.** Application SHA `f50b56c6d874148963479830ad25af5b65522c20`. Preserve all backend changes exactly.

**Lock-screen Launcher A / R1 functional completion remains implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.** Application SHA `319a99e5c2d55750fd9949f8a31fd137c45b703b`.

**Final Client Shortcut Completion: implemented / awaiting Architect review. NOT CODE ACCEPTED. NOT PRODUCTION ACCEPTED. NOT DEPLOYED.** Application SHA `b0c75eaa5e879ee108afe90f152a29914d28a2f2` (parent docs tip `afaab5859b57c5a34c9dcb5eb14f92e790dcbae0`; accepted backend/source base `f50b56c6d874148963479830ad25af5b65522c20`).

Do not start Voice B. Do not deploy. Do not restart production worker. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED.

## Client delivered

Android-only Driving Mode shortcut in the main app, next to the existing Account action:

- Narrow: AppBar `actions`, immediately left of `shell_account_button` (`Icons.account_circle`).
- Wide: NavigationRail `trailing`, immediately above the same Account button.
- Icon `Icons.directions_car`, tooltip «Режим вождения».
- Linux/desktop: hidden (`drivingModeShortcutVisible` / `systemAssistantSettingsVisible`).
- `lock_screen_voice_enabled.<userId> == true` → existing `openLockScreenLauncher` once.
- `false` → compact confirmation «Разрешить голосовой режим на экране блокировки?»; Cancel mutates nothing; «Включить и открыть» persists via existing `setLockScreenVoiceEnabled(true)` then the same launcher once.
- Account/Profile Driving Mode section unchanged. No second launcher. No `ROLE_ASSISTANT`. No orb redesign. Backend/source-sync/review-marker untouched.

## Checks

- `test/shell/driving_mode_shortcut_test.dart` (visibility Android/Linux, enabled launch, confirmation, cancel, confirm+persist, Profile entry).
- Regressions: `test/shell/app_shell_test.dart`, `test/account/system_assistant_account_test.dart`, `test/assistant/lock_screen_launcher_test.dart`, `test/assistant/driving_locked_voice_flow_test.dart`, `test/assistant/voice_output_policy_test.dart` — **59 passed**.
- `flutter analyze` on touched files: clean. Project analyze still has pre-existing issues only.
- `flutter build apk --debug`: `client/build/app/outputs/flutter-apk/app-debug.apk`
- sha256: `b127fb5b061d6910c037c43576bf225a8a612f2bac30b79b0d1e0700a5bb3729`
- `aapt dump badging` `sdkVersion:'23'`

## Remaining

Architect review of this client SHA. Combined tree still includes undeployed backend `f50b56c`. After PASS, Architect issues exact-SHA deploy. Do not restart production worker without the IMAP-timeout tree.

## Stop

Wait for Architect. Do not deploy. Do not restart production worker. Do not mark CODE ACCEPTED / PRODUCTION ACCEPTED. Do not start Voice B.

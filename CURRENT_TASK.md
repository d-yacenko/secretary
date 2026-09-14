# Current task — Voice Assistant A R3

## Status

**Voice Assistant A: CODE ACCEPTED / DEPLOYED / AWAITING USER MANUAL ACCEPTANCE** on `review/voice-assistant-a`.

Accepted / exact deployed application SHA: `5ef2a2db117dc5a1c0ac54bad3d0e897ebcf6357`

Previous production SHA: `eb3af922f804e6faf1d895fd14c0973981ce515e`

**R3 (configurable Android hardware-button trigger): awaiting Architect review. Not CODE ACCEPTED.**

R3 application SHA: `fe496d23358fc3bd0b0cd407fc72258ceeec0022`

R3 parent (docs tip after Voice A deploy): `9d7587432afccf9eafc62c98f02035db68f33986`

R2 application SHA: `244cdd28b81e7d8b33b6f78938fa062c03a82b3a`

R1 application SHA: `89c7e0bf9fc74dbfcc8a02f9a6795b4f3deae82e`

R1 PASS. R2 marker architecture/semantics PASS. R2-R1 reference hygiene PASS.

Not PRODUCTION ACCEPTED. Do not start Voice B. Do not redeploy production. Do not mark R3 CODE ACCEPTED.

## R3 facts

Client-only. No backend API. No DB migration. Binding is local to this Android device and namespaced by authenticated Secretary user id in `shared_preferences` (`hardware_voice_binding.$userId`). Logout disables the native binding immediately and keeps the namespaced pref for a later login of the same user.

Foreground-only: Secretary `MainActivity` must be active. No background service, wake lock, MediaSession global interception, default-assistant role, or Accessibility.

Canonical trigger: `AssistantController.handleVoiceTrigger()`. On-screen mic uses the same path. Hardware events in Learn/Test do not start Voice.

Navigation: if the AppShell route is not current or `Navigator.canPop()` (Account, object detail, capture, OAuth, other pushed routes), ignore rather than pop. Otherwise select «Секретарь» and invoke the canonical trigger.

Double-press window: **350 ms**. Learn/test timeout: **9000 ms**. Volume Up is forced to double-press. Generic OEM keys default to single-press. Held KeyDown repeats are not extra taps.

Volume Up fallback delays the first short press for 350 ms, then `AudioManager.adjustSuggestedStreamVolume(ADJUST_RAISE, USE_DEFAULT_STREAM_TYPE, FLAG_SHOW_UI)` once if no second press; a second press inside the window emits one Voice trigger and does not raise volume. Long-press raises volume and does not start Voice.

Rejected Learn keys: HOME 3, BACK 4, CALL 5, ENDCALL 6, VOLUME_DOWN 25, POWER 26, MENU 82, VOLUME_MUTE 164, APP_SWITCH 187, SLEEP 223, WAKEUP 224, SOFT_SLEEP 276, SYSTEM_NAVIGATION_* 280–283.

MethodChannel `secretary/hardware_voice`: Flutter→native `configure` / `startLearn` / `cancelLearn` / `startTest` / `cancelTest`; native→Flutter `onVoiceTrigger` / `onLearnResult` / `onTestResult`.

Linux: no hardware-button selector. No Linux keyboard shortcut in R3.

Checks: `dart format` on R3 Dart files; `flutter analyze` on R3 files (1 pre-existing `unnecessary_null_comparison` in `assistant_screen.dart` desktop-drop path); Flutter Voice A / hardware / shell / profile tests passed (127); Android `HardwareVoiceEngineTest` 12/12; `flutter build apk --debug`; `aapt dump badging` → `sdkVersion:'23'`. `account_layout_polish_test` two lazy-ListView findings also fail on HEAD without R3 Account wiring (pre-existing).

Device smoke on SM-T355 was started then stopped because the user was busy. Partial: R3 debug APK installed; Account section «Голосовой помощник» visible as device-local; Volume Up double preset saved (`Громкость +` / `Двойное нажатие`); Learn dialog copy shown. Not completed: single Volume Up ordinary volume, double Volume Up → recording, second double while recording, TTS interrupt. No Bixby/OEM extra key on this tablet.

## Stop

Wait for **Architect review of R3**. Do not mark R3 CODE ACCEPTED. Do not mark PRODUCTION ACCEPTED. Do not deploy. Do not start Voice B.

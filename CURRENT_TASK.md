# Current task — PHASE 20 (awaiting review)

## Status

PHASE 19.5 accepted / closed.

PHASE 20 implemented: Flutter bootstrap + Manual Capture vertical slice.

PHASE 21 not started.

## Delivered (PHASE 20)

- Single Flutter app in `client/` for Android + Linux
- Bearer token auth (`GET /me`), secure token store, server URL preferences
- Typed `SecretaryApiClient` (`/health`, `/me`, `/connections`, `/capture/task`)
- Adaptive shell with five placeholder destinations + prominent Capture
- Working Manual Capture (exact text preserved, no client-side OpenAI)
- `CaptureDraft` contract with context/dependency object ID lists for later phases
- Account screen with `/me` display name and `/connections` status (no secrets)
- Client tests (API, auth, capture, shell, security regressions)
- `client/README.md` with run/build instructions

## Verification

```bash
cd client
flutter pub get
flutter analyze
flutter test
flutter build apk --debug   # verified where Android SDK available
```

Linux: `flutter build linux` requires CMake/clang/GTK on the host; not available on current dev machine.

## STOP

Do not start PHASE 21 until PHASE 20 is accepted.

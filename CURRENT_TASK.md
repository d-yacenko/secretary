# Current task — PHASE 20 (awaiting final acceptance)

## Status

PHASE 19.5 accepted / closed.

PHASE 20 final corrective implemented (safe URL composition, auth navigation boundary, capture session cleanup, Android INTERNET).

PHASE 21 not started.

## Final corrective (this cycle)

- Structured `Uri` API endpoint composition (no string concat)
- `AuthGate` + session termination pops pushed routes on 401/logout
- `CaptureController.resetSession()` on logout / user change / auth failure
- Android `INTERNET` in main manifest
- Removed public bearer token getter from API client

## Verification

```bash
cd client
flutter analyze
flutter test
flutter build apk --debug
flutter build apk --release
```

Linux: `flutter build linux` still requires CMake/clang/GTK on the host (not available here).

## STOP

Do not start PHASE 21 until PHASE 20 is accepted.

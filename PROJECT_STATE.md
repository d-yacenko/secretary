# Project state

## Current phase

PHASE 20 — Flutter client: **final corrective implemented, awaiting final acceptance**

PHASE 19.5 — auth, connections, manual capture: **accepted / closed**

PHASE 19 — local files and huge datasets: **accepted / closed**

PHASE 18 — resource registration: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) completed; required before PHASE 20 Flutter.

## Working components

- PHASE 00–19: (prior phases, PHASE 19 closed)
- PHASE 19.5:
  - Bearer auth, `/me`, `/connections`, manual capture
  - Async embed indexing for captured tasks
  - Bounded pinned-context excerpts in context assembly
  - HTTP two-user isolation regressions
- PHASE 20 (client):
  - Flutter app in `client/` (Android + Linux platforms)
  - Bearer auth setup, secure token storage, typed API client
  - Structured API URL composition; auth session boundary with navigation reset
  - Capture draft cleared on logout / user identity change
  - Adaptive shell (Inbox, Today, Graph, Search, Assistant placeholders)
  - Manual Capture end-to-end via `POST /capture/task`
  - Account/connections status surface
  - Android `INTERNET` permission in main manifest
  - `flutter analyze` + `flutter test` pass (43 tests)
  - Android debug + release APK builds verified
  - Linux build blocked on missing host toolchain (CMake/clang/GTK); documented in `client/README.md`

## Not done

- PHASE 21 (Flutter Inbox and Today)

## Next phase

PHASE 21 — Flutter Inbox and Today (not started).

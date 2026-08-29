# Project state

## Current phase

PHASE 21 — Flutter Inbox, Today, Object Detail, task-proposal acceptance: **implemented, awaiting review**

PHASE 20 — Flutter client: **accepted / closed** (manual Linux smoke completed by user)

PHASE 19.5 — auth, connections, manual capture: **accepted / closed**

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`.

## Working components

- PHASE 00–20: (prior phases, PHASE 20 closed)
- PHASE 21:
  - Task-proposal notification Accept materializes confirmed local task (`result_object_id` idempotency)
  - `GET /today` read model (tasks, calendar events, important notifications)
  - `GET /notifications?status=unresolved` pseudo-filter
  - Flutter Inbox (Accept / Ignore / Open context)
  - Flutter Today (tasks, calendar, important notifications)
  - Object Detail with neighbors/context and **Use as task context**
  - Capture draft shows attached context labels; session cleanup preserved
  - Backend + client tests; `flutter analyze` + `flutter test` pass
  - Android debug APK build verified
  - Linux build still requires host toolchain (CMake/clang/GTK); see `client/README.md`

## Not done

- PHASE 22 (not started)
- Search UI, Assistant, voice, graph editor

## Next phase

PHASE 22 — not started.

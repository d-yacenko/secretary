# Current task — Unified Week A — Read-only unified calendar projection

## Authorization

This phase is Architect-authorized. Executor may implement only this scope and must STOP after report. Do not choose or start the next phase.

## Base / production

- Production application SHA: `4945f19e6f6c134b435066d099d9b84d21612ce2`
- Role-boundary hygiene branch head is the required implementation base for this phase.
- Inbox Quick Actions — Swipe to Remove A / A-R1: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Design Quality Pass C: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Alembic: **0034 / 0034** unless this phase proves a migration is strictly necessary (expected: no migration)
- Android minSdk: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`

## Goal

Build the first read-only **Unified Week** view: one derived weekly schedule that merges already-materialized Google Calendar and Yandex Calendar event Objects.

This is NOT a third calendar and creates no independent calendar records.

Authoritative hard commitments remain provider calendar events already synchronized into Secretary.

## Scope A

- Add one backend read projection / endpoint for a requested week.
- Return only already-materialized calendar event Objects in the requested temporal range.
- Merge Google Calendar + Yandex Calendar in one chronological response.
- Preserve provider identity and Object id for opening existing Object Detail / provider source actions.
- Add a Flutter Week surface reachable from the temporal area, preferably as a lightweight `Сегодня | Неделя` mode rather than a new top-level product area.
- Show seven days with clear day/date headers and compact chronological event rows.
- Handle overlapping events visually without inventing availability semantics yet.
- Read-only: no event creation/edit/delete from Week A.

## Temporal semantics

- Use existing materialized recurrence occurrence Objects; do not expand RRULEs in the client or Week endpoint.
- Query by event interval overlap with the requested week, not by Inbox feed semantics.
- All-day and timed events must be represented distinctly if current normalized data supports it.
- Provider calendars are authoritative hard commitments.
- Tasks, deadlines, Telegram/message hints, inferred temporal facts, and proactive proposals are NOT part of Week A.
- Do not mark non-calendar data as busy.

## Week boundary

Use the user's existing timezone semantics consistently with Today/current backend behavior. Define a deterministic Monday-starting 7-day interval and test timezone/DST boundaries. Do not introduce device-only date math that can disagree with backend results.

## Non-goals

Do NOT implement in A:

- free/busy or Availability A;
- conflict warnings;
- event mutation;
- task execution intervals;
- task deadlines in the week grid;
- temporal hints from messages;
- Telegram connector;
- a third writable Secretary calendar;
- recurrence expansion;
- provider sync changes;
- Graph Advanced UX.

## Quality / safety

- Keep backend/provider writes at zero.
- Prefer existing Object/query/service abstractions; no new calendar data model if avoidable.
- No provider-specific duplicate business logic in the Flutter client.
- Keep Android/Linux first-class.
- Preserve source minSdk and APK manifest minSdk at 23.
- Do not read/decrypt/modify/recreate/re-encrypt/commit `secretary_architect_context_encrypted.md`.

## Acceptance

Executor must deliver focused backend + Flutter tests for range boundaries, merged provider ordering, recurrence occurrence use, empty days, overlap presentation, navigation/detail identity, phone/tablet/desktop layout, and timezone/DST behavior as applicable.

Run changed backend tests, changed Dart analyze, focused Flutter tests, canonical Android `./gradlew :app:assembleDebug`, source/merged/APK minSdk23 proof, and Linux release build.

No deploy before Architect review.

After commit/push, report exact parent/base, changed files, API/projection contract, timezone/week-boundary rule, test totals, analyze/build results, migration/schema status, and STOP.

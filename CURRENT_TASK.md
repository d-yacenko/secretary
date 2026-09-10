# Current task — Design Quality Pass C-R1 — Bookmark Hit Target + Graph Reconcile Failure Recovery

## Status

Pass C architecture/presentation direction **ACCEPTED**. C-R1 corrective is implemented on `review/design-quality-pass-c` and **awaiting Architect review**.

Do **not** deploy. Do **not** start Graph Advanced UX. Do **not** redesign Pass C.

## Production / lineage

- Canonical production/base: `9f0abe0d44cb91dbf0a555f2ae79aa5e2b21d25b`
- Pass C SHA / exact C-R1 parent: `b0cf7c9d63dcf19b2b4933d6b81395e5ae06b3a1`
- Temporal Correctness C / C-R1: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Inbox Workflow Controls A / A-R3: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Temporal A: **CLOSED / DEPLOYED**
- Temporal B: **CLOSED / DEPLOYED / PRODUCTION ACCEPTED**
- Alembic: **`0034 / 0034`** (no migration in this phase)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- Real-user `auto_label_enabled`: **true**
- Graph Bookmark Presentation: **IN SCOPE for Pass C only**
- Graph Advanced UX: **NOT STARTED / later**
- Encrypted Architect context: untouched

## C-R1 scope

Two focused client-only fixes:

- active `ObjectBookmarkRibbon` keeps the small swallow-tail glyph (`kBookmarkTabSize` 16×20) and adds a transparent ~36×36 hit target (`kBookmarkTabHitSize`); Graph node overlay stays non-interactive
- `ObjectBookmarkController.reconcileVisible` returns `Future<bool>`; Graph commits `_reconciledVisibleIds` only after a successful reconcile of the current visible set

No backend/schema/API/migration/recurrence changes.

## Technical debt (record only, not fixed here)

- Yandex attendee canonicalization / passive-sync metadata churn
- Provider brand assets: deferred
- Two pre-existing Graph delete text-finder tests (not in C-R1 scope)

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.

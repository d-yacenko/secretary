# Current task — Inbox Workflow Controls A-R3

## Status

Inbox Workflow Controls A is **CLOSED / DEPLOYED / PRODUCTION ACCEPTED** at `d824bdfca17bae652e3f3e19042b299475372e08`.

Current corrective:

**Inbox Workflow Controls A-R3-R1 — Bookmark reconcile ABSENT vs READ FAILURE** is implemented and **awaiting Architect review** on `review/inbox-workflow-controls-a`.

A-R3 (universal bookmarks, forgiving marker, Today subtitle alignment) remains on this branch. Production identity diagnosis: **ACCEPTED** (`EXPECTED_RECURRENCE_MATERIALIZATION`). No calendar/backend identity changes.

Do **not** deploy. Do **not** start Design Quality Pass C. Do **not** start Graph Advanced UX / Graph bookmark visualization.

Temporal Correctness A/B remain **CLOSED**. Do not reopen recurrence/calendar or Tasks redesign.

## Production / lineage

- Canonical production/base/parent: `d824bdfca17bae652e3f3e19042b299475372e08`
- Inbox Workflow Controls A (incl. A-R1/A-R2): **CLOSED / DEPLOYED / PRODUCTION ACCEPTED** at that SHA
- Alembic on production: **`0034 / 0034`** (no 0035; this corrective is Flutter-only)
- Android `minSdk`: **23**
- Proactive: **OFF**
- Design Quality Pass C: **NOT STARTED**
- Graph bookmark visualization: **DEFERRED** (must consume the same `ObjectBookmarkController` later)
- Encrypted Architect context: untouched

## A-R3 scope (Flutter)

- Session-scoped `ObjectBookmarkController`: one bookmark state per `(user, object_id)` across Inbox, Today, Search, Object Detail
- Shared swallow-tail `ObjectBookmarkGlyph` (Material bookmark / bookmark_border silhouette)
- Unbookmarked: lower outline affordance; bookmarked: one top-right filled glyph, no lower duplicate
- Inbox review marker: every object card is a drop target (`after_object_id` = that object); hover preview below the card; gap targets remain

## Technical debt (record only, not fixed here)

Yandex Calendar attendee payload ordering/normalization can rewrite source Object metadata and `updated_at` with stable semantic event identity. Future: **Yandex attendee canonicalization / passive-sync metadata churn** (canonical dedupe/sort before metadata equality).

Design Pass C should unify shared Object presentation primitives where semantics are global (kind/source identity, bookmark, labels, title/header, timestamp, actions). Today current/soon event emphasis stays screen-specific.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.

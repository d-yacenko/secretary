# Design decisions

Entries added when a choice will matter in later phases.

## PHASE 14.5 — User ownership and connector sync policy

- Every personal resource has explicit `user_id`; bootstrap owner for single-user operation until auth.
- `resolve_current_user()` is the single bootstrap identity resolver; domain services receive `user_id`.
- User filter before retrieval/ranking (search, vector, context, graph, representations).
- Source object uniqueness is `(user_id, provider, kind, external_id)`.
- `external_id` identifies a source object; it is **not** alone proof the remote object is unchanged (except where a connector explicitly treats known IDs as stable).
- Google credential APIs require both `account_id` and `user_id`.
- `RepresentationService` is user-scoped via parent `Object.user_id`.
- OAuth state carries `user_id`; Google email is not Secretary user identity.
- `secrets/google-oauth-client.json` is deployment secret, not user data.

## Connector ingestion policy (global)

**Initial connection:** bounded recent backfill (normally 30–60 days, never >90 without explicit user request) plus item/page limits.

**After initial connection:** incremental/new/changed objects only when technically possible.

- UNKNOWN object → fetch and process.
- KNOWN unchanged → no expensive fetch/embed/analyze.
- KNOWN changed → update and reprocess only what changed.

Being inside the synchronization time window does **not** mean the full object must be downloaded again.

**Gmail (normal bounded sync):** `messages.list` → batch known external IDs for current user → `messages.get(full)` only for unknown IDs. Known imported message bodies are treated as stable until Gmail History / provider reconciliation exists. Label/deletion changes are deferred.

**Yandex Mail (PHASE 16):** encrypted per-user Mail app passwords (MVP); OAuth deferred to PHASE 19.5 Connections. IMAP incremental via UIDVALIDITY + last UID; initial backfill newest batch; incremental oldest batch first; skip FETCH for known external IDs.

**Yandex Calendar (PHASE 17):** encrypted per-user **Calendar** app passwords (separate from Mail). Read-only CalDAV via principal discovery; bounded time-range query with expand; per-calendar sync-token incremental (`Depth: 0`, `DAV:nresults`); deletion tombstones; occurrence identity UID+RECURRENCE-ID.

**Cloud/web resources (PHASE 18):** `POST /resources/register` stores user-owned metadata for selected Google Drive / Yandex Disk files, web URLs, uploads, and inline text. Full fetch/extract only when `ingest_content=true`. Skip re-embed/re-extract when `content_revision` (etag/revision/modified/hash) unchanged. No whole-drive or arbitrary web crawling.

**Local files (PHASE 19):** user-scoped `local_devices` + `local_roots`; mirror under `local_files_root`. Only explicitly registered roots/files; bounded scan/report. Path-based `external_id` (not hash-as-identity). Policies `metadata_only` / `index_text` / `upload_copy`. Worker `ingest_local_file` checks ownership before filesystem read. Dataset tools bounded (schema, sample, stats, column query).

**Manual capture (PHASE 19.5):** explicit user capture is a primary ingest path (typed text now; voice later via same path). `POST /capture/task` creates confirmed user-owned tasks with optional pinned context (`references` + `context_role=user_pinned`) and explicit `depends_on` edges. Provider-derived objects remain an additional path, not the only path.

**Auth (PHASE 19.5):** opaque bearer tokens (hashed at rest); no bootstrap-user fallback on personal APIs. Google OAuth start requires Secretary authentication; callback identity from single-use state only.

**Flutter roadmap (PHASE 20+):** client must include a prominent Manual Capture flow (typed input, later voice, context attachment, dependencies). Secretary is not merely a viewer for Gmail/Calendar-derived objects.

**Future:** when a provider offers reliable cursor/history/sync tokens, prefer that over rescans; unchanged processed content must not be repeatedly downloaded/embedded/analyzed.

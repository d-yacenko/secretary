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

**Flutter voice contract (PHASE 20):** voice is another input method, not another task model. Direct capture: voice → transcript → same `CaptureDraft` → `POST /capture/task`. Conversational commands: voice → transcript → Secretary assistant/command flow. No separate voice task entity/API. Implementation deferred to PHASE 23 or later approved phase.

**Future:** when a provider offers reliable cursor/history/sync tokens, prefer that over rescans; unchanged processed content must not be repeatedly downloaded/embedded/analyzed.

## PHASE 22.5A — Local retrieval foundation

1. Top-K is a maximum, not a target.
2. Retrieval is local-first and PostgreSQL-first.
3. Default time-sensitive source horizon is 90 days, progressively widened to 365 days and then local all-history when relevance is insufficient or history is explicitly requested.
4. Personal/active graph objects are not removed merely because they are old.
5. Retrieval v1 uses PostgreSQL FTS/trigram; embeddings are not required for ordinary retrieval.
6. Provider-assisted archive search and ML reranking are future fallbacks, not v1 dependencies.

## PHASE 22.5C — Context neighbor selection note

`ContextService` loads graph neighbors via `GraphService.get_neighbors(limit=MAX_NEIGHBORS)` and then applies local `EDGE_TYPE_PRIORITY` sorting on that SQL-limited set. Future high-degree graph work may need priority-aware neighbor selection in SQL rather than post-limit sorting.

## PHASE 22.6 — Task taxonomy

`kind=task` is reserved for Secretary-native actionable work ("дело").

Source/evidence objects (email, event, file, web_page, chat_message, note, etc.) support tasks through `references` edges but are not interchangeable with tasks.

Future provider-native todo systems (Google Tasks, Microsoft To Do, etc.) must **not** automatically reuse `kind=task` as authoritative provider objects. A future normalized kind such as `todo_item` with `origin=source` and `state=observed` may link or mirror to a Secretary task through an explicit future policy. That connector is not implemented in PHASE 22.6.

## PHASE 22.7 — Assistant cost profile

Routine interactive Secretary work uses a cost-sensitive Assistant model (`OPENAI_ASSISTANT_MODEL`, default `gpt-5.6-luna`) with `reasoning.effort=low` and `text.verbosity=low` by default.

`OPENAI_MODEL` (`gpt-5.6-terra`) remains available for future higher-value analysis paths; the Assistant does not use it automatically.

Higher-cost reasoning is opt-in via configuration, not an automatic Luna→Terra fallback.

OpenAI cost is measured per Assistant turn and per Responses API round (`assistant_turn` telemetry), not per materialized task.

Explicit OpenAI prompt-cache breakpoints are deferred; measure `cached_tokens` / `cache_write_tokens` on real turns first.

Stateless `reasoning.encrypted_content` replay is deferred until telemetry shows reasoning tokens or repeated rounds dominating cost after Luna/low.

## PHASE 23A — Voice transcription foundation

Voice audio is ephemeral input only: `/assistant/transcribe` does not persist uploads or create Secretary objects.

Transcription uses a dedicated configurable model (`OPENAI_TRANSCRIPTION_MODEL`, default `gpt-4o-mini-transcribe`), not `OPENAI_ASSISTANT_MODEL` or `OPENAI_MODEL`.

Transcripts are routed through existing flows (`/assistant/message`, capture) in later phases rather than introducing a voice domain model (`kind=voice`, audio graph objects, transcription history tables).

## PHASE 23C — Agent execution gateway and tool policy foundation

Secretary is a constrained domain agent, not a one-shot LLM intent decoder.

The LLM controls research strategy, reasoning strategy, tool selection, when enough information has been gathered, and how to explain the result.

Deterministic backend code controls which tools exist, argument validation, authenticated-user isolation, permission class, whether execution is allowed, transaction boundaries, tool budgets, evidence allowlists, future approval enforcement, and audit boundaries.

Canonical permission levels: `READ`, `INTERNAL_WRITE`, `EXTERNAL_PROPOSE`, `EXTERNAL_WRITE`, `COMMUNICATE`.

PHASE 23C preserves current `INTERNAL_WRITE` behavior (baseline policy allows execution).

PHASE 23D will introduce persisted frozen action plans and interactive approval.

MCP and built-in Assistant must ultimately converge on the same governed execution layer (MCP routing through the gateway is planned for PHASE 23E).

## PHASE 23D-A — Frozen pending action plans and exact approval execution

Interactive Assistant mutations require explicit user approval.

Approval binds a persisted frozen action plan with validated exact arguments.

The approval endpoint executes stored exact arguments; the LLM does not regenerate them.

Background/system `INTERNAL_WRITE` policy remains separately controllable via `ExecutionContext.BASELINE`.

MCP convergence is deferred to PHASE 23E.

PHASE 23D-B will add approval UX and conversational post-approval resume.

## PHASE 23D-B — Approval UX and safe agent resume

Approved action-plan execution uses `DomainWriteMode.APPROVED_CONFIRMED` so agent-created tasks and edges are `confirmed`; baseline agent writes remain `proposed`.

`POST /assistant/action-plans/{plan_id}/resume` performs a tool-free finalization turn with the same Secretary provider configuration after mutations are committed.

Resume derives `affected_objects` deterministically from persisted execution results; OpenAI failure returns HTTP 502 without rolling back executed plans.

Flutter blocks normal send/voice while a pending plan is unresolved and drives approve → resume UX from the proposal message card.

PHASE 23D-B closure: recoverable approve/reject errors, structured-vs-generic 409 decoding, resume validates plan before provider construction, bounded untrusted finalization context, and truthful completed-affected-object labels.

## PHASE 26A — Bounded personal data correlation (in review)

- Correlation pipeline: deterministic source relations → bounded candidates → `CorrelationJudge` → `agent/proposed` edges (min confidence 0.80, max 5 per run).
- Worker pipeline: `summarize_resource` → `embed_object` → `correlate_object`; OpenAI summary uses `OPENAI_ASSISTANT_MODEL` in worker only.
- Semantic summaries in `Representation(kind=summary)` + `metadata.semantic_summary`.
- Local roots map to `folder` objects with `system/confirmed contains` edges.
- Proposed correlation review via `POST /relations/{edge_id}/decision`; not a Pending Action Plan.

## PHASE 26B — Client-assisted local file intake (deferred)

Canonical future local-device path:

`Desktop / Android → choose/drop file → mechanical local extraction (filename/path, size/mtime, revision/hash, bounded text/chunks, dataset schema/sample/statistics) → typed bounded payload → backend validation → canonical Object/Representation → semantic summary → embedding → correlation`

Architecture rule: mechanical extraction may happen on the client; semantic understanding remains server-side. The client must not make semantic correlation decisions. The backend must still validate all client-extracted representation bounds and ownership.

PHASE 26B should use this path for: desktop drag-and-drop, desktop file/folder intake, Android system file picker.

Server-side parsing remains valid for: cloud/server-accessible sources, compatibility/fallback paths.

Do not implement client extraction in PHASE 26A closure.


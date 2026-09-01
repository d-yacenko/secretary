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

## PHASE 26A — Bounded personal data correlation (accepted / closed)

- Correlation pipeline: deterministic source relations → bounded candidates → `CorrelationJudge` → `agent/proposed` edges (min confidence 0.80, max 5 per run).
- Worker pipeline: `summarize_resource` → `embed_object` → `correlate_object`; OpenAI summary uses `OPENAI_ASSISTANT_MODEL` in worker only.
- Semantic summaries in `Representation(kind=summary)` + `metadata.semantic_summary`.
- Local roots map to `folder` objects with `system/confirmed contains` edges.
- Proposed correlation review via `POST /relations/{edge_id}/decision`; not a Pending Action Plan.

## PHASE 26B — Client-assisted intake & source navigation (accepted / closed)

- Mechanical extraction on Desktop/Android for `.txt`, `.md`, `.csv`; unsupported formats metadata-only.
- Typed `POST /local/files/client-intake` with server-side representation allowlist and revision validation.
- `GET /objects/{id}/open-target` returns trusted navigation actions only (no arbitrary metadata URL guessing).
- Gmail/Yandex attachments as `file` objects with `source/observed` `contains` edges from parent email.
- Server-side `ingest_local_file` and upload paths preserved for server-accessible sources.
- Flutter deps: `file_picker`, `url_launcher`, `desktop_drop` (Linux drop only).
- Android: system file picker without broad storage permission; persistent reopen best-effort.
- Yandex Mail open-target: mailbox URL when exact message browser link unavailable from IMAP.

## PHASE 26C — Structured query, search ordering & topology graph (accepted / closed)

- `query_objects` is the general structured READ primitive; `retrieve` remains semantic discovery only.
- `ObjectQueryService`: bounded filters, inclusive date ranges, `NULLS LAST` nullable date sorts, max limit 50, default visibility excludes rejected/deleted tasks; `proposed` objects remain visible; legacy task `status NULL→open`, `completed→done` on read/filter; model-visible normalization `NULL→open`, `completed→done`.
- Assistant `query_objects` tool output: ordered-prefix truncation to `MAX_ASSISTANT_TOOL_OUTPUT_CHARS` (not empty `truncated-only` payload); grounding IDs match exposed rows only.
- Search newest/oldest: bounded qualified candidate pool (≤100), primary date helper aligned with Flutter semantics (UTC-aware; naive `metadata.modified_at` falls back), sort before display limit.
- `GET /search/facets`: capped per dimension (`MAX_SEARCH_FACETS_PER_DIMENSION=64`), count DESC / value ASC, no empty provider values.
- Flutter: shared `object_presentation.dart`; compact icon filters on Search and Graph; desktop uses anchored menus (`MenuAnchor`), mobile may use bottom sheet; topology-aware layout uses visible edges (undirected for placement), cumulative BFS radii, branch sectors, isolated grid packing, incremental expansion preserves existing positions.
- Client timezone contract: Flutter sends `client_timezone_id` and `client_utc_offset_minutes` on Assistant and Today requests; backend `resolve_client_timezone()` for day-boundary semantics.
- Search provider filter: retrieval filter suffix uses newline join (not empty-string join) to avoid malformed `:kindAND` suffix and HTTP 500.
- Graph workspace: client-side `visibleNodes` / `visibleEdges` display filters; fit/empty state when selection hidden.
- Assistant per-turn tool budget: `MAX_ASSISTANT_TOOL_CALLS_PER_TURN = 12` (generic `ToolExecutor.DEFAULT_MAX_TOOL_CALLS` unchanged at 5).
- Task evidence: `update_task` reports `evidence_added_object_ids` and `evidence_already_linked_object_ids`; `link_objects` rejects self-link and idempotent duplicates (`created: bool`).
- Email HTML-to-text: shared `email_html_text.py` for Gmail/Yandex normalize; legacy flattened DB rows not retroactively restored.
- No specialized deadline/urgency tools; Secretary combines atomic tools.
- Manual matched-version Linux E2E PASS: deadline/today semantics, urgent task, task context enrichment, Gmail/Yandex provider filters, Graph type/provider filtering, HTML email readable structure.
- Accepted application SHA: `5c4ffc40fd7462c1ecc29b2a00bc9f5920a50ba6`.
- Deferred: Mattermost, Google Drive, Yandex Disk connectors; manual drag; persisted layout; curved edges.

## PHASE 27 — Source Completion (in progress)

Major phase reordered before Safe External Actions.

- **27A** Live Source Sync, Inbox/Today & Assistant Presentation — accepted (`f92ca0c`)
- **27B** Mattermost (`provider=mattermost`, `kind=chat_message`) — accepted (`1dc493d`; user E2E accepted)
- **27C** Google Drive, Yandex Disk, registered-folder local refresh — in progress; 27C-A accepted (`2a4145f`); 27C-B operational sync + OpenTarget awaiting review

## PHASE 27C-B — Google Drive recurring sync + trusted OpenTarget (awaiting architect review)

- Recurring job `sync_google_drive` in `RECURRING_SOURCE_JOB_TYPES`; payload `{"account_id": "<uuid>"}` only; default interval 300s (`SOURCE_SYNC_GOOGLE_DRIVE_INTERVAL_SECONDS`, min 60s).
- Worker handler: `handle_sync_google_drive` → `build_drive_sync_service` → `sync_account(account_id, user_id)`; no tokens/cursors in Job.payload.
- `SourceSyncScheduler`: Drive row only when `drive.readonly` in account scopes; Gmail/Calendar rows unchanged for legacy accounts; maintenance, trigger, stale retirement, failed rearm.
- `POST /sources/sync` triggers Drive recurring row; `GET /sources/status` shows `google_drive` with Google account email label.
- `OpenTargetService`: explicit branch for `provider=google_drive`, `kind=file|folder`; provenance `account_id` + `file_id` + `external_id` match; URL only `https://drive.google.com/open?id=<file_id>`; ignores `canonical_uri` and `web_view_link`.
- `POST /connectors/google/drive/sync` retained as direct connector/debug path.
- Deferred: content download/export, Flutter, Yandex Disk, merge, production deploy.

## PHASE 27C-A — Google Drive read-only foundation (accepted at `2a4145f`)

- OAuth scope `drive.readonly`; `GoogleAccount.drive_sync_state` (migration `0020`); bounded bootstrap + incremental Changes sync; hard budget + durable cursors (`2a4145f`).
- Objects `provider=google_drive`; manual `POST /connectors/google/drive/sync`; operational integration in 27C-B.

## PHASE 27B-C — Mattermost Flutter UX (accepted at `1dc493d`)

- Flutter connect UX; compose passes `MATTERMOST_ALLOWED_BASE_URLS` to api/worker containers.
- User Mattermost E2E accepted: new message in Inbox.
- Deferred: Mattermost disconnect; PHASE 27C.

## PHASE 27B-A — Mattermost secure connector & sync core (accepted at `87b16cb`)

- Read-only Mattermost PAT connector with SSRF allowlist (`MATTERMOST_ALLOWED_BASE_URLS`), HTTPS-only normalized URLs, `follow_redirects=false`, no userinfo/query/fragment.
- `MattermostAccount` encrypted PAT at rest; `POST /connectors/mattermost/connect` verifies `/api/v4/users/me`, no token in API response, no initial sync in connect.
- Channel discovery: `GET /api/v4/users/me/channels` with teams+per-team channels fallback on 404; sorted by `last_post_at`, bounded `max_channels`.
- Per-channel `sync_state` cursors (`last_processed_post_id`, `last_processed_create_at_ms`); incremental new posts via `after=<post_id>`; separate bounded edit sweep via `since=` with overlap; no false watermark advance on provider `since` saturation (max 1000).
- Bootstrap bounds: 14 days, 50 channels, 100 initial posts/channel, 500 posts/run, 300s overlap (server-side config).
- Normalized `chat_message` objects with server-namespaced `external_id`; `embed_object` on create/semantic update only.
- Mattermost object metadata contract: `server_url`, `account_id`, `post_id`, channel/team/author provenance fields, `create_at`/`update_at` ms timestamps; `author_user_id` canonical author id; no PAT in metadata.
- Semantic embedding rule: `embed_object` only when `title` or `body` changes; metadata-only provider updates refresh Object metadata without a new embedding job.
- `MattermostHttpTransport` closes owned `httpx.Client` on `close()`; connect and sync close production transport; injected factory/external transports are caller-owned.
- Deferred in 27B-A: scheduler job, `/sources/status`, Flutter, deploy (delivered in 27B-B for scheduler/status/connections/OpenTarget; Flutter still deferred).

## PHASE 27B-B — Mattermost operational backend integration (accepted at `96a5249`)

- Recurring job `sync_mattermost` in existing `RECURRING_SOURCE_JOB_TYPES`; payload `{"account_id": "<uuid>"}` only; default interval 120s (`SOURCE_SYNC_MATTERMOST_INTERVAL_SECONDS`, min 60s).
- Worker handler: `account_id` from payload + claimed `user_id` → `build_mattermost_sync_service` → `sync_account`; PAT only via user-owned `MattermostAccount`.
- `SourceSyncScheduler`: one recurring row per Mattermost account; stale retirement when account removed; failed-job rearm; `trigger_all_for_user` scoped to user; no network in scheduler maintenance.
- `POST /sources/sync` re-arms existing Mattermost recurring rows without inline network sync.
- `GET /sources/status`: provider `mattermost`; label from display_name/username @ server; sanitized job errors; no PAT.
- `GET /connections`: list of Mattermost accounts (`account_id`, `server_url`, `remote_user_id`, `username`, `display_name`, `email`); no PAT/encrypted token.
- `OpenTargetService`: explicit branch for `provider=mattermost`, `kind=chat_message`; trust via user-owned account + allowlist + bounded metadata (`account_id`, `post_id`, `team_name`); deep link `server/team/pl/post_id` or server-base fallback with `mattermost_exact_post_link_unavailable`; rejects tampered/cross-user metadata; never opens `canonical_uri` or arbitrary URLs.
- `sanitize_job_error` strengthened: Authorization, Bearer, access_token, refresh_token, PAT/token material never in `Job.last_error`.
- `chat_message` continues through generic Object pipelines (embed, correlate, retrieval); no Mattermost-specific LLM tools.
- Deferred in 27B-B: Flutter UX (27B-C), disconnect flow, production deploy.

## PHASE 27B-C — Mattermost Flutter UX + matched-version E2E prep (accepted at `1dc493d`)

- Flutter: `MattermostConnection` model; `Connections.mattermost[]`; `connectMattermost(serverUrl, accessToken)`; PAT not stored/logged in client state after connect.
- Account → Подключения: list connected Mattermost accounts; connect dialog (Server URL + obscured PAT).
- Provider presentation: glyph `M`, label `Mattermost`; `chat_message` uses existing Inbox/Search/Graph/Object detail pipelines.
- Backend connect: `ensure_recurring_source_job(sync_mattermost)` + trigger row runnable now; no inline message sync on HTTP connect.
- User Mattermost E2E accepted at application SHA `1dc493d`.
- Deferred: Mattermost disconnect.

## PHASE 27A — Live source sync & daily workspace (accepted)

- Recurring DB jobs: `sync_google_gmail`, `sync_google_calendar`, `sync_yandex_mail`, `sync_yandex_calendar`; payload `account_id` only; same-row reschedule on success.
- `SourceSyncScheduler`: enumerate connected accounts, scope-aware scheduling, repair missing jobs, re-arm failed after cooldown; worker maintenance ≈60s.
- Default intervals: mail 120s, calendar 300s; manual `POST /sources/sync` re-arms without duplicate rows.
- `GET /sources/status` bounded status without credentials; `GET /inbox` aggregates notifications + recent source objects + sync status.
- Today includes active proposed tasks (`state != rejected`, non-terminal); «Предложено» in Flutter.
- Assistant Markdown rendering (`flutter_markdown`); user messages remain plain text.
- Provider compact badges: `yandex_calendar` → `Я`, `google_calendar` → `G`.
- Inbox/Today passive snapshot refresh: GET `/inbox` / `/today` every 30s while screen open; manual Refresh still triggers `POST /sources/sync`.
- `ObjectCompactHeaderRow`: kind icon + provider glyph before title; date/time trailing right.
- Gmail intake hygiene: provider-side `includeSpamTrash=false` and query exclusions for spam/trash/promotions/social/forums; existing noisy Gmail objects excluded from recent Inbox feed (no DB delete).
- Local files unchanged; VDS does not poll user filesystem (27C).

## Gmail noise filtering (PHASE 27A closure)

- Secretary trusts Gmail provider classification; no custom spam/LLM classifier.
- `messages.list` uses `includeSpamTrash=false` and query excludes spam/trash plus `category:promotions`, `category:social`, `category:forums`; `category:updates` remains allowed.
- Filter applies at list time before `messages.get` / attachment / embedding work.
- Already-imported Gmail objects with noise labels are hidden from recent Inbox feed only; objects are not deleted from the graph.

PHASE 26A + 26B + 26C accepted as one major phase. Full PHASE 26 closed at `5c4ffc40`.


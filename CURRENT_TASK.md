# Current task — PHASE 26 closed; PHASE 27 not started

## Status

PHASE 26 — Personal Data Correlation: **accepted / closed** (accepted application SHA `5c4ffc40fd7462c1ecc29b2a00bc9f5920a50ba6`).

PHASE 26C — Structured Query, Search UX & Topology-Aware Graph: **accepted / closed** (`5c4ffc40`).

PHASE 26C closure corrective: timezone contract, Search provider filter fix, Graph client-side visible filtering, Assistant tool budget/evidence, shared email HTML-to-text.

Manual matched-version Linux E2E: **PASS** (deadline/today semantics, urgent task, task context enrichment, Gmail/Yandex provider filters, Graph type/provider filtering, HTML email readable structure).

Architect code review: **PASS**.

Architect context refresh checkpoint: **completed** at `114608d`.

Do **not** start PHASE 27A until explicitly tasked.

## PHASE 26C delivered

- `query_objects` structured READ primitive (Assistant + MCP)
- `ObjectQueryService` deterministic SQL filtering/ordering; legacy `NULL→open`, `completed→done`
- Assistant `query_objects` output: ordered-prefix truncation under `MAX_ASSISTANT_TOOL_OUTPUT_CHARS`
- Search `sort=relevance|newest|oldest`, bounded candidate pool, capped `GET /search/facets`
- Primary search date: UTC-aware normalization; naive `metadata.modified_at` falls back
- Shared `object_presentation.dart` registry; compact Search/Graph icon filters
- Desktop: anchored `MenuAnchor` popups (no bottom sheet / full-screen dim)
- Topology-aware Graph layout: cumulative BFS radii, branch sectors, isolated grid packing, incremental stability
- Client timezone transport for Assistant and Today (`client_timezone_id`, `client_utc_offset_minutes`)

## Closure corrective highlights

- Regression: NULL-status proposed task with today's `due_at` visible via `query_objects`
- Regression: truncated `query_objects` preserves earliest-due prefix and grounding IDs
- Graph production-widget tests: desktop anchored Type/Provider filters at 1280×800
- Search `provider` filter: no HTTP 500 from malformed filter suffix
- Email HTML-to-text shared helper for Gmail/Yandex normalize (legacy flattened rows not restored)

## Deferred (not PHASE 26)

- Mattermost / Google Drive / Yandex Disk connectors
- Manual Graph node drag, persisted positions, curved edges
- Labels/tags, workflow intelligence, external writes, proactive Secretary

## Next major phase

PHASE 27 — Safe External Actions (not started).

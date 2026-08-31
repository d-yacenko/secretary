# Current task — PHASE 26C awaiting architect review

## Status

PHASE 26C — Structured Query, Search UX & Topology-Aware Graph: **implementation complete, awaiting architect review**

Closure corrective applied on branch `review/phase-26c-query-search-graph` (baseline `ff4626c`).

Architect context refresh checkpoint: **completed** at `114608d`

PHASE 26 remains **open** (not closed until PHASE 26C acceptance).

Do **not** merge, deploy, or start PHASE 27.

## PHASE 26C delivered

- `query_objects` structured READ primitive (Assistant + MCP)
- `ObjectQueryService` deterministic SQL filtering/ordering; legacy `NULL→open`, `completed→done`
- Assistant `query_objects` output: ordered-prefix truncation under `MAX_ASSISTANT_TOOL_OUTPUT_CHARS`
- Search `sort=relevance|newest|oldest`, bounded candidate pool, capped `GET /search/facets`
- Primary search date: UTC-aware normalization; naive `metadata.modified_at` falls back
- Shared `object_presentation.dart` registry; compact Search/Graph icon filters
- Desktop: anchored `MenuAnchor` popups (no bottom sheet / full-screen dim)
- Topology-aware Graph layout: cumulative BFS radii, branch sectors, isolated grid packing, incremental stability

## Closure corrective highlights

- Regression: NULL-status proposed task with today's `due_at` visible via `query_objects`
- Regression: truncated `query_objects` preserves earliest-due prefix and grounding IDs
- Graph production-widget tests: desktop anchored Type/Provider filters at 1280×800

## Deferred (not PHASE 26C)

- Mattermost / Google Drive / Yandex Disk connectors
- Manual Graph node drag, persisted positions, curved edges
- Labels/tags, workflow intelligence, external writes, proactive Secretary

## Next major phase (after PHASE 26 closes)

PHASE 27 — Safe External Actions

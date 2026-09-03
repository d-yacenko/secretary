# PHASE 29A Real E2E Retrieval Diagnostic

**Generated:** 2026-09-03T17:34:04Z  
**Production SHA:** `fc8e90b7c9e706691aec7afc30caa4b95825cc51`  
**Incident:** User added Google Drive spreadsheet «Второе полугодие», asked Assistant twice about «Контрольное мероприятие №1: Классификация на ручных признаках» — no match.

## Archive layout

| Path | Description |
|------|-------------|
| `manifest.json` | Index of all files |
| `traces/` | AI audit trace waterfalls |
| `object/` | Target Object + Representations + phrase checks |
| `checks/` | Direct read-only retrieve/query_objects/get_context |
| `analysis/` | Tool sequence, XLSX policy, conclusion |

## Key traces (failed user queries)

1. `5d13e0f1-3555-4352-b629-186ff73dca1f` — 2026-09-03 17:11:10 UTC (first query)
2. `9aaba601-235f-4db3-8dc1-3e8a7f785f66` — 2026-09-03 17:12:18 UTC (second query)

Supplementary: `31764060-7c4c-4634-8342-8347e84f4971` — 17:25:55 UTC (later attempt, same failure pattern).

## Payload capture

`ai_audit_capture_sessions` empty — historical payloads NOT retained. Metadata-only traces.

## Target object

`19940b16-893b-49be-969c-5b430063e6ac` — Второе полугодие.xlsx (google_drive, ready).

## Bottom line

**Root cause:** XLSX mechanical extraction persists only `rows[1:6]` into sample Representation; target phrase at ~row 15 never entered searchable text. Assistant called `retrieve` correctly but target Object never appeared in results; misleading partial-token hits from other sources.

See `analysis/conclusion.md` for full Q&A.

**No code changes. No corrective implemented.**

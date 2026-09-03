# PHASE 29A E2E Retrieval Failure — Production Diagnostic

**Date:** 2026-09-03  
**Production SHA:** fc8e90b7c9e706691aec7afc30caa4b95825cc51  
**User query:** «Контрольное мероприятие №1: Классификация на ручных признаках»

## Target object

| Field | Value |
|-------|-------|
| object_id | `19940b16-893b-49be-969c-5b430063e6ac` |
| title | Второе полугодие.xlsx |
| provider | google_drive |
| kind | file |
| content_extraction_status | ready |
| content_revision | gdrive:md5:182842f56683449a8e1e3a04c4bea88b |
| content_extraction_version | phase29a-v1 |
| mechanical_representation_count | 3 |
| created_at | 2026-09-03 17:10:01 UTC (before failed queries at 17:11 / 17:12) |

## Two failed Assistant traces

| # | trace_id | started_at (UTC) | retrieve calls | query_objects | get_context |
|---|----------|------------------|----------------|---------------|-------------|
| 1 | `5d13e0f1-3555-4352-b629-186ff73dca1f` | 17:11:10 | 3 | NO | YES (wrong object) |
| 2 | `9aaba601-235f-4db3-8dc1-3e8a7f785f66` | 17:12:18 | 2 | NO | NO |

**Payload capture:** `ai_audit_capture_sessions` table empty — payloads NOT retained for these traces. Only metadata available.

## Trace 5d13e0f1 (first user query)

1. **retrieve** — kind=file, time_scope=recent, query ~68 chars → **0 file hits** (raw 160 chars)
2. **retrieve** — kind=null, time_scope=all, query ~33 chars → **5 hits**, top=`Архитектура платформы данных` (NOT xlsx)
3. **get_context** — object_id=`857f1fda-6c93-4e07-a6f6-bf037a3b30be` (`Архитектура платформы данных`) — misleading partial match
4. **retrieve** — kind=null, query ~55 chars → **5 hits**, still no xlsx
5. Model response: 535 chars — concluded no matching file

## Trace 9aaba601 (second user query)

1. **retrieve** — kind=all, query ~60 chars → **5 hits**, no xlsx (raw 159, visible 60 truncated)
2. **retrieve** — kind=all, query ~53 chars → **5 hits**, no xlsx
3. Model response: 281 chars — no matching file

## Retrieval replay (current production DB)

| Query | kind | scope | hits | xlsx found? |
|-------|------|-------|------|-------------|
| Full phrase | null | all | 10 | NO |
| Full phrase | file | all/recent | 0 | NO |
| «Классификация на ручных признаках» | null | all | 10 | NO |
| «Второе полугодие» | file | all | 1 | YES |

**retrieve never returned object 19940b16 for the target phrase.**

## Representation / phrase presence

- phrase «Классификация на ручных признаках»: **NOT_FOUND** in any representation of xlsx object
- phrase «Контрольное мероприятие»: **NOT_FOUND**
- global DB search for phrase: **0 rows**
- sample text contains only rows 1.0–2.0 (first 5 data rows via `rows[1:6]`)
- statistics: **46 rows** in sheet — full sheet read, but row 15+ not in searchable text

## Root cause hypothesis

**CONFIRMED:** `_build_xlsx_representations()` persists only `rows[1:6]` into sample Representation.
Target phrase at ~row 15 was mechanically readable (46 rows counted) but **never persisted** into searchable Representation.text.

## Model behavior

Evidence was **absent from tool output** — not model stopping despite evidence.
retrieve returned misleading unrelated objects (partial token overlap on «Классификация», «мероприятие»).
get_context on wrong object showed «Классификация применяемого ПО» — different context, not target phrase.

# Current task — PHASE 29A bounded content extraction, awaiting architect review

## Status

PHASE 28D: **ARCHITECT ACCEPTED / CLOSED** at `c791461287a3b60e34c9474c9df146ea3fd8ea52`.

PHASE 29A — Bounded Content Extraction for Explicit Resources: **implemented**, **awaiting architect review**.

## Branch

`review/phase-29a-bounded-content-extraction`

## PHASE 29A scope (implemented)

- Explicit cloud link intake enqueues `extract_explicit_resource_content` for supported files
- Bounded mechanical extraction (no LLM in extractors) → `summarize_resource` → embed → correlate
- Google Drive: Docs/Sheets/Slides export + binary formats within bounds
- Yandex Disk: public file download via provider API only
- `content_status` / `content_jobs_enqueued` on intake link response
- Local txt/md/csv client intake preserved (no VDS raw upload for PDF/DOCX/etc.)

## Deploy

Pending matched-version VDS deploy and manual Google/Yandex E2E (see PROJECT_STATE).

## Next

STOP — await architect review. Do not start Safe External Actions or scheduled_activity.

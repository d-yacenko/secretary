# Current task — PHASE 18 review corrective

## Status

**corrective implemented, awaiting review**

## Fixes delivered

1. **Web fetch SSRF** — manual redirect hops; validate each target; resolve DNS; reject private/loopback; redirect cap; httpx errors → `WebFetchError`
2. **No network in DB transaction** — web fetch before mutation / commit before network; no sync `refresh_object_embedding`; `RepresentationService` without embedding service; `embed_object` job only
3. **Revision / ingest semantics** — `content_ingested_revision` marker; four ingest/revision cases covered in tests
4. **Bounded upload** — chunked staging; size limit 413; preserved filename; content-hash revision/identity; malformed payload → 422
5. **Embedding regression** — one job per changed resource; zero activity for unchanged ingested revision
6. **Docs** — PHASE 17 marked accepted/closed in `PROJECT_STATE.md`

## PHASE 18 invariants

- User-owned from registration (`origin=user`, `user_id`)
- Selected/scoped only — client supplies explicit provider IDs/URLs
- Metadata-first; content on `ingest_content`
- Same ingested revision → no reprocessing
- Bounded representations via existing chunk/summary limits
- Search/context user-scoped

## Defer

- PHASE 19 local filesystem crawling
- PHASE 19.5 auth/connections UI
- Live Google Drive / Yandex Disk API fetch (metadata supplied at register)

## STOP

PHASE 19 not started. Awaiting PHASE 18 review acceptance.

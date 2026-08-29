# Current task — PHASE 18

## Status

**implemented, awaiting review**

## Delivered

- `POST /resources/register` — JSON or multipart (`payload` + optional `file`)
- `GET /resources/{object_id}` — user-scoped read
- `ResourceRegistrationService` — metadata-first registration with revision skip
- Providers: `google_drive`, `yandex_disk`, `upload`, `web` (web_page)
- Explicit `ingest_content` for text/file/web extraction via `RepresentationService`
- Bounded web fetch with SSRF guards (`app/resources/web_fetch.py`)
- Revision keys: `etag`, `revision`, `content_hash`, `modified_at`, `provider_revision`
- Known unchanged cloud resources skip download/extract/embed jobs
- Tests: `test_resources.py`, `test_web_fetch.py` (263 total suite passing)

## PHASE 18 invariants

- User-owned from registration (`origin=user`, `user_id`)
- Selected/scoped only — client supplies explicit provider IDs/URLs, no drive crawl
- Metadata-first; content on `ingest_content`
- Unchanged revision → no reprocessing
- Bounded representations via existing chunk/summary limits
- Search/context already user-scoped
- `canonical_uri` / `provider` / `external_id` preserved

## Defer

- PHASE 19 local filesystem crawling
- PHASE 19.5 auth/connections UI
- Live Google Drive / Yandex Disk API fetch (metadata supplied at register)

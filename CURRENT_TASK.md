# Current task — PHASE 18 final corrective

## Status

**corrective implemented, awaiting final acceptance**

## Fixes delivered

1. **Resource identity** — removed `content_revision` object lookup; identity is `provider+external_id` or `canonical_uri` only
2. **Representation embeddings** — `embed_object` worker embeds unembedded chunk representations post-commit; registration stays DB-only
3. **Upload storage** — unique staging names; content-addressed persistent paths; metadata-only uploads persisted for deferred ingest; Docker `resource_data` volume
4. **Bounded JSON** — `MAX_REGISTER_PAYLOAD_BYTES` / `MAX_MULTIPART_PAYLOAD_BYTES` with streaming read
5. **Tests** — identity collision regressions, worker chunk embedding + ContextService ranking, upload isolation/persistence, payload limits

## PHASE 18 invariants

- User-owned from registration
- Metadata-first; explicit `ingest_content` with `content_ingested_revision`
- Worker-only embedding network path (object + chunk representations)
- Revision tracks content changes, not resource identity

## Defer

- PHASE 19 local filesystem crawling
- PHASE 19.5 auth/connections UI

## STOP

PHASE 19 not started. Awaiting PHASE 18 final acceptance.

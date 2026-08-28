# Current task — PHASE 17 final corrective (awaiting review)

## Status

PHASE 17 final corrective applied. Full offline suite: 231 passed, 2 skipped. Not deployed.

## Final corrective scope

- RFC6578 DAV:limit XML (`<d:limit><d:nresults>`) + HTTP body regression test
- Truncated multistatus parser (507, partial sync-token)
- Incremental sync-collection with calendar-data expand in bounded window
- Sync-token safety: persist only after entire CalDAV resource batch applied
- Tombstone ALL occurrences for deleted `event_href` (user-scoped)
- DB transaction leak fix on noop deletions; tx_checker during sync_collection path
- Merge all 200 propstats for calendar-data + etag
- Initial bounded query deterministic cap (>100 resources); incremental strict on overflow

## Defer

- Deploy / live CalDAV smoke until acceptance
- Calendar app password request
- PHASE 18

## Note

STOP for review.

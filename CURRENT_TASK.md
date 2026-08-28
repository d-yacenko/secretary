# Current task — PHASE 17 corrective (awaiting review)

## Status

PHASE 17 corrective applied. Offline tests pass. Not deployed.

## Corrective scope

- Principal-based CalDAV discovery (`/principals/users/{login}/`)
- sync-collection Depth 0 + DAV:nresults batching with partial tokens
- CalDAV deletion tombstones (`status=deleted`)
- TZID / all-day iCalendar parsing
- Expanded recurring occurrence identity (UID + RECURRENCE-ID)
- Transport/sync regression tests

## Defer

- Deploy / live CalDAV smoke until acceptance
- PHASE 18

## Note

STOP for review.

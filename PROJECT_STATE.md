# Project state

## Current phase

PHASE 17 — Yandex Calendar: **live-smoked, awaiting final acceptance**

PHASE 18 — files/cloud links (not started)

## Global invariants (PHASE 14.5+)

See `DECISIONS.md`. PHASE 19.5 (auth + connections) required before PHASE 20 Flutter.

## Working components

- PHASE 00–16: (prior phases)
- PHASE 17: Yandex Calendar CalDAV sync — live smoke passed on VDS `185.233.107.66`
  - Account `ydv@arenadata.io` (`db6353cb-1ac6-4478-9f7f-5fd9f31867de`)
  - First sync (backfill): created 44, unchanged 3, synchronized 47, jobs_enqueued 44
  - Second sync (steady state): all counters 0
  - 44 `yandex_calendar` objects; all bootstrap-owned; 44 embed jobs done
  - 2 calendars discovered: «Мои события» (44 events), «Не забыть» (0)
  - Recurring: 4 distinct occurrences (not collapsed); 2 RRULE masters
  - `/health` ok; credentials absent from API responses and logs
  - Backfill complete; sync_token present on both calendars (values not logged)
  - CalDAV hotfix: no `c:expand` in calendar-query + `</c:filter>` XML close (Yandex compatibility)

## Not done

- PHASE 17 final acceptance
- PHASE 18+

## Next phase

PHASE 18 after PHASE 17 final acceptance.

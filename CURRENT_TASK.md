# Current task — PHASE 28C-R1-R1-R1 final manual E2E awaiting user

## Status

PHASE 28C-R1-R1 manual E2E: **functionally PASS** except stuck sync banner after visible sync completion.

PHASE 28C-R1-R1-R1 — Final Sync Banner Closure Corrective: **implemented and deployed** at `8b02c32a3ad653e24f3cb11309f2875ccaf7dca3`.

Matched-version deployment: **complete** at `8b02c32a3ad653e24f3cb11309f2875ccaf7dca3` (Alembic `0023`).

Current: **final manual E2E awaiting user verification**.

PHASE 29A MUST NOT start until the user reports final manual E2E PASS.

PHASE 28C is NOT fully closed until final user PASS.

## Branch

`review/phase-28c-inbox-recent-ordering-r1-r1-r1` at `8b02c32a3ad653e24f3cb11309f2875ccaf7dca3`.

## Final manual acceptance target

With Inbox open on Flutter client built from `8b02c32a3ad653e24f3cb11309f2875ccaf7dca3` against `https://web-itx.duckdns.org/secretary`:

1. Press **Обновить**.
2. Allow `/sources/status` polling to reach its bounded timeout while at least one source is still syncing.
3. Wait until source synchronization has visibly completed.
4. The message **«Синхронизация источников продолжается»** must disappear automatically (within passive Inbox refresh) without another manual refresh.
5. If sources are genuinely still syncing after timeout, the message may remain until they settle, then must clear on passive refresh.
6. Inbox contents must not blank/flicker unnecessarily.
7. Passive Inbox refresh must not repeatedly POST `/sources/sync`.

## Next after final manual E2E PASS

**PHASE 29A — bounded content extraction**.

## Not started

- Phase 29A (until final manual E2E reported)
- merge to main

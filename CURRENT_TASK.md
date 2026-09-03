# Current task — PHASE 28C-R1-R1 manual E2E awaiting user

## Status

PHASE 28C-R1-R1 — Eliminate Sync Banner Settlement Race: **accepted** at `e0ac78c50e7cb46dff9cf9b786409197977fb728`.

Matched-version deployment: **complete** at `e0ac78c50e7cb46dff9cf9b786409197977fb728` (Alembic `0023`).

Current: **manual E2E awaiting user verification**.

Do **not** start **PHASE 29A** until the user reports manual E2E result.

## Branch

`review/phase-28c-inbox-recent-ordering-r1-r1` at `e0ac78c50e7cb46dff9cf9b786409197977fb728`.

## Manual acceptance target

With Inbox open:

1. Press **Обновить**.
2. Allow `/sources/status` polling to reach its bounded timeout while at least one source is still reported as syncing.
3. If the subsequent Inbox snapshot already shows all sources settled, the message
   **«Синхронизация источников продолжается»** must **NOT** remain visible.
4. If sources really are still syncing, the message may appear and must disappear on a later passive Inbox refresh once statuses settle.
5. Existing Inbox contents must not blank/flicker unnecessarily.
6. No repeated provider sync should be triggered by passive Inbox refresh.

Test the Flutter client built from the same SHA (`e0ac78c`) against `https://web-itx.duckdns.org/secretary`.

## Next after manual E2E PASS

**PHASE 29A — bounded content extraction**.

## Not started

- Phase 29A (until manual E2E reported)
- merge to main

# Current task — Unified Week B-R6 — FINAL desktop calmness + Today badge + task-button microcopy

## Status

Unified Week A / A-R1: **CODE ACCEPTED / DEPLOYED / HUMAN UX NOT ACCEPTED** at `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`.

Unified Week B: code at `14cd6b86f5fddb7c0d5fc669950afe9453e069f5`.

Unified Week B-R1: `e7d9e5084707137384a3b21f40a2d4d1d34708f0`.

Unified Week B-R2: `d4627c8749f4dd786632a38a28e8feb7ec7d453f`.

Unified Week B-R3: `915f7d56aca07d86d3e7201344120d5ef5657a27`.

Unified Week B-R4: `cb99f40cdf50f7e88ce108d857be2de36c5b2ae2`.

Unified Week B-R5: `6b7e0ed575b8d18f616a0752f689784030180b21`.

Unified Week B-R6: **implemented / awaiting Architect review** on `review/unified-week-b` (not deployed).

Do **not** deploy Week B through B-R6 until Architect accepts.
Do **not** begin Availability A.
Do **not** begin recurring calendar actions.
Do **not** begin next functional calendar projection work.
Do **not** mark Week A or Week B PRODUCTION ACCEPTED.

## Production / lineage

- Production application SHA: `eeb3ab4b49b3bdc1e2f6c2e5c6c90bddfc244d4a`
- Branch: `review/unified-week-b`
- Parent of B-R6: `6b7e0ed575b8d18f616a0752f689784030180b21`
- Alembic: **0034 / 0034** (no migration)
- Android `minSdk`: **23**
- Proactive: **OFF**, interval 60
- real-user `auto_label_enabled=true`
- Encrypted Architect context: untouched
- kalender pin: **0.29.1** (exact)

## What B-R6 is

Narrow Week closure corrective after B-R5 human feedback:

- visible capture label `+ Добавить` → `+ Задача` (plus icon kept, same Capture action);
- Today header: strong saturated blue circular date badge; pale full-header tint removed; body column tint `0.085` kept on wide current Week;
- desktop viewport calmness: freeze initial `initialTimeOfDay` after mount; skip no-op equivalent `/week` snapshots; keep live `nowCallback` current-time indicator.

## Out of this phase

Availability / free-busy, scheduled work, temporal hints, recurring calendar creation, calendar/provider mutation, task projection onto Week, kalender fork/vendor, deploy.

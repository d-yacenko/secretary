# Current task — Workflow Intelligence Pass E-C

## Status

Workflow Intelligence Pass E-C — Proactive Personalization: **implemented, awaiting Architect review**.

Do **not** deploy production. Do **not** start Design Quality Pass. Do **not** enable Proactive or auto-label.

## Branch

`review/workflow-intelligence-proactive-personalization-e-c`

Exact parent / production baseline: `f00604aeb5ef9ae3319a6e76bdf7093d623c1d8d`

## Production truth (unchanged by this pass)

- Production application SHA: `f00604aeb5ef9ae3319a6e76bdf7093d623c1d8d`
- Alembic on production: **`0033 / 0033`** (current/head); **no `0034`**
- `auto_label_enabled=false` in production
- Proactive unchanged / **OFF** (`proactive_enabled=false`, interval 60)
- Pass E-A: **ACCEPTED / CLOSED / PRODUCTION E2E ACCEPTED** at `fac292e7bb82fa95549f96ef83206fa2e55a5084`
- Pass E-B / accepted production SHA: `f00604aeb5ef9ae3319a6e76bdf7093d623c1d8d`
- Android `minSdk`: 23

## Goal

Integrate Pass E-B `PersonalRelevanceEvidenceSnapshot` into the existing Proactive Secretary loop so the one Secretary LLM can judge personal relationship and dependency. Facts/evidence stay in code; semantic judgment stays in the Secretary LLM.

## Non-goals

No Alembic `0034`. No new tables, settings, Flutter UI, REST, MCP, Proactive tools, second LLM/classifier, or job type. No automatic Task creation. No auto-label coupling. No production enablement.

Do not read, decrypt, modify, recreate, re-encrypt, or commit `secretary_architect_context_encrypted.md`.

## Planned production E2E (do not run yet)

1. Responsible / waiting_on_user — clear direct request requiring user action → likely notification/task proposal.
2. Participant — user involved, no current action → likely NONE.
3. Observer — globally important, user copied/observing, no personal action → NONE.
4. Waiting on others — user finished their part → normally NONE.
5. Waiting on user — someone clearly awaits the user → notification may be appropriate.
6. Related only — Arenadata/project/research sphere, no current action → NONE.
7. Label evidence helps interpretation but does not independently cause notification.
8. Conflicting/incomplete/truncated evidence → prefer uncertainty/silence.

False-positive suppression is a primary acceptance criterion. Stub LLM tests do not prove live model quality.

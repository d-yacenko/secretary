# Current task — Voice Assistant A Final Production Corrective R2

## Status

Voice Assistant A remains **CODE ACCEPTED / DEPLOYED / AWAITING FINAL USER MANUAL ACCEPTANCE**.
It is **NOT PRODUCTION ACCEPTED**. Voice B is not started.

Production application SHA remains `b0c75eaa5e879ee108afe90f152a29914d28a2f2`.
Production Alembic remains `0040`.
The corrective is **not deployed**. Implementation branch: `review/voice-assistant-a`.
Architect review is required before any deploy.

## Authorized scope

### A. Inbox review marker corrective

Fix the post-deploy physical acceptance failure where “Перечисли все новые сообщения” completed full enumeration and TTS, but the “Просмотрено досюда” marker did not move and a subsequent count still returned 18 new items.

Required:

- read-only production diagnosis of the failed turn where evidence remains available;
- deterministic backend enforcement of review versus inspect intent;
- preservation of frozen snapshot, verified receipt, and CAS completion semantics;
- structured completion observability with fail-closed behavior;
- end-to-end regression coverage for review pagination, playback completion, interruption/error, and completion outcomes.

### B. Teams incoming synchronization corrective

Fix the incoming synchronization pressure observed after Teams became operational. Current 60-second polling across approximately 319 chats causes Microsoft Graph rate limiting.

Required:

- quantify current request amplification and 429 behavior where evidence exists;
- safely reduce reconciliation amplification;
- implement Microsoft Graph Change Notifications as the primary incoming path, subject to the approved v1.0 capability/probe rules;
- retain polling as reconciliation/fallback;
- keep channels out of scope;
- do not broaden permissions without Architect authorization.

### C. Compatibility and safety

Preserve all accepted Voice Assistant A functionality.

Do not deploy, restart the production worker for implementation, manually move the marker, mark PRODUCTION ACCEPTED, or start Voice B.

## Ledger rules

Preserve historical production facts in `PROJECT_STATE.md` and `DECISIONS.md`. Update those ledgers only at the end with facts proven by this corrective. Do not claim the corrective is CODE ACCEPTED or PRODUCTION ACCEPTED.

## Stop condition

After implementation, relevant checks, factual ledger updates, commit, and push, stop for Architect review. No deployment is authorized by this task.

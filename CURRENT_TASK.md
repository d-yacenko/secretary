# Current task — Teams A + Communication Action Plan Integrity

## Status

**Teams A: IMPLEMENTED / AWAITING ARCHITECT REVIEW** on `review/teams-a`.

Authorized work in this phase only:

1. Communication Action Plan Integrity corrective for the observed post-Telegram-A missing approval-card defect.
2. Microsoft Teams personal-chat (work/school, delegated OAuth) on the existing unified communications architecture.

Do not mark CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED / CLOSED from this chat.

## Canonical base

SHA: `fd5d1497215e4c72033274908b69aebe42e175a9`  
Branch: `review/telegram-a`  
Commit: `Close Telegram A after production activation`

Do not use an Architect branch as implementation base.

Known production application before this phase: `c5d288444cc5053e79c0942cdbc23af3eebbbb50`  
Known production Alembic: **0039 / 0039**

Telegram A remains CLOSED / CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED. Do not reopen or redesign Telegram A.

## Scope (this phase only)

- Provider-neutral Assistant communication instructions and Action Plan integrity: prose such as «Подтвердите отправку» is not an approval proposal. Only a persisted Pending Action Plan renders the approval card.
- Microsoft Graph v1.0 delegated OAuth (`organizations`), oneOnOne and group chats, inbound polling, compose + `replyWithQuote`, existing `send_message`, existing approval/ExternalActionAttempt replay.

Out of this phase: Teams channels, meetings, consumer Microsoft accounts, Graph webhooks/subscriptions, live Teams write, deploy.

## Stop

Implementation + tests + commit + push + report are done. No live Teams write. No deploy. Do not start the next phase.

# Current task — Teams A + Communication Action Plan Integrity

## Status

**Teams A: IMPLEMENTED / AWAITING ARCHITECT REVIEW** on `review/teams-a`.

A-R3 application: `eb3af922f804e6faf1d895fd14c0973981ce515e`  
Parent: `fb980a886e406e816570603391f8319988271ab9`  
Accepted R2 application: `6fee41b57b8421699cefc1443c2e8e639f1214fe`  
Accepted R1 application: `49396cad686cc4631254ec389657b7a52d0dcf8f`

Do not mark CODE ACCEPTED / DEPLOYED / PRODUCTION ACCEPTED / CLOSED from this chat.

Authorized work in this phase only:

1. Communication Action Plan Integrity corrective for the observed post-Telegram-A missing approval-card defect.
2. Microsoft Teams personal-chat (work/school, delegated OAuth) on the existing unified communications architecture.
3. Architect R1 corrections (OAuth ID-token validation, Graph contracts, account uniqueness/disconnect, shared token refresh, invalid_grant reconnect-required, createdDateTime watermark, 429/Retry-After).
4. Architect R2 corrections (Microsoft multitenant signing-key issuer validation, GUID identity canonicalization, required ID-token time claims).
5. Architect R3 corrections (Graph replyWithQuote messageReference provenance; `replyToId` remains Graph fact; Secretary `quoted_message_id` is quote provenance).

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

A-R3 implementation + tests + commit + push + report are done. No live Teams OAuth/write. No deploy. Do not start the next phase.

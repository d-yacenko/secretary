# Current task — PHASE 14

## Goal

Synchronize Gmail into graph objects via Google OAuth.

## Prerequisites (credentials checkpoint)

- Google Cloud project with OAuth client credentials.
- Store refresh/access tokens encrypted at rest.
- Do not commit credentials or request Google secrets during planning.

## Do

1. Google OAuth web flow.
2. `GoogleAccount` storage with encrypted tokens.
3. Bounded initial Gmail sync → `objects(kind=email)`.
4. Queue embedding + analysis jobs for synced mail.

## Defer

- Gmail push/Pub/Sub until base sync is stable.
- External notification delivery.

## Accept

OAuth connect works; recent Gmail messages appear as graph email objects with provenance.

## Note

Secrets only in `.env`. Stop after phase for user review.

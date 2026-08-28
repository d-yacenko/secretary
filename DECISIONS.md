# Design decisions

Entries added when a choice will matter in later phases.

## PHASE 14.5 — User ownership and connector sync policy

- Every personal resource has explicit `user_id`; bootstrap owner for single-user operation until auth.
- `CurrentUserContext` is the only place that resolves "who is acting"; domain services receive `user_id`.
- User filter before retrieval/ranking (search, vector, context, graph).
- Source object uniqueness is `(user_id, provider, kind, external_id)`.
- Connector normal sync: bounded initial window; skip fetch/process for known unchanged external IDs.
- Gmail: list IDs → batch known lookup → fetch bodies only for unknown; no repeat embed for unchanged.
- OAuth state carries `user_id`; Google email is not Secretary user identity.
- `secrets/google-oauth-client.json` is deployment secret, not user data.

# Current task — Design Quality Pass D

## Status

**Design Quality Pass D: implemented / awaiting Architect review**

Branch: `review/design-quality-pass-d`
Exact application SHA: `9b433013c9651a38d1d4f3127e3d44189982d6b5`
Exact application parent/base: `ae7c549bfccedf3eddf1f017f5ead865a699b813`
Production application remains: `e535adfb9857d2407fac06998a1a5a14c2b73502`
Production Alembic: **0038 / 0038**
Migration: **NONE**. No `0039`. No backfill.
No deploy.

## Scope (client-only)

1. Temporal hint in Week uses a centered pill/`StadiumBorder` with light/surface fill. HARD calendar blocks and SOFT `scheduled_work` appearance are unchanged.
2. Week time-grid visual cadence is whole hours only, via public kalender 0.29.1 `MultiDayBodyComponents` custom hour-line and timeline builders. Event geometry, `initialHeightPerMinute = 0.9`, today tint, and now-line are unchanged.
3. Account disconnect is an explicit destructive action. First click opens a typed-confirmation dialog. `authController.forgetToken()` runs only after exact `delete` plus the confirm button. No server-side deletion.

No backend, API, Alembic, OpenAI, provider, or calendar-semantics changes.

Encrypted Architect context untouched.

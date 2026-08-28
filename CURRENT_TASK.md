# Current task — PHASE 08

## Goal

Never confuse source facts with LLM guesses.

## Do

1. Use edge/object states: `observed`, `proposed`, `confirmed`, `rejected`.
2. Use `origin`: `source`, `user`, `agent`, `system`.
3. Store confidence for inferred items.
4. Tests: email text → observed source; proposed meeting relation; confirmed after approval.

## Accept

Agent-created facts are distinguishable from observed source facts in storage and API responses.

## Note

No Secretary LLM yet. No job queues. Secrets only in `.env`.

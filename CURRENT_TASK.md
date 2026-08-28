# Current task — PHASE 09

## Goal

Add one Secretary LLM service, not many.

## Do

1. Create `SecretaryService` using OpenAI Responses API.
2. Model ID from env.
3. Structured Pydantic output for analysis (importance, urgency, possible task/deadline/meeting, relations, next action).
4. Pass bounded Context Resolver output only.
5. Fixture test for meeting + deadline from sample email context.

## Do not

- Add another agent.
- Expose SQL to the model.
- Execute external writes.

## Accept

Sample email context produces typed proposals; tests pass offline with fixtures.

## Note

No notifications or approval UI yet. Secrets only in `.env`.

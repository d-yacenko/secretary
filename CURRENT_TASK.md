# Current task — PHASE 03

## Goal

Make the graph usable without any LLM.

## Do

1. REST: `POST/GET/PATCH/DELETE /objects/{id}`, `POST/DELETE /edges/{id}`, `GET /objects/{id}/neighbors`, `GET /objects/{id}/context`.
2. Service layer — no SQL in route handlers.
3. Safe deletion (soft delete default or reject when uncertain).

## Accept

Integration test creates and links objects through HTTP.

# Current task — PHASE 05

## Goal

Add semantic retrieval without a second database.

## Do

1. Embedding service; model ID from env (default `text-embedding-3-small`).
2. Embed title, body, useful metadata on objects.
3. Store embeddings in pgvector column.
4. Semantic search service + lexical fallback (`ILIKE` or PostgreSQL text search).
5. `GET /search?q=...` with optional filters: kind, provider, project_id, limit.

## Accept

A semantically similar query finds a test object with different wording.

## Credentials checkpoint

OpenAI (or configured embedding provider) API key required for live embedding tests. If unavailable: implement connector + deterministic fake + document in PROJECT_STATE.md.

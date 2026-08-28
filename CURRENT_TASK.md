# Current task — PHASE 12

## Goal

Run synchronization and LLM analysis asynchronously using a PostgreSQL-backed job queue (no Redis).

## Do

1. Create `jobs` table (`type`, `payload` JSONB, `status`, `attempts`, `run_after`, `locked_at`, `last_error`, timestamps).
2. Worker: `FOR UPDATE SKIP LOCKED`, mark running, execute, done/failed with bounded retry backoff.
3. Initial job types: `sync_connector`, `embed_object`, `build_representations`, `analyze_object`, `send_notification`, `reconcile_connector`.
4. Keep worker in existing Docker Compose stack.

## Defer

- External connector implementations beyond enqueue stubs if not yet built.
- Public MCP / calendar / notification exposure.

## Accept

Jobs can be enqueued and processed by the worker with safe locking and retries.

## Note

Secrets only in `.env`. Stop after phase for user review.

# Current task — PHASE 02

## Goal

Create the smallest useful graph schema.

## Do

1. Table `objects`: id UUID PK, kind, title, body, provider, external_id, canonical_uri, status, start_at, due_at, metadata JSONB, origin, confidence, embedding VECTOR NULL, created_at, updated_at.
2. Table `edges`: id UUID PK, source_id, target_id, type, origin, confidence, state, metadata JSONB, created_at, updated_at.
3. Uniqueness on `(provider, kind, external_id)` when non-null.
4. Indexes: objects `kind`, `status`, `due_at`; edges source, target, type.

## Accept

Tests create: project, task, email, `task related_to email`, `task parent_of task`.

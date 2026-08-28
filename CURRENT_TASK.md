# Current task — PHASE 06

## Goal

Handle tiny files and huge documents without dumping everything into LLM context.

## Do

1. Table `representations`: object_id, kind, part_index, text, metadata, embedding, timestamps.
2. Kinds: full, summary, chunk, sample, schema, statistics.
3. Policy: small → full; medium → chunks + summary; large → summary + chunk embeddings.

## Accept

Tests for small file, medium text, large document representation paths.

## Note

Embedding API key in `.env` on VDS; never commit secrets.

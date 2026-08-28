# Current task — PHASE 07

## Goal

Build a compact context pack for one task or question without dumping large resources into LLM context.

## Do

1. `build_context(object_id=None, query=None, max_chars=...)`
2. Candidate sources: target object, graph neighbors, parent project, blockers, semantic matches, useful representations (summary + top chunks, not full document).
3. Context item fields: object_id, kind, title, short content/representation, why included, canonical_uri when available.

## Accept

A task linked to a long document receives: task, relation, document summary, top relevant chunks, document reference — not the full text.

## Note

No job queues yet. Embedding API key in `.env` on VDS; never commit secrets.

# Tool sequence analysis

## Payload retention

- `ai_audit_capture_sessions`: **0 rows** — payloads were NOT captured for any trace.
- `--include-payloads` returns metadata only; exact retrieve query strings and tool outputs are **not retained** in DB.
- Reconstruction uses `argument_structure.query.chars`, `current_user_message_chars`, and direct retrieve replay.

## Trace A — first failed query

**trace_id:** `5d13e0f1-3555-4352-b629-186ff73dca1f`  
**UTC:** 2026-09-03 17:11:10  
**user_message_chars:** 92  
**model_rounds:** 5 | **final response_chars:** 535

| Seq | Event | Detail |
|-----|-------|--------|
| 2 | model_round | round 1, reasoning_tokens=15 |
| 3 | **retrieve** | kind=file, time_scope=recent, query ~68 chars, limit=5 → raw 160 / visible 61 (truncated) — **0 file hits** |
| 4 | model_round | round 2 |
| 5 | **retrieve** | kind=null, time_scope=all, query ~33 chars, limit=5 → raw 9885 / visible 3220 — **5 hits, no target** |
| 6 | model_round | round 3 |
| 7 | **get_context** | object_id=`857f1fda-6c93-4e07-a6f6-bf037a3b30be` («Архитектура платформы данных») — **wrong object** |
| 8 | model_round | round 4 |
| 9 | **retrieve** | kind=null, query ~55 chars → raw 9090 / visible 3013 — **no target** |
| 10 | model_round | round 5, response_chars=535 |

**Not called:** `query_objects`, `get_object`, `search_objects`

## Trace B — second failed query

**trace_id:** `9aaba601-235f-4db3-8dc1-3e8a7f785f66`  
**UTC:** 2026-09-03 17:12:18  
**user_message_chars:** 60  
**model_rounds:** 3 | **final response_chars:** 281

| Seq | Event | Detail |
|-----|-------|--------|
| 2 | model_round | round 1 |
| 3 | **retrieve** | kind=all, query ~60 chars → raw 159 / visible 60 — **no target** |
| 4 | model_round | round 2 |
| 5 | **retrieve** | kind=all, query ~53 chars → raw 159 / visible 60 — **no target** |
| 6 | model_round | round 3, response_chars=281 |

**Not called:** `query_objects`, `get_object`, `get_context`

## Misleading hit (trace A only)

`857f1fda-6c93-4e07-a6f6-bf037a3b30be` — «Архитектура платформы данных» (yandex_calendar event).

get_context showed «Классификация применяемого ПО» — partial token overlap, **not** target phrase.

Target xlsx `19940b16` never appeared in any retrieve output.

## Hypothesis mapping

| Hypothesis | Result |
|------------|--------|
| A — wrong tools | **Partially rejected** — retrieve WAS used; query_objects NOT used |
| B — Object absent from retrieve | **CONFIRMED** for target phrase |
| C — Rep lacks searchable content | **CONFIRMED** |
| D — get_context never on target | **CONFIRMED** (called on wrong object in trace A only) |
| E — rows[1:6] sampling | **CONFIRMED** as root cause |

## Evidence disappearance step

**Before retrieval:** target phrase never in Representation.text (extraction policy).  
**At retrieve:** FTS/trigram cannot match → Object not in candidate pool for phrase queries.  
**At get_context (trace A):** wrong object inspected; target never opened.

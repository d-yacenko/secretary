# Current task — PHASE 28D-A awaiting architect review

## Status

PHASE 28C: **fully accepted/closed** at `8b02c32a3ad653e24f3cb11309f2875ccaf7dca3`.

Final PHASE 28C-R1-R1 manual E2E: **PASS** (sync banner clears after settlement).

PHASE 28D-A — End-to-End AI Execution Observability: **implemented, awaiting architect review**.

PHASE 29A MUST NOT start until PHASE 28D reaches architect-approved checkpoint.

## Branch

`review/phase-28d-ai-execution-observability`

## Implemented in 28D-A

- User-scoped `AITrace` / `AITraceEvent` persistence (Alembic `0024`)
- Workloads: `assistant_interactive`, `assistant_action_plan_finalize`, `background_summary`, `background_correlation`, `embedding`, `transcription`
- Per-round Assistant Responses API tracing + tool execution tracing
- Background AI tracing (summarizer, correlation judge, embeddings, transcription)
- Bounded full-payload capture session (OFF by default)
- API: `/me/ai-audit/summary`, `/me/ai-audit/traces/{id}`, `/me/ai-audit/capture`
- CLI: `python -m app.cli.ai_audit_report`

## Not in 28D-A (documented for later subphases)

- **28D-B** controlled cost/behavior audit (no optimizations yet)
- **28D-C** workload-specific model profiles / routing
- **28D-D** experimental two-stage Assistant
- **28D-E** benchmark and closure

## Temporary audit capture

```bash
# Enable 60-minute payload capture (authenticated API):
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://web-itx.duckdns.org/secretary/me/ai-audit/capture \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes": 60}'

# Sanitized summary (CLI on VDS):
cd /opt/secretary/backend && python -m app.cli.ai_audit_report summary --hours 24

# Trace waterfall with payloads (only while capture active):
python -m app.cli.ai_audit_report trace <trace_id> --include-payloads
```

## Next after 28D-A acceptance

**28D-B** controlled cost/behavior audit using new telemetry baseline.

## Not started

- Phase 29A
- model routing / reasoning optimization
- merge to main

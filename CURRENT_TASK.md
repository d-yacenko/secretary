# Current task — PHASE 28D-A-R1 corrective deployed, awaiting architect review

## Status

PHASE 28C: **fully accepted/closed** at `8b02c32a3ad653e24f3cb11309f2875ccaf7dca3`.

PHASE 28D-A initial implementation (`9090ee8`): **architect corrective required** — observability foundation good but not baseline-ready.

PHASE 28D-A-R1 — AI Audit Trace Correctness, Privacy & Baseline Readiness Corrective: **implemented and deployed**, **awaiting architect review**.

PHASE 28D-B/C/D/E: **NOT started**.

PHASE 29A: **NOT started**.

Model routing, two-stage Assistant, workload-specific models: **NOT started**.

## Branch

`review/phase-28d-a-r1`

## R1 corrective scope (observability correctness only)

- Non-destructive metadata-only trace reads (no ORM mutation / DB payload loss)
- Per-event `payload_expires_at` retention (Alembic `0025`)
- Full diagnostic payload capture for all AI workloads when capture active
- Canonical validated tool-argument tracing + capture-OFF structural privacy
- Summary metrics distinguish traces vs model/API calls
- Bounded trace listing API + CLI `list`
- Background `job_id` + `parent_trace_id` provenance
- Assistant input component accounting without user-message double-count
- Correlation raw vs accepted decision counts
- Transcription failure model-call events
- Failure-path consistency across instrumented workloads

## Not changed in R1

- Assistant model / medium reasoning configuration
- AI behavior optimization
- PHASE 28D-B controlled baseline export

## Temporary audit capture

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  https://web-itx.duckdns.org/secretary/me/ai-audit/capture \
  -H "Content-Type: application/json" \
  -d '{"duration_minutes":60}'
```

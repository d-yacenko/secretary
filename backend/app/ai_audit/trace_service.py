"""Persisted AI trace storage, queries, and capture sessions."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai_audit.constants import (
    DEFAULT_CAPTURE_DURATION,
    MAX_EVENTS_PER_TRACE,
    MAX_SUMMARY_RANGE_DAYS,
    METADATA_RETENTION,
    PAYLOAD_RETENTION_AFTER_CAPTURE,
)
from app.ai_audit.sanitizer import sanitize_for_audit
from app.db.models import AIAuditCaptureSession, AITrace, AITraceEvent
from app.services.job_queue_service import utcnow


class AITraceService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start_trace(
        self,
        user_id: UUID,
        workload: str,
        *,
        parent_trace_id: UUID | None = None,
        job_id: UUID | None = None,
        object_id: UUID | None = None,
    ) -> AITrace:
        now = utcnow()
        trace = AITrace(
            user_id=user_id,
            workload=workload,
            parent_trace_id=parent_trace_id,
            job_id=job_id,
            object_id=object_id,
            started_at=now,
            success=True,
        )
        self._session.add(trace)
        self._session.flush()
        return trace

    def record_event(
        self,
        trace_id: UUID,
        user_id: UUID,
        sequence: int,
        event_type: str,
        metadata: dict[str, Any],
    ) -> AITraceEvent:
        event = AITraceEvent(
            trace_id=trace_id,
            user_id=user_id,
            sequence=sequence,
            event_type=event_type,
            metadata_=sanitize_for_audit(metadata),
        )
        self._session.add(event)
        self._session.flush()
        return event

    def finish_trace(
        self,
        trace_id: UUID,
        user_id: UUID,
        *,
        success: bool,
        error_category: str | None = None,
    ) -> None:
        trace = self._require_trace(trace_id, user_id)
        trace.finished_at = utcnow()
        trace.success = success
        trace.error_category = error_category

    def get_trace(self, trace_id: UUID, user_id: UUID) -> AITrace | None:
        return self._session.scalar(
            select(AITrace).where(AITrace.id == trace_id, AITrace.user_id == user_id)
        )

    def list_trace_events(
        self,
        trace_id: UUID,
        user_id: UUID,
        *,
        include_payloads: bool = False,
    ) -> list[AITraceEvent]:
        trace = self.get_trace(trace_id, user_id)
        if trace is None:
            return []
        events = list(
            self._session.scalars(
                select(AITraceEvent)
                .where(
                    AITraceEvent.trace_id == trace_id,
                    AITraceEvent.user_id == user_id,
                )
                .order_by(AITraceEvent.sequence)
                .limit(MAX_EVENTS_PER_TRACE)
            )
        )
        if not include_payloads:
            for event in events:
                meta = dict(event.metadata_ or {})
                if "payloads" in meta:
                    meta["payloads"] = "[withheld]"
                    event.metadata_ = meta
        return events

    def build_summary(
        self,
        user_id: UUID,
        started_after: datetime,
        started_before: datetime,
    ) -> dict[str, Any]:
        if started_before <= started_after:
            raise ValueError("invalid time range")
        if (started_before - started_after).days > MAX_SUMMARY_RANGE_DAYS:
            raise ValueError("time range too large")

        traces = list(
            self._session.scalars(
                select(AITrace).where(
                    AITrace.user_id == user_id,
                    AITrace.started_at >= started_after,
                    AITrace.started_at < started_before,
                )
            )
        )
        trace_ids = [trace.id for trace in traces]
        events: list[AITraceEvent] = []
        if trace_ids:
            events = list(
                self._session.scalars(
                    select(AITraceEvent).where(
                        AITraceEvent.user_id == user_id,
                        AITraceEvent.trace_id.in_(trace_ids),
                    )
                )
            )

        by_workload: dict[str, int] = {}
        by_model: dict[str, int] = {}
        totals = {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cache_write_tokens": 0,
        }
        model_rounds = 0
        tool_calls = 0
        failures = 0
        assistant_turns = 0
        assistant_rounds: list[int] = []
        assistant_tool_counts: list[int] = []
        background_counts: dict[str, int] = {}

        for trace in traces:
            by_workload[trace.workload] = by_workload.get(trace.workload, 0) + 1
            if trace.workload == "assistant_interactive":
                assistant_turns += 1
            if trace.workload.startswith("background_") or trace.workload == "embedding":
                background_counts[trace.workload] = background_counts.get(trace.workload, 0) + 1
            if not trace.success:
                failures += 1

        per_trace_rounds: dict[UUID, int] = {}
        per_trace_tools: dict[UUID, int] = {}

        for event in events:
            meta = event.metadata_ or {}
            if event.event_type in ("model_round", "model_round_failed"):
                model_rounds += 1
                per_trace_rounds[event.trace_id] = per_trace_rounds.get(event.trace_id, 0) + 1
                model = meta.get("model")
                if model:
                    by_model[str(model)] = by_model.get(str(model), 0) + 1
                for key in totals:
                    value = meta.get(key)
                    if isinstance(value, int):
                        totals[key] += value
            if event.event_type == "tool_call":
                tool_calls += 1
                per_trace_tools[event.trace_id] = per_trace_tools.get(event.trace_id, 0) + 1

        for trace_id in trace_ids:
            if trace_id in per_trace_rounds:
                assistant_rounds.append(per_trace_rounds[trace_id])
            if trace_id in per_trace_tools:
                assistant_tool_counts.append(per_trace_tools[trace_id])

        def _avg(values: list[int]) -> float | None:
            return sum(values) / len(values) if values else None

        def _max(values: list[int]) -> int | None:
            return max(values) if values else None

        return {
            "trace_count": len(traces),
            "calls_by_workload": by_workload,
            "calls_by_model": by_model,
            "total_input_tokens": totals["input_tokens"],
            "total_cached_input_tokens": totals["cached_input_tokens"],
            "total_output_tokens": totals["output_tokens"],
            "total_reasoning_tokens": totals["reasoning_tokens"],
            "total_cache_write_tokens": totals["cache_write_tokens"],
            "model_round_count": model_rounds,
            "tool_call_count": tool_calls,
            "failure_count": failures,
            "assistant_turn_count": assistant_turns,
            "assistant_avg_rounds": _avg(assistant_rounds),
            "assistant_max_rounds": _max(assistant_rounds),
            "assistant_avg_tool_calls": _avg(assistant_tool_counts),
            "assistant_max_tool_calls": _max(assistant_tool_counts),
            "background_call_counts": background_counts,
            "started_after": started_after.isoformat(),
            "started_before": started_before.isoformat(),
        }

    def enable_capture(
        self,
        user_id: UUID,
        duration: timedelta = DEFAULT_CAPTURE_DURATION,
    ) -> AIAuditCaptureSession:
        now = utcnow()
        session_row = AIAuditCaptureSession(
            user_id=user_id,
            enabled_at=now,
            expires_at=now + duration,
            payload_retention_until=now + duration + PAYLOAD_RETENTION_AFTER_CAPTURE,
        )
        self._session.merge(session_row)
        self._session.flush()
        return session_row

    def disable_capture(self, user_id: UUID) -> None:
        row = self._session.get(AIAuditCaptureSession, user_id)
        if row is not None:
            self._session.delete(row)

    def get_capture_session(self, user_id: UUID) -> AIAuditCaptureSession | None:
        row = self._session.get(AIAuditCaptureSession, user_id)
        if row is None:
            return None
        if row.expires_at <= utcnow():
            return None
        return row

    def is_payload_capture_active(self, user_id: UUID) -> bool:
        return self.get_capture_session(user_id) is not None

    def cleanup_expired(self) -> dict[str, int]:
        now = utcnow()
        metadata_cutoff = now - METADATA_RETENTION
        capture_rows = list(self._session.scalars(select(AIAuditCaptureSession)))
        expired_capture_users = [
            row.user_id
            for row in capture_rows
            if row.payload_retention_until <= now
        ]
        if expired_capture_users:
            self._session.execute(
                delete(AIAuditCaptureSession).where(
                    AIAuditCaptureSession.user_id.in_(expired_capture_users)
                )
            )
        scrubbed = 0
        if expired_capture_users:
            events = list(
                self._session.scalars(
                    select(AITraceEvent).where(
                        AITraceEvent.user_id.in_(expired_capture_users)
                    )
                )
            )
            for event in events:
                meta = dict(event.metadata_ or {})
                if "payloads" in meta:
                    meta.pop("payloads", None)
                    event.metadata_ = meta
                    scrubbed += 1
        old_trace_ids = list(
            self._session.scalars(
                select(AITrace.id).where(AITrace.started_at < metadata_cutoff)
            )
        )
        deleted_events = 0
        deleted_traces = 0
        if old_trace_ids:
            result = self._session.execute(
                delete(AITraceEvent).where(AITraceEvent.trace_id.in_(old_trace_ids))
            )
            deleted_events = result.rowcount or 0
            result = self._session.execute(
                delete(AITrace).where(AITrace.id.in_(old_trace_ids))
            )
            deleted_traces = result.rowcount or 0
        return {
            "scrubbed_payload_events": scrubbed,
            "deleted_events": deleted_events,
            "deleted_traces": deleted_traces,
        }

    def _require_trace(self, trace_id: UUID, user_id: UUID) -> AITrace:
        trace = self.get_trace(trace_id, user_id)
        if trace is None:
            raise ValueError("trace not found")
        return trace

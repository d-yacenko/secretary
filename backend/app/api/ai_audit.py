"""Authenticated AI audit read API (PHASE 28D-A)."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.ai_audit.constants import DEFAULT_CAPTURE_DURATION_MINUTES, MAX_CAPTURE_DURATION_MINUTES
from app.ai_audit.trace_service import AITraceService
from app.api.deps import get_current_user, get_db
from app.core.current_user import CurrentUserContext

router = APIRouter(tags=["ai-audit"])


class AIAuditCaptureSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled_at: datetime
    expires_at: datetime
    payload_retention_until: datetime


class AIAuditCaptureEnableRequest(BaseModel):
    duration_minutes: int = Field(
        default=DEFAULT_CAPTURE_DURATION_MINUTES,
        ge=1,
        le=MAX_CAPTURE_DURATION_MINUTES,
    )


class AITraceEventOut(BaseModel):
    sequence: int
    event_type: str
    created_at: datetime
    metadata: dict = Field(alias="metadata_")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class AITraceDetailOut(BaseModel):
    trace_id: UUID
    workload: str
    parent_trace_id: UUID | None
    job_id: UUID | None
    object_id: UUID | None
    started_at: datetime
    finished_at: datetime | None
    success: bool
    error_category: str | None
    events: list[AITraceEventOut]


@router.get("/me/ai-audit/summary")
def get_ai_audit_summary(
    started_after: datetime = Query(...),
    started_before: datetime = Query(...),
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> dict:
    service = AITraceService(session)
    try:
        return service.build_summary(
            current_user.user_id,
            started_after,
            started_before,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/me/ai-audit/traces/{trace_id}", response_model=AITraceDetailOut)
def get_ai_audit_trace(
    trace_id: UUID,
    include_payloads: bool = Query(default=False),
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> AITraceDetailOut:
    service = AITraceService(session)
    trace = service.get_trace(trace_id, current_user.user_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
    if include_payloads and not service.is_payload_capture_active(current_user.user_id):
        include_payloads = False
    events = service.list_trace_events(
        trace_id,
        current_user.user_id,
        include_payloads=include_payloads,
    )
    return AITraceDetailOut(
        trace_id=trace.id,
        workload=trace.workload,
        parent_trace_id=trace.parent_trace_id,
        job_id=trace.job_id,
        object_id=trace.object_id,
        started_at=trace.started_at,
        finished_at=trace.finished_at,
        success=trace.success,
        error_category=trace.error_category,
        events=[
            AITraceEventOut(
                sequence=event.sequence,
                event_type=event.event_type,
                created_at=event.created_at,
                metadata_=event.metadata_ or {},
            )
            for event in events
        ],
    )


@router.get("/me/ai-audit/capture", response_model=AIAuditCaptureSessionOut | None)
def get_ai_audit_capture(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> AIAuditCaptureSessionOut | None:
    row = AITraceService(session).get_capture_session(current_user.user_id)
    if row is None:
        return None
    return AIAuditCaptureSessionOut.model_validate(row)


@router.post("/me/ai-audit/capture", response_model=AIAuditCaptureSessionOut)
def enable_ai_audit_capture(
    data: AIAuditCaptureEnableRequest,
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> AIAuditCaptureSessionOut:
    from datetime import timedelta

    row = AITraceService(session).enable_capture(
        current_user.user_id,
        duration=timedelta(minutes=data.duration_minutes),
    )
    session.commit()
    return AIAuditCaptureSessionOut.model_validate(row)


@router.delete("/me/ai-audit/capture", status_code=status.HTTP_204_NO_CONTENT)
def disable_ai_audit_capture(
    session: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user),
) -> None:
    AITraceService(session).disable_capture(current_user.user_id)
    session.commit()

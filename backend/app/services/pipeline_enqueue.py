"""Job enqueue helpers for correlation and semantic summary pipeline."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_audit.context import get_active_trace
from app.db.models import Job
from app.jobs.constants import (
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_CORRELATE_OBJECT,
    JOB_TYPE_EMBED_OBJECT,
    JOB_TYPE_EXTRACT_EXPLICIT_RESOURCE_CONTENT,
    JOB_TYPE_SUMMARIZE_RESOURCE,
)
from app.services.correlation_constants import CORRELATION_TRIGGER_KINDS
from app.services.job_queue_service import JobQueueService


def _active_parent_trace_id() -> str | None:
    active = get_active_trace()
    if active is None:
        return None
    return str(active.trace_id)


def enqueue_extract_explicit_resource_content(
    session: Session,
    object_id: UUID,
    user_id: UUID,
    expected_revision: str | None,
    extraction_version: str,
) -> None:
    if _has_pending_job(
        session,
        user_id,
        JOB_TYPE_EXTRACT_EXPLICIT_RESOURCE_CONTENT,
        object_id,
        {
            "expected_content_revision": expected_revision,
            "extraction_version": extraction_version,
        },
    ):
        return
    payload: dict = {
        "object_id": str(object_id),
        "expected_content_revision": expected_revision,
        "extraction_version": extraction_version,
    }
    parent_trace_id = _active_parent_trace_id()
    if parent_trace_id is not None:
        payload["parent_trace_id"] = parent_trace_id
    JobQueueService(session).enqueue(
        JOB_TYPE_EXTRACT_EXPLICIT_RESOURCE_CONTENT,
        payload,
        user_id=user_id,
    )


def enqueue_summarize_resource(
    session: Session,
    object_id: UUID,
    user_id: UUID,
    expected_revision: str | None,
) -> None:
    if _has_pending_job(
        session,
        user_id,
        JOB_TYPE_SUMMARIZE_RESOURCE,
        object_id,
        {"expected_revision": expected_revision},
    ):
        return
    payload: dict = {
        "object_id": str(object_id),
        "expected_revision": expected_revision,
    }
    parent_trace_id = _active_parent_trace_id()
    if parent_trace_id is not None:
        payload["parent_trace_id"] = parent_trace_id
    JobQueueService(session).enqueue(
        JOB_TYPE_SUMMARIZE_RESOURCE,
        payload,
        user_id=user_id,
    )


def enqueue_correlate_object(
    session: Session,
    object_id: UUID,
    user_id: UUID,
    object_kind: str,
) -> None:
    if object_kind not in CORRELATION_TRIGGER_KINDS:
        return
    if _has_pending_job(session, user_id, JOB_TYPE_CORRELATE_OBJECT, object_id, {}):
        return
    payload: dict = {"object_id": str(object_id)}
    parent_trace_id = _active_parent_trace_id()
    if parent_trace_id is not None:
        payload["parent_trace_id"] = parent_trace_id
    JobQueueService(session).enqueue(
        JOB_TYPE_CORRELATE_OBJECT,
        payload,
        user_id=user_id,
    )


def enqueue_embed_object(session: Session, object_id: UUID, user_id: UUID) -> None:
    if _has_pending_job(session, user_id, JOB_TYPE_EMBED_OBJECT, object_id, {}):
        return
    payload: dict = {"object_id": str(object_id)}
    parent_trace_id = _active_parent_trace_id()
    if parent_trace_id is not None:
        payload["parent_trace_id"] = parent_trace_id
    JobQueueService(session).enqueue(
        JOB_TYPE_EMBED_OBJECT,
        payload,
        user_id=user_id,
    )


def _has_pending_job(
    session: Session,
    user_id: UUID,
    job_type: str,
    object_id: UUID,
    extra: dict,
) -> bool:
    jobs = session.scalars(
        select(Job).where(
            Job.user_id == user_id,
            Job.type == job_type,
            Job.status.in_((JOB_STATUS_PENDING, JOB_STATUS_RUNNING)),
        )
    )
    object_key = str(object_id)
    for job in jobs:
        payload = job.payload or {}
        if payload.get("object_id") != object_key:
            continue
        for key, value in extra.items():
            if payload.get(key) != value:
                break
        else:
            return True
    return False

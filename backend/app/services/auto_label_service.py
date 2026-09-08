from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_audit.constants import WORKLOAD_BACKGROUND_AUTO_LABEL
from app.ai_audit.context import ai_trace_session, get_active_trace
from app.db.models import Job, Object, UserSettings
from app.domain.labels import KIND_LABEL
from app.domain.object_visibility import is_object_hidden_from_active_reads
from app.domain.scheduled_activity import KIND_SCHEDULED_ACTIVITY
from app.jobs.constants import (
    JOB_STATUS_DONE,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_AUTO_LABEL_OBJECT,
)
from app.llm.auto_label_classifier import (
    AutoLabelClassifier,
    create_auto_label_classifier_from_effective,
)
from app.services.auto_label_constants import (
    ANNOTATION_SOURCE_BACKGROUND_AUTO_LABEL,
    AUTO_LABEL_ELIGIBLE_ORIGINS,
    AUTO_LABEL_ENABLED_DEFAULT,
    AUTO_LABEL_MAX_CONTENT_CHARS,
    AUTO_LABEL_MAX_PENDING_PER_USER,
    AUTO_LABEL_MAX_TITLE_CHARS,
    AUTO_LABEL_MAX_VOCABULARY,
    AUTO_LABEL_VERSION,
    METADATA_ANNOTATION_SOURCE,
    METADATA_AUTO_LABEL_SIGNATURE,
    METADATA_AUTO_LABEL_VERSION,
    METADATA_RATIONALE,
    PARENT_EMAIL_ID_KEY,
)
from app.services.auto_label_models import (
    AutoLabelCandidate,
    AutoLabelObjectInput,
    BackgroundAssignOutcome,
)
from app.services.correlation_constants import SEMANTIC_SUMMARY_METADATA_KEY
from app.services.effective_user_settings_service import EffectiveUserSettingsService
from app.services.job_queue_service import JobQueueService
from app.services.label_service import LabelService
from app.services.provenance import AGENT_ORIGIN, CONFIRMED_STATE, REJECTED_STATE
from app.services.user_identity_context_service import (
    UserIdentityContextService,
    bound_runtime_identity_facts,
)


def is_auto_label_enabled(session: Session, user_id: UUID) -> bool:
    row = session.get(UserSettings, user_id)
    if row is None:
        return AUTO_LABEL_ENABLED_DEFAULT
    return bool(row.auto_label_enabled)


def object_is_auto_label_eligible(obj: Object) -> bool:
    if is_object_hidden_from_active_reads(obj) or obj.state == REJECTED_STATE:
        return False
    if obj.kind in {KIND_LABEL, KIND_SCHEDULED_ACTIVITY}:
        return False
    if obj.origin not in AUTO_LABEL_ELIGIBLE_ORIGINS:
        return False
    parent_email_id = (obj.metadata_ or {}).get(PARENT_EMAIL_ID_KEY)
    return not (isinstance(parent_email_id, str) and bool(parent_email_id.strip()))


def bounded_object_input(obj: Object) -> AutoLabelObjectInput:
    title = (obj.title or "")[:AUTO_LABEL_MAX_TITLE_CHARS]
    summary = (obj.metadata_ or {}).get(SEMANTIC_SUMMARY_METADATA_KEY)
    if isinstance(summary, str) and summary.strip():
        content = summary.strip()[:AUTO_LABEL_MAX_CONTENT_CHARS]
        source = "semantic_summary"
    elif obj.body and obj.body.strip():
        content = obj.body.strip()[:AUTO_LABEL_MAX_CONTENT_CHARS]
        source = "body"
    else:
        content = title
        source = "title"
    return AutoLabelObjectInput(
        object_id=obj.id,
        kind=obj.kind,
        title=title,
        provider=obj.provider,
        content=content,
        content_source=source,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def object_signature(obj_input: AutoLabelObjectInput) -> str:
    return _sha256_text(
        _canonical_json(
            {
                "object_id": str(obj_input.object_id),
                "kind": obj_input.kind,
                "title": obj_input.title,
                "provider": obj_input.provider,
                "content": obj_input.content,
                "content_source": obj_input.content_source,
            }
        )
    )


def vocabulary_signature(candidates: list[AutoLabelCandidate]) -> str:
    ordered = sorted(candidates, key=lambda item: item.label_id.bytes)
    return _sha256_text(
        _canonical_json(
            [{"label_id": str(item.label_id), "title": item.title} for item in ordered]
        )
    )


def classification_signature(object_sig: str, vocabulary_sig: str) -> str:
    return _sha256_text(f"{AUTO_LABEL_VERSION}\n{object_sig}\n{vocabulary_sig}")


def enqueue_auto_label_object(
    session: Session,
    object_id: UUID,
    user_id: UUID,
    *,
    parent_trace_id: UUID | str | None = None,
) -> None:
    if not is_auto_label_enabled(session, user_id):
        return
    obj = session.scalar(select(Object).where(Object.id == object_id, Object.user_id == user_id))
    if obj is None or not object_is_auto_label_eligible(obj):
        return
    label_count = count_active_labels(session, user_id)
    if label_count == 0 or label_count > AUTO_LABEL_MAX_VOCABULARY:
        return
    candidates = load_active_label_candidates(session, user_id)
    obj_input = bounded_object_input(obj)
    object_sig = object_signature(obj_input)
    vocab_sig = vocabulary_signature(candidates)
    class_sig = classification_signature(object_sig, vocab_sig)
    if _has_signature_job(session, user_id, object_id, class_sig):
        return
    if _pending_or_running_count(session, user_id) >= AUTO_LABEL_MAX_PENDING_PER_USER:
        return
    payload: dict = {
        "object_id": str(object_id),
        "classification_signature": class_sig,
        "object_signature": object_sig,
        "vocabulary_signature": vocab_sig,
    }
    trace_id = parent_trace_id
    if trace_id is None:
        active = get_active_trace()
        if active is not None:
            trace_id = active.trace_id
    if trace_id is not None:
        payload["parent_trace_id"] = str(trace_id)
    JobQueueService(session).enqueue(JOB_TYPE_AUTO_LABEL_OBJECT, payload, user_id=user_id)


def count_active_labels(session: Session, user_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Object)
            .where(*LabelService(session, user_id)._active_label_filters())
        )
        or 0
    )


def load_active_label_candidates(session: Session, user_id: UUID) -> list[AutoLabelCandidate]:
    labels = list(
        session.scalars(
            select(Object)
            .where(*LabelService(session, user_id)._active_label_filters())
            .order_by(Object.id.asc())
            .limit(AUTO_LABEL_MAX_VOCABULARY + 1)
        )
    )
    return [AutoLabelCandidate(label_id=item.id, title=item.title) for item in labels]


def _has_signature_job(
    session: Session,
    user_id: UUID,
    object_id: UUID,
    class_sig: str,
) -> bool:
    jobs = session.scalars(
        select(Job).where(
            Job.user_id == user_id,
            Job.type == JOB_TYPE_AUTO_LABEL_OBJECT,
            Job.status.in_((JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_DONE)),
        )
    )
    object_key = str(object_id)
    for job in jobs:
        payload = job.payload or {}
        if payload.get("object_id") != object_key:
            continue
        if payload.get("classification_signature") == class_sig:
            return True
    return False


def _pending_or_running_count(session: Session, user_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.user_id == user_id,
                Job.type == JOB_TYPE_AUTO_LABEL_OBJECT,
                Job.status.in_((JOB_STATUS_PENDING, JOB_STATUS_RUNNING)),
            )
        )
        or 0
    )


class AutoLabelService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        *,
        classifier: AutoLabelClassifier | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._classifier = classifier

    def run_job(self, payload: dict) -> BackgroundAssignOutcome:
        if not is_auto_label_enabled(self._session, self._user_id):
            return BackgroundAssignOutcome()
        object_id = UUID(str(payload["object_id"]))
        payload_sig = str(payload.get("classification_signature") or "")
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None or not object_is_auto_label_eligible(obj):
            return BackgroundAssignOutcome()
        label_count = count_active_labels(self._session, self._user_id)
        if label_count == 0 or label_count > AUTO_LABEL_MAX_VOCABULARY:
            return BackgroundAssignOutcome()
        candidates = load_active_label_candidates(self._session, self._user_id)
        obj_input = bounded_object_input(obj)
        object_sig = object_signature(obj_input)
        vocab_sig = vocabulary_signature(candidates)
        current_sig = classification_signature(object_sig, vocab_sig)
        if current_sig != payload_sig:
            enqueue_auto_label_object(self._session, object_id, self._user_id)
            return BackgroundAssignOutcome()
        parent_raw = payload.get("parent_trace_id")
        parent_trace_id = UUID(str(parent_raw)) if parent_raw else None
        with ai_trace_session(
            self._user_id,
            WORKLOAD_BACKGROUND_AUTO_LABEL,
            object_id=object_id,
            parent_trace_id=parent_trace_id,
        ):
            classifier = self._classifier or create_auto_label_classifier_from_effective(
                EffectiveUserSettingsService.build(self._session).get_effective_settings(
                    self._user_id
                )
            )
            identity = bound_runtime_identity_facts(
                UserIdentityContextService.build(self._session).get_runtime_facts(self._user_id)
            )
            result = classifier.classify(
                obj=obj_input,
                candidates=candidates,
                identity_facts=identity if not identity.is_empty() else None,
            )
            labels = LabelService(
                self._session,
                self._user_id,
                origin=AGENT_ORIGIN,
                state=CONFIRMED_STATE,
            )
            outcome = BackgroundAssignOutcome()
            created = already = suppressed = 0
            for assignment in result.assignments:
                apply_result = labels.assign_label_background(
                    object_id,
                    assignment.label_id,
                    confidence=assignment.confidence,
                    metadata={
                        METADATA_ANNOTATION_SOURCE: ANNOTATION_SOURCE_BACKGROUND_AUTO_LABEL,
                        METADATA_AUTO_LABEL_VERSION: AUTO_LABEL_VERSION,
                        METADATA_AUTO_LABEL_SIGNATURE: current_sig,
                        METADATA_RATIONALE: assignment.rationale,
                    },
                )
                created += apply_result.created
                already += apply_result.already_present
                suppressed += apply_result.suppressed_rejected
            outcome = BackgroundAssignOutcome(
                created=created,
                already_present=already,
                suppressed_rejected=suppressed,
            )
            active = get_active_trace()
            if active is not None:
                active.record_event(
                    "auto_label_result",
                    {
                        "candidate_label_count": len(candidates),
                        "raw_assignment_count": result.raw_assignment_count,
                        "accepted_assignment_count": len(result.assignments),
                        "created_assignment_count": created,
                        "already_present_count": already,
                        "suppressed_rejected_count": suppressed,
                    },
                )
            return outcome

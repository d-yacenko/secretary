from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_audit.constants import WORKLOAD_BACKGROUND_TEMPORAL_SIGNAL
from app.ai_audit.context import ai_trace_session, get_active_trace
from app.api.schemas import EdgeCreate, ObjectCreate
from app.db.models import Edge, Job, Object, UserSettings
from app.domain.object_visibility import is_object_hidden_from_active_reads
from app.domain.temporal_hint import (
    EDGE_TYPE_TEMPORAL_CONFIRMATION,
    EDGE_TYPE_TEMPORAL_EVIDENCE,
    KIND_TEMPORAL_HINT,
    LIFECYCLE_SUPERSEDED_BY_CALENDAR,
    LIFECYCLE_UNRESOLVED,
    PARTICIPATION_EXPECTED,
    PARTICIPATION_OTHERS_ONLY,
    PARTICIPATION_POSSIBLE,
    PARTICIPATION_UNKNOWN,
    RESULT_EXACT_TEMPORAL_SIGNAL,
    START_PRECISION_EXACT,
)
from app.jobs.constants import (
    JOB_STATUS_DONE,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_EXTRACT_TEMPORAL_SIGNAL,
    JOB_TYPE_RECONCILE_TEMPORAL_HINTS,
)
from app.llm.temporal_match_judge import (
    TemporalMatchJudge,
    create_temporal_match_judge_from_effective,
)
from app.llm.temporal_signal_extractor import (
    TemporalSignalExtractor,
    create_temporal_signal_extractor_from_effective,
)
from app.services.calendar_event_query import (
    WEEK_CALENDAR_PROVIDERS,
    active_event_predicates,
    event_overlaps_window,
)
from app.services.correlation_constants import SEMANTIC_SUMMARY_METADATA_KEY
from app.services.edge_dedup import has_equivalent_relation
from app.services.effective_user_settings_service import EffectiveUserSettingsService
from app.services.graph_service import GraphService
from app.services.job_queue_service import JobQueueService
from app.services.personal_relevance_evidence_service import PersonalRelevanceEvidenceService
from app.services.provenance import (
    OBSERVED_STATE,
    REJECTED_STATE,
    SYSTEM_ORIGIN,
)
from app.services.temporal_signals_constants import (
    METADATA_END_PRECISION,
    METADATA_EVIDENCE_COUNT,
    METADATA_EXTRACTION_CONFIDENCE,
    METADATA_EXTRACTOR_VERSION,
    METADATA_LIFECYCLE,
    METADATA_PARTICIPATION,
    METADATA_PRIMARY_EVIDENCE_KIND,
    METADATA_PRIMARY_EVIDENCE_OBJECT_ID,
    METADATA_PRIMARY_EVIDENCE_PROVIDER,
    METADATA_SEMANTIC_SUBJECT,
    METADATA_SOURCE_REFERENCE_AT,
    METADATA_SOURCE_SIGNATURE,
    METADATA_START_PRECISION,
    METADATA_SUPERSEDED_BY_OBJECT_ID,
    METADATA_TEMPORAL_SIGNAL_VERSION,
    TEMPORAL_ELIGIBLE_KINDS,
    TEMPORAL_ELIGIBLE_ORIGINS,
    TEMPORAL_ELIGIBLE_PROVIDERS,
    TEMPORAL_SIGNAL_CANDIDATE_WINDOW,
    TEMPORAL_SIGNAL_EXPECTED_MIN_CONFIDENCE,
    TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
    TEMPORAL_SIGNAL_MATCH_MIN_CONFIDENCE,
    TEMPORAL_SIGNAL_MAX_BODY_CHARS,
    TEMPORAL_SIGNAL_MAX_CANDIDATES,
    TEMPORAL_SIGNAL_MAX_PENDING_PER_USER,
    TEMPORAL_SIGNAL_MAX_TITLE_CHARS,
    TEMPORAL_SIGNAL_METADATA_VERSION,
    TEMPORAL_SIGNAL_POSSIBLE_MIN_CONFIDENCE,
    TEMPORAL_SIGNAL_START_PROXIMITY,
    TEMPORAL_SIGNALS_ENABLED_DEFAULT,
)
from app.services.temporal_signals_models import (
    ResolvedTemporalSignal,
    TemporalExtractionRequest,
    TemporalMatchCandidate,
)
from app.services.temporal_signals_resolution import (
    resolve_exact_signal,
    source_reference_timestamp,
)
from app.services.user_participation_evidence_service import extract_email_address
from app.services.user_serialization_gate import lock_user_serialization_row
from app.source_sync.constants import SOURCE_MATTERMOST


@dataclass(frozen=True)
class TemporalSignalJobOutcome:
    reason: str
    hint_id: UUID | None = None
    calendar_id: UUID | None = None
    stale: bool = False


def is_temporal_signals_enabled(session: Session, user_id: UUID) -> bool:
    row = session.get(UserSettings, user_id)
    if row is None:
        return TEMPORAL_SIGNALS_ENABLED_DEFAULT
    return bool(row.temporal_signals_enabled)


def acquire_temporal_signals_user_gate(session: Session, user_id: UUID) -> UserSettings | None:
    user = lock_user_serialization_row(session, user_id)
    if user is None:
        return None
    return session.scalar(
        select(UserSettings)
        .where(UserSettings.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def object_is_temporal_source_eligible(obj: Object) -> bool:
    if is_object_hidden_from_active_reads(obj) or obj.state == REJECTED_STATE:
        return False
    if obj.kind not in TEMPORAL_ELIGIBLE_KINDS:
        return False
    if obj.provider not in TEMPORAL_ELIGIBLE_PROVIDERS:
        return False
    if obj.origin not in TEMPORAL_ELIGIBLE_ORIGINS:
        return False
    if obj.kind == KIND_TEMPORAL_HINT:
        return False
    return not _is_self_only_outgoing(obj)


def object_is_calendar_reconcile_eligible(obj: Object) -> bool:
    if is_object_hidden_from_active_reads(obj) or obj.state == REJECTED_STATE:
        return False
    return obj.kind == "event" and obj.provider in WEEK_CALENDAR_PROVIDERS and obj.start_at is not None


def _is_self_only_outgoing(obj: Object) -> bool:
    metadata = obj.metadata_ or {}
    if obj.provider in {"gmail", "yandex_mail"}:
        sender = extract_email_address(metadata.get("sender"))
        recipients = _string_values(metadata.get("recipients"))
        copied = _string_values(metadata.get("cc"))
        others = [
            extract_email_address(item)
            for item in (*recipients, *copied)
        ]
        other_emails = {item for item in others if item and item != sender}
        return bool(sender) and not other_emails
    return False


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bounded_source_text(obj: Object) -> tuple[str, str]:
    title = (obj.title or "")[:TEMPORAL_SIGNAL_MAX_TITLE_CHARS]
    summary = (obj.metadata_ or {}).get(SEMANTIC_SUMMARY_METADATA_KEY)
    if isinstance(summary, str) and summary.strip():
        body = summary.strip()[:TEMPORAL_SIGNAL_MAX_BODY_CHARS]
    else:
        body = (obj.body or "").strip()[:TEMPORAL_SIGNAL_MAX_BODY_CHARS]
    return title, body


def source_extraction_signature(obj: Object) -> str:
    title, body = bounded_source_text(obj)
    metadata = obj.metadata_ or {}
    reference = source_reference_timestamp(obj.occurred_at, metadata)
    reference_iso = reference.astimezone(UTC).isoformat() if reference is not None else None
    participants = {
        "sender": metadata.get("sender"),
        "recipients": metadata.get("recipients"),
        "cc": metadata.get("cc"),
        "author_user_id": metadata.get("author_user_id"),
        "author_username": metadata.get("author_username"),
        "mentioned_user_ids": metadata.get("mentioned_user_ids"),
        "mentioned_usernames": metadata.get("mentioned_usernames"),
    }
    return _sha256_text(
        _canonical_json(
            {
                "object_id": str(obj.id),
                "kind": obj.kind,
                "provider": obj.provider,
                "title": title,
                "body": body,
                "occurred_at": reference_iso,
                "participants": participants,
                "extractor_version": TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
            }
        )
    )


def calendar_event_signature(obj: Object) -> str:
    return _sha256_text(
        _canonical_json(
            {
                "object_id": str(obj.id),
                "title": obj.title,
                "start_at": obj.start_at.isoformat() if obj.start_at else None,
                "due_at": obj.due_at.isoformat() if obj.due_at else None,
                "provider": obj.provider,
            }
        )
    )


def hint_is_unresolved(obj: Object) -> bool:
    if obj.kind != KIND_TEMPORAL_HINT:
        return False
    if is_object_hidden_from_active_reads(obj) or obj.state == REJECTED_STATE:
        return False
    lifecycle = (obj.metadata_ or {}).get(METADATA_LIFECYCLE, LIFECYCLE_UNRESOLVED)
    return lifecycle == LIFECYCLE_UNRESOLVED


def enqueue_extract_temporal_signal(
    session: Session,
    object_id: UUID,
    user_id: UUID,
    *,
    parent_trace_id: UUID | str | None = None,
    already_gated: bool = False,
) -> None:
    if not already_gated:
        settings = acquire_temporal_signals_user_gate(session, user_id)
        if settings is None or not bool(settings.temporal_signals_enabled):
            return
    elif not is_temporal_signals_enabled(session, user_id):
        return
    obj = session.scalar(select(Object).where(Object.id == object_id, Object.user_id == user_id))
    if obj is None or not object_is_temporal_source_eligible(obj):
        return
    signature = source_extraction_signature(obj)
    extra = {
        "source_signature": signature,
        "extractor_version": TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
    }
    if _has_signature_job(
        session, user_id, JOB_TYPE_EXTRACT_TEMPORAL_SIGNAL, object_id, extra
    ):
        return
    if _pending_or_running_count(session, user_id, JOB_TYPE_EXTRACT_TEMPORAL_SIGNAL) >= (
        TEMPORAL_SIGNAL_MAX_PENDING_PER_USER
    ):
        return
    payload: dict = {
        "object_id": str(object_id),
        "source_signature": signature,
        "extractor_version": TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
    }
    parent = _parent_trace_id(parent_trace_id)
    if parent is not None:
        payload["parent_trace_id"] = parent
    JobQueueService(session).enqueue(
        JOB_TYPE_EXTRACT_TEMPORAL_SIGNAL,
        payload,
        user_id=user_id,
    )


def enqueue_reconcile_temporal_hints(
    session: Session,
    object_id: UUID,
    user_id: UUID,
    *,
    parent_trace_id: UUID | str | None = None,
    already_gated: bool = False,
) -> None:
    if not already_gated:
        settings = acquire_temporal_signals_user_gate(session, user_id)
        if settings is None or not bool(settings.temporal_signals_enabled):
            return
    elif not is_temporal_signals_enabled(session, user_id):
        return
    obj = session.scalar(select(Object).where(Object.id == object_id, Object.user_id == user_id))
    if obj is None or not object_is_calendar_reconcile_eligible(obj):
        return
    signature = calendar_event_signature(obj)
    extra = {"event_signature": signature}
    if _has_signature_job(
        session, user_id, JOB_TYPE_RECONCILE_TEMPORAL_HINTS, object_id, extra
    ):
        return
    payload: dict = {"object_id": str(object_id), "event_signature": signature}
    parent = _parent_trace_id(parent_trace_id)
    if parent is not None:
        payload["parent_trace_id"] = parent
    JobQueueService(session).enqueue(
        JOB_TYPE_RECONCILE_TEMPORAL_HINTS,
        payload,
        user_id=user_id,
    )


def _parent_trace_id(parent_trace_id: UUID | str | None) -> str | None:
    if parent_trace_id is not None:
        return str(parent_trace_id)
    active = get_active_trace()
    if active is None:
        return None
    return str(active.trace_id)


def _has_signature_job(
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
            Job.status.in_((JOB_STATUS_PENDING, JOB_STATUS_RUNNING, JOB_STATUS_DONE)),
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


def _pending_or_running_count(session: Session, user_id: UUID, job_type: str) -> int:
    return len(
        list(
            session.scalars(
                select(Job.id).where(
                    Job.user_id == user_id,
                    Job.type == job_type,
                    Job.status.in_((JOB_STATUS_PENDING, JOB_STATUS_RUNNING)),
                )
            )
        )
    )


class TemporalSignalService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        *,
        extractor: TemporalSignalExtractor | None = None,
        match_judge: TemporalMatchJudge | None = None,
        after_extract: Callable[[], None] | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._extractor = extractor
        self._match_judge = match_judge
        self._after_extract = after_extract
        self._graph = GraphService(session, user_id)

    def run_extract_job(self, payload: dict) -> TemporalSignalJobOutcome:
        object_id = UUID(str(payload["object_id"]))
        payload_sig = str(payload.get("source_signature") or "")
        if not is_temporal_signals_enabled(self._session, self._user_id):
            return TemporalSignalJobOutcome(reason="disabled")
        source = self._load_source(object_id)
        if source is None or not object_is_temporal_source_eligible(source):
            return TemporalSignalJobOutcome(reason="ineligible")
        live_sig = source_extraction_signature(source)
        if live_sig != payload_sig:
            enqueue_extract_temporal_signal(self._session, object_id, self._user_id)
            return TemporalSignalJobOutcome(reason="stale_before_model", stale=True)
        parent_raw = payload.get("parent_trace_id")
        parent_trace_id = UUID(str(parent_raw)) if parent_raw else None
        with ai_trace_session(
            self._user_id,
            WORKLOAD_BACKGROUND_TEMPORAL_SIGNAL,
            object_id=object_id,
            parent_trace_id=parent_trace_id,
        ):
            outcome = self._extract_and_persist(source, payload_sig)
            self._record_result(source.id, outcome)
            return outcome

    def run_reconcile_job(self, payload: dict) -> TemporalSignalJobOutcome:
        object_id = UUID(str(payload["object_id"]))
        if not is_temporal_signals_enabled(self._session, self._user_id):
            return TemporalSignalJobOutcome(reason="disabled")
        event = self._load_source(object_id)
        if event is None or not object_is_calendar_reconcile_eligible(event):
            return TemporalSignalJobOutcome(reason="ineligible")
        parent_raw = payload.get("parent_trace_id")
        parent_trace_id = UUID(str(parent_raw)) if parent_raw else None
        with ai_trace_session(
            self._user_id,
            WORKLOAD_BACKGROUND_TEMPORAL_SIGNAL,
            object_id=object_id,
            parent_trace_id=parent_trace_id,
        ):
            outcome = self._reconcile_calendar_event(event)
            self._record_result(event.id, outcome)
            return outcome

    def _extract_and_persist(self, source: Object, payload_sig: str) -> TemporalSignalJobOutcome:
        request = self._build_request(source)
        extractor = self._extractor or create_temporal_signal_extractor_from_effective(
            EffectiveUserSettingsService.build(self._session).get_effective_settings(
                self._user_id
            )
        )
        extraction = extractor.extract(request)
        if self._after_extract is not None:
            self._after_extract()
        fenced = self._post_model_fence(source.id, payload_sig)
        if fenced is None:
            return TemporalSignalJobOutcome(reason="stale_after_model", stale=True)
        source = fenced
        if extraction.result_class != RESULT_EXACT_TEMPORAL_SIGNAL or extraction.exact is None:
            return TemporalSignalJobOutcome(
                reason=extraction.reject_reason or extraction.result_class
            )
        timezone = EffectiveUserSettingsService.build(self._session).get_settings_view(
            self._user_id
        ).timezone
        reference = source_reference_timestamp(source.occurred_at, source.metadata_ or {})
        resolved, reason = resolve_exact_signal(
            extraction.exact,
            timezone_name=timezone,
            source_reference_at=reference,
        )
        if resolved is None:
            return TemporalSignalJobOutcome(reason=reason or "unresolved_datetime")
        participation = self._effective_participation(
            resolved.participation,
            resolved.extraction_confidence,
            request.participation_roles,
            request.is_channel_message,
            request.has_other_participants,
        )
        if participation in {PARTICIPATION_OTHERS_ONLY, PARTICIPATION_UNKNOWN}:
            return TemporalSignalJobOutcome(reason=f"participation_{participation}")
        resolved = ResolvedTemporalSignal(
            title=resolved.title,
            start_at=resolved.start_at,
            due_at=resolved.due_at,
            end_precision=resolved.end_precision,
            participation=participation,
            extraction_confidence=resolved.extraction_confidence,
            semantic_subject=resolved.semantic_subject,
            source_reference_at=resolved.source_reference_at,
        )
        existing_anchor = self._existing_evidence_anchor(source.id)
        if existing_anchor is not None:
            return TemporalSignalJobOutcome(
                reason="already_evidenced",
                hint_id=existing_anchor.id if existing_anchor.kind == KIND_TEMPORAL_HINT else None,
                calendar_id=existing_anchor.id if existing_anchor.kind == "event" else None,
            )
        calendar = self._match_calendar(resolved)
        if calendar is not None:
            self._attach_evidence(calendar, source, resolved.extraction_confidence)
            return TemporalSignalJobOutcome(
                reason="calendar_first_match",
                calendar_id=calendar.id,
            )
        hint = self._match_hint(resolved)
        if hint is not None:
            self._attach_evidence(hint, source, resolved.extraction_confidence)
            self._bump_evidence_count(hint)
            return TemporalSignalJobOutcome(reason="hint_merged", hint_id=hint.id)
        created = self._create_hint(resolved, source, payload_sig)
        return TemporalSignalJobOutcome(reason="hint_created", hint_id=created.id)

    def _reconcile_calendar_event(self, event: Object) -> TemporalSignalJobOutcome:
        unresolved = self._unresolved_hints_near(event.start_at, event.due_at)
        if not unresolved:
            return TemporalSignalJobOutcome(reason="no_hints", calendar_id=event.id)
        candidates = [self._candidate_from_object(item) for item in unresolved]
        judge = self._match_judge or create_temporal_match_judge_from_effective(
            EffectiveUserSettingsService.build(self._session).get_effective_settings(
                self._user_id
            )
        )
        result = judge.judge(
            trigger_title=event.title or "",
            trigger_subject=self._content_summary(event),
            trigger_kind="event",
            candidates=candidates,
        )
        allowed = {item.object_id for item in candidates}
        decision = result.decision
        if (
            decision is None
            or decision.target_object_id not in allowed
            or decision.confidence < TEMPORAL_SIGNAL_MATCH_MIN_CONFIDENCE
            or not _finite_score(decision.confidence)
        ):
            return TemporalSignalJobOutcome(reason="no_semantic_match", calendar_id=event.id)
        hint = self._load_source(decision.target_object_id)
        if hint is None or not hint_is_unresolved(hint):
            return TemporalSignalJobOutcome(reason="hint_gone", calendar_id=event.id)
        self._suppress_hint(hint, event)
        for evidence in self._evidence_sources(hint):
            self._attach_evidence(event, evidence, decision.confidence)
        return TemporalSignalJobOutcome(
            reason="hint_superseded",
            hint_id=hint.id,
            calendar_id=event.id,
        )

    def _match_calendar(self, resolved: ResolvedTemporalSignal) -> Object | None:
        events = self._calendar_candidates(resolved.start_at, resolved.due_at)
        return self._judge_match(
            resolved,
            events,
            trigger_kind=KIND_TEMPORAL_HINT,
        )

    def _match_hint(self, resolved: ResolvedTemporalSignal) -> Object | None:
        hints = self._unresolved_hints_near(resolved.start_at, resolved.due_at)
        return self._judge_match(
            resolved,
            hints,
            trigger_kind=KIND_TEMPORAL_HINT,
        )

    def _judge_match(
        self,
        resolved: ResolvedTemporalSignal,
        objects: list[Object],
        *,
        trigger_kind: str,
    ) -> Object | None:
        if not objects:
            return None
        candidates = [self._candidate_from_object(item) for item in objects]
        judge = self._match_judge or create_temporal_match_judge_from_effective(
            EffectiveUserSettingsService.build(self._session).get_effective_settings(
                self._user_id
            )
        )
        result = judge.judge(
            trigger_title=resolved.title,
            trigger_subject=resolved.semantic_subject,
            trigger_kind=trigger_kind,
            candidates=candidates,
        )
        allowed = {item.object_id for item in candidates}
        decision = result.decision
        if (
            decision is None
            or decision.target_object_id not in allowed
            or decision.confidence < TEMPORAL_SIGNAL_MATCH_MIN_CONFIDENCE
            or not _finite_score(decision.confidence)
        ):
            return None
        return next(item for item in objects if item.id == decision.target_object_id)

    def _calendar_candidates(self, start_at: datetime, due_at: datetime | None) -> list[Object]:
        window_start = start_at - TEMPORAL_SIGNAL_CANDIDATE_WINDOW
        window_end = (due_at or start_at) + TEMPORAL_SIGNAL_CANDIDATE_WINDOW
        rows = list(
            self._session.scalars(
                select(Object)
                .where(
                    *active_event_predicates(self._user_id),
                    Object.provider.in_(WEEK_CALENDAR_PROVIDERS),
                    event_overlaps_window(window_start, window_end),
                )
                .order_by(Object.start_at.asc(), Object.id.asc())
                .limit(TEMPORAL_SIGNAL_MAX_CANDIDATES)
            )
        )
        return [row for row in rows if _temporally_compatible(start_at, due_at, row.start_at, row.due_at)]

    def _unresolved_hints_near(self, start_at: datetime | None, due_at: datetime | None) -> list[Object]:
        if start_at is None:
            return []
        window_start = start_at - TEMPORAL_SIGNAL_CANDIDATE_WINDOW
        window_end = (due_at or start_at) + TEMPORAL_SIGNAL_CANDIDATE_WINDOW
        rows = list(
            self._session.scalars(
                select(Object)
                .where(
                    Object.user_id == self._user_id,
                    Object.kind == KIND_TEMPORAL_HINT,
                    Object.state != REJECTED_STATE,
                    Object.deleted_at.is_(None),
                    Object.start_at.is_not(None),
                    event_overlaps_window(window_start, window_end),
                )
                .order_by(Object.start_at.asc(), Object.id.asc())
                .limit(TEMPORAL_SIGNAL_MAX_CANDIDATES)
            )
        )
        return [
            row
            for row in rows
            if hint_is_unresolved(row)
            and _temporally_compatible(start_at, due_at, row.start_at, row.due_at)
        ]

    def _create_hint(
        self,
        resolved: ResolvedTemporalSignal,
        source: Object,
        source_signature: str,
    ) -> Object:
        metadata = {
            METADATA_TEMPORAL_SIGNAL_VERSION: TEMPORAL_SIGNAL_METADATA_VERSION,
            METADATA_START_PRECISION: START_PRECISION_EXACT,
            METADATA_END_PRECISION: resolved.end_precision,
            METADATA_PARTICIPATION: resolved.participation,
            METADATA_PRIMARY_EVIDENCE_OBJECT_ID: str(source.id),
            METADATA_PRIMARY_EVIDENCE_PROVIDER: source.provider,
            METADATA_PRIMARY_EVIDENCE_KIND: source.kind,
            METADATA_EVIDENCE_COUNT: 1,
            METADATA_EXTRACTION_CONFIDENCE: resolved.extraction_confidence,
            METADATA_SOURCE_REFERENCE_AT: resolved.source_reference_at.isoformat(),
            METADATA_SOURCE_SIGNATURE: source_signature,
            METADATA_EXTRACTOR_VERSION: TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
            METADATA_LIFECYCLE: LIFECYCLE_UNRESOLVED,
        }
        if resolved.semantic_subject:
            metadata[METADATA_SEMANTIC_SUBJECT] = resolved.semantic_subject
        hint = self._graph.create_object(
            ObjectCreate(
                kind=KIND_TEMPORAL_HINT,
                title=resolved.title,
                origin=SYSTEM_ORIGIN,
                state=OBSERVED_STATE,
                start_at=resolved.start_at,
                due_at=resolved.due_at,
                metadata=metadata,
                confidence=resolved.extraction_confidence,
            )
        )
        self._attach_evidence(hint, source, resolved.extraction_confidence)
        return hint

    def _attach_evidence(self, anchor: Object, source: Object, confidence: float) -> None:
        if has_equivalent_relation(
            self._session,
            self._user_id,
            anchor.id,
            source.id,
            EDGE_TYPE_TEMPORAL_EVIDENCE,
        ):
            return
        self._graph.create_edge(
            EdgeCreate(
                source_id=anchor.id,
                target_id=source.id,
                type=EDGE_TYPE_TEMPORAL_EVIDENCE,
                origin=SYSTEM_ORIGIN,
                state=OBSERVED_STATE,
                confidence=confidence,
                metadata={
                    METADATA_EXTRACTOR_VERSION: TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
                },
            )
        )

    def _bump_evidence_count(self, hint: Object) -> None:
        metadata = dict(hint.metadata_ or {})
        count = int(metadata.get(METADATA_EVIDENCE_COUNT) or 1) + 1
        metadata[METADATA_EVIDENCE_COUNT] = count
        hint.metadata_ = metadata
        self._session.flush()

    def _suppress_hint(self, hint: Object, calendar: Object) -> None:
        if not has_equivalent_relation(
            self._session,
            self._user_id,
            hint.id,
            calendar.id,
            EDGE_TYPE_TEMPORAL_CONFIRMATION,
        ):
            self._graph.create_edge(
                EdgeCreate(
                    source_id=hint.id,
                    target_id=calendar.id,
                    type=EDGE_TYPE_TEMPORAL_CONFIRMATION,
                    origin=SYSTEM_ORIGIN,
                    state=OBSERVED_STATE,
                    metadata={
                        METADATA_LIFECYCLE: LIFECYCLE_SUPERSEDED_BY_CALENDAR,
                    },
                )
            )
        metadata = dict(hint.metadata_ or {})
        metadata[METADATA_LIFECYCLE] = LIFECYCLE_SUPERSEDED_BY_CALENDAR
        metadata[METADATA_SUPERSEDED_BY_OBJECT_ID] = str(calendar.id)
        hint.metadata_ = metadata
        self._session.flush()

    def _evidence_sources(self, hint: Object) -> list[Object]:
        edges = list(
            self._session.scalars(
                select(Edge).where(
                    Edge.user_id == self._user_id,
                    Edge.source_id == hint.id,
                    Edge.type == EDGE_TYPE_TEMPORAL_EVIDENCE,
                    Edge.state != REJECTED_STATE,
                )
            )
        )
        if not edges:
            return []
        ids = [edge.target_id for edge in edges]
        return list(
            self._session.scalars(
                select(Object).where(Object.user_id == self._user_id, Object.id.in_(ids))
            )
        )

    def _existing_evidence_anchor(self, source_id: UUID) -> Object | None:
        edge = self._session.scalar(
            select(Edge).where(
                Edge.user_id == self._user_id,
                Edge.target_id == source_id,
                Edge.type == EDGE_TYPE_TEMPORAL_EVIDENCE,
                Edge.state != REJECTED_STATE,
            ).limit(1)
        )
        if edge is None:
            return None
        return self._load_source(edge.source_id)

    def _build_request(self, source: Object) -> TemporalExtractionRequest:
        title, body = bounded_source_text(source)
        snapshot = PersonalRelevanceEvidenceService.build(self._session).build_snapshot(
            self._user_id,
            [source.id],
        )
        roles: tuple[str, ...] = ()
        if snapshot.objects:
            roles = snapshot.objects[0].user_participation_roles
        metadata = source.metadata_ or {}
        is_channel = source.provider == SOURCE_MATTERMOST and bool(metadata.get("channel_id"))
        has_others = _has_other_participants(source, roles)
        return TemporalExtractionRequest(
            object_id=source.id,
            kind=source.kind,
            provider=source.provider,
            title=title,
            body=body,
            source_reference_at=source_reference_timestamp(source.occurred_at, metadata),
            timezone=EffectiveUserSettingsService.build(self._session).get_settings_view(
                self._user_id
            ).timezone,
            participation_roles=roles,
            is_channel_message=is_channel,
            has_other_participants=has_others,
        )

    def _effective_participation(
        self,
        llm_value: str,
        confidence: float,
        roles: tuple[str, ...],
        is_channel: bool,
        has_others: bool,
    ) -> str:
        directed = bool(
            set(roles)
            & {
                "direct_recipient",
                "copied_recipient",
                "mentioned",
                "organizer",
                "attendee",
                "sender",
                "author",
            }
        )
        if llm_value == PARTICIPATION_OTHERS_ONLY:
            return PARTICIPATION_OTHERS_ONLY
        if not directed and not is_channel:
            return PARTICIPATION_OTHERS_ONLY
        if llm_value == PARTICIPATION_UNKNOWN:
            return PARTICIPATION_UNKNOWN
        if llm_value == PARTICIPATION_POSSIBLE:
            if confidence < TEMPORAL_SIGNAL_POSSIBLE_MIN_CONFIDENCE:
                return PARTICIPATION_UNKNOWN
            return PARTICIPATION_POSSIBLE
        if confidence < TEMPORAL_SIGNAL_EXPECTED_MIN_CONFIDENCE:
            return PARTICIPATION_UNKNOWN
        if directed:
            return PARTICIPATION_EXPECTED
        if is_channel or has_others:
            if confidence >= TEMPORAL_SIGNAL_POSSIBLE_MIN_CONFIDENCE:
                return PARTICIPATION_POSSIBLE
            return PARTICIPATION_UNKNOWN
        return PARTICIPATION_OTHERS_ONLY

    def _post_model_fence(self, object_id: UUID, payload_sig: str) -> Object | None:
        self._session.expire_all()
        settings = acquire_temporal_signals_user_gate(self._session, self._user_id)
        if settings is None or not bool(settings.temporal_signals_enabled):
            return None
        source = self._load_source(object_id)
        if source is None or not object_is_temporal_source_eligible(source):
            return None
        if source_extraction_signature(source) != payload_sig:
            enqueue_extract_temporal_signal(
                self._session,
                object_id,
                self._user_id,
                already_gated=True,
            )
            return None
        return source

    def _load_source(self, object_id: UUID) -> Object | None:
        return self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )

    def _candidate_from_object(self, obj: Object) -> TemporalMatchCandidate:
        return TemporalMatchCandidate(
            object_id=obj.id,
            kind=obj.kind,
            title=obj.title or "",
            start_at=obj.start_at,
            due_at=obj.due_at,
            summary=self._content_summary(obj),
            provider=obj.provider,
        )

    def _content_summary(self, obj: Object) -> str:
        summary = (obj.metadata_ or {}).get(SEMANTIC_SUMMARY_METADATA_KEY)
        if isinstance(summary, str) and summary.strip():
            return summary.strip()[:500]
        if obj.body and obj.body.strip():
            return obj.body.strip()[:500]
        return (obj.title or "")[:500]

    def _record_result(self, source_id: UUID, outcome: TemporalSignalJobOutcome) -> None:
        active = get_active_trace()
        if active is None:
            return
        active.record_event(
            "temporal_signal_result",
            {
                "source_object_id": str(source_id),
                "extractor_version": TEMPORAL_SIGNAL_EXTRACTOR_VERSION,
                "result_class": outcome.reason,
                "accepted_rejected_reason": outcome.reason,
                "chosen_calendar_id": str(outcome.calendar_id) if outcome.calendar_id else None,
                "chosen_hint_id": str(outcome.hint_id) if outcome.hint_id else None,
                "stale": outcome.stale,
            },
        )


def _finite_score(value: float) -> bool:
    return math.isfinite(value) and 0.0 <= value <= 1.0


def _temporally_compatible(
    left_start: datetime | None,
    left_end: datetime | None,
    right_start: datetime | None,
    right_end: datetime | None,
) -> bool:
    if left_start is None or right_start is None:
        return False
    if abs(left_start - right_start) <= TEMPORAL_SIGNAL_START_PROXIMITY:
        return True
    if left_end is None and right_end is not None:
        return right_start <= left_start < right_end
    if right_end is None and left_end is not None:
        return left_start <= right_start < left_end
    if left_end is not None and right_end is not None:
        return left_start < right_end and right_start < left_end
    return False


def _has_other_participants(obj: Object, roles: tuple[str, ...]) -> bool:
    metadata = obj.metadata_ or {}
    if _string_values(metadata.get("recipients")) or _string_values(metadata.get("cc")):
        return True
    if metadata.get("mentioned_user_ids") or metadata.get("mentioned_usernames"):
        return True
    author = metadata.get("author_user_id") or metadata.get("author_username")
    if author and "author" not in roles:
        return True
    sender = extract_email_address(metadata.get("sender"))
    return bool(sender) and "sender" not in roles

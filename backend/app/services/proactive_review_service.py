from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.ai_audit.constants import WORKLOAD_BACKGROUND_PROACTIVE_REVIEW
from app.ai_audit.context import ai_trace_session, get_current_job_id
from app.core.assistant_openai_config import AssistantOpenAIConfigError
from app.db.models import Edge, Notification, Object
from app.domain.object_visibility import is_object_hidden_from_active_reads, object_is_active
from app.domain.scheduled_activity import KIND_SCHEDULED_ACTIVITY
from app.domain.task_lifecycle import TASK_STATUS_IN_PROGRESS, TASK_STATUS_OPEN
from app.jobs.constants import JOB_TYPE_PROACTIVE_REVIEW
from app.llm.openai_assistant_provider import OpenAIAssistantProvider
from app.notifications.constants import (
    NOTIFICATION_STATUS_NEW,
    NOTIFICATION_STATUS_READ,
)
from app.proactive.constants import (
    NOTIFICATION_KIND_INSIGHT,
    NOTIFICATION_KIND_TASK_PROPOSAL,
    PROACTIVE_EVENT_HORIZON,
    PROACTIVE_EVENT_KINDS,
    PROACTIVE_GATE_ORIGINS,
    PROACTIVE_MAX_OUTPUT_TOKENS,
    PROACTIVE_MAX_ROUNDS,
    PROACTIVE_MAX_UNRESOLVED,
    PROACTIVE_MIN_CONFIDENCE,
    PROACTIVE_SEED_OBJECT_LIMIT,
    PROACTIVE_SIGNATURE_COOLDOWN,
    PROACTIVE_SIGNATURE_VERSION,
    PROACTIVE_TASK_HORIZON,
    PROACTIVE_TASK_LOOKBACK,
    PROPOSAL_TYPE_PROACTIVE_INSIGHT,
    PROPOSAL_TYPE_TASK,
)
from app.proactive.control import read_proactive_control
from app.proactive.decision import ProactiveDecision, ProactiveNotificationPayload
from app.proactive.instructions import PROACTIVE_SYSTEM_INSTRUCTIONS
from app.proactive.tool_runner import ProactiveToolRunner
from app.services.background_ai_errors import BackgroundAIConfigurationError
from app.services.domain_tool_service import DomainToolService
from app.services.effective_user_settings_service import (
    EffectiveUserSettings,
    EffectiveUserSettingsService,
)
from app.services.job_queue_service import JobQueueService, utcnow
from app.services.notification_service import NotificationService
from app.services.provenance import CONFIRMED_STATE, REJECTED_STATE
from app.tools.registry import PROACTIVE_TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

_UNRESOLVED_STATUSES = (NOTIFICATION_STATUS_NEW, NOTIFICATION_STATUS_READ)
_REFERENCES_EDGE = "references"


def create_proactive_provider(effective: EffectiveUserSettings) -> OpenAIAssistantProvider:
    if not effective.openai_api_key:
        raise BackgroundAIConfigurationError("OpenAI API key is not configured")
    return OpenAIAssistantProvider(
        api_key=effective.openai_api_key,
        model=effective.assistant_model,
        reasoning_effort=effective.assistant_reasoning_effort,
        verbosity=effective.assistant_verbosity,
        max_output_tokens=PROACTIVE_MAX_OUTPUT_TOKENS,
        max_rounds=PROACTIVE_MAX_ROUNDS,
    )


def parse_aware_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=UTC)
        return value
    text = str(value).strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))  # noqa: FURB162
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def is_proactive_proposal(proposal: dict | None) -> bool:
    if not isinstance(proposal, dict):
        return False
    if proposal.get("proactive") is True:
        return True
    if proposal.get("type") == PROPOSAL_TYPE_PROACTIVE_INSIGHT:
        return True
    return bool(proposal.get("proactive_signature"))


def compute_proactive_signature(
    *,
    kind: str,
    source: Object,
    related: Object | None,
    task_due_at: datetime | None,
    task_start_at: datetime | None,
) -> str:
    updated = parse_aware_datetime(source.updated_at) or utcnow()
    parts = [
        f"v{PROACTIVE_SIGNATURE_VERSION}",
        kind,
        str(source.id),
        updated.isoformat(),
        str(related.id) if related is not None else "",
        task_due_at.isoformat() if task_due_at is not None else "",
        task_start_at.isoformat() if task_start_at is not None else "",
    ]
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return digest


def _proactive_proposal_sql():
    proposal = Notification.proposal_
    signature = proposal["proactive_signature"].as_string()
    return or_(
        proposal["proactive"].as_boolean().is_(True),
        proposal["type"].as_string() == PROPOSAL_TYPE_PROACTIVE_INSIGHT,
        and_(signature.is_not(None), signature != ""),
    )


class ProactiveReviewService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._queue = JobQueueService(session)
        self._notifications = NotificationService(session, user_id)
        self._settings_service = EffectiveUserSettingsService.build(session)

    def run(self, payload: dict) -> None:
        control = read_proactive_control(self._session, self._user_id, for_update=False)
        if not control.enabled:
            return
        now = utcnow()
        window_start = parse_aware_datetime(payload.get("window_start"))
        if window_start is None:
            window_start = now - timedelta(minutes=control.interval_minutes)
        window_end = now
        if self._unresolved_proactive_count() >= PROACTIVE_MAX_UNRESOLVED:
            self._commit_quiet_successor(window_end)
            return
        seed_objects = self._gate_seed_objects(window_start, window_end, now)
        if not seed_objects:
            self._commit_quiet_successor(window_end)
            return
        if not read_proactive_control(self._session, self._user_id, for_update=False).enabled:
            return
        effective = self._load_effective()
        decision, runner = self._run_llm(effective, seed_objects, window_start, window_end)
        locked = read_proactive_control(self._session, self._user_id, for_update=True)
        if not locked.enabled:
            return
        if runner is not None and runner.has_rejected_tool_attempt:
            decision = None
        else:
            self._maybe_notify(decision)
        self._enqueue_successor(window_end, locked.interval_minutes)

    def _commit_quiet_successor(self, window_end: datetime) -> None:
        locked = read_proactive_control(self._session, self._user_id, for_update=True)
        if not locked.enabled:
            return
        self._enqueue_successor(window_end, locked.interval_minutes)

    def _load_effective(self) -> EffectiveUserSettings:
        try:
            return self._settings_service.get_effective_settings(self._user_id)
        except AssistantOpenAIConfigError as exc:
            raise BackgroundAIConfigurationError(str(exc)) from exc

    def _enqueue_successor(self, window_end: datetime, interval_minutes: int) -> None:
        self._queue.enqueue(
            JOB_TYPE_PROACTIVE_REVIEW,
            {"window_start": window_end.isoformat()},
            self._user_id,
            run_after=window_end + timedelta(minutes=interval_minutes),
        )

    def _unresolved_proactive_count(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == self._user_id,
                    Notification.status.in_(_UNRESOLVED_STATUSES),
                    _proactive_proposal_sql(),
                )
            )
            or 0
        )

    def _gate_seed_objects(
        self,
        window_start: datetime,
        window_end: datetime,
        now: datetime,
    ) -> list[Object]:
        found: dict[UUID, Object] = {}
        for obj in self._recent_activity(window_start, window_end):
            found[obj.id] = obj
        for obj in self._attention_tasks(now):
            found[obj.id] = obj
        for obj in self._upcoming_events(now):
            found[obj.id] = obj
        objects = list(found.values())
        objects.sort(key=lambda item: (item.updated_at, item.id), reverse=True)
        return objects[:PROACTIVE_SEED_OBJECT_LIMIT]

    def _visible_owned(self) -> list:
        return [
            Object.user_id == self._user_id,
            object_is_active(),
            Object.state != REJECTED_STATE,
        ]

    def _recent_activity(self, window_start: datetime, window_end: datetime) -> list[Object]:
        parent_email_id = Object.metadata_["parent_email_id"].as_string()
        child_email_attachment = and_(
            Object.origin == "source",
            Object.kind == "file",
            parent_email_id.is_not(None),
            parent_email_id != "",
        )
        stmt = (
            select(Object)
            .where(
                *self._visible_owned(),
                Object.origin.in_(tuple(PROACTIVE_GATE_ORIGINS)),
                Object.kind != KIND_SCHEDULED_ACTIVITY,
                Object.updated_at > window_start,
                Object.updated_at <= window_end,
                ~child_email_attachment,
            )
            .order_by(Object.updated_at.desc(), Object.id.desc())
            .limit(PROACTIVE_SEED_OBJECT_LIMIT)
        )
        return list(self._session.scalars(stmt))

    def _attention_tasks(self, now: datetime) -> list[Object]:
        start = now - PROACTIVE_TASK_LOOKBACK
        end = now + PROACTIVE_TASK_HORIZON
        stmt = (
            select(Object)
            .where(
                *self._visible_owned(),
                Object.kind == "task",
                Object.status.in_((TASK_STATUS_OPEN, TASK_STATUS_IN_PROGRESS)),
                Object.due_at.is_not(None),
                Object.due_at >= start,
                Object.due_at <= end,
            )
            .order_by(Object.due_at.asc(), Object.id.asc())
            .limit(PROACTIVE_SEED_OBJECT_LIMIT)
        )
        return list(self._session.scalars(stmt))

    def _upcoming_events(self, now: datetime) -> list[Object]:
        end = now + PROACTIVE_EVENT_HORIZON
        stmt = (
            select(Object)
            .where(
                *self._visible_owned(),
                Object.kind.in_(PROACTIVE_EVENT_KINDS),
                Object.start_at.is_not(None),
                Object.start_at > now,
                Object.start_at <= end,
            )
            .order_by(Object.start_at.asc(), Object.id.asc())
            .limit(PROACTIVE_SEED_OBJECT_LIMIT)
        )
        return list(self._session.scalars(stmt))

    def _run_llm(
        self,
        effective: EffectiveUserSettings,
        seed_objects: list[Object],
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[ProactiveDecision | None, ProactiveToolRunner]:
        tools = DomainToolService(
            self._session,
            self._user_id,
            None,
            defer_write_embeddings=True,
            client_timezone=effective.timezone,
        )
        runner = ProactiveToolRunner(
            tools,
            initial_seen_object_ids=[obj.id for obj in seed_objects],
        )
        if not read_proactive_control(self._session, self._user_id, for_update=False).enabled:
            return None, runner
        provider = create_proactive_provider(effective)
        seed_payload = [
            {
                "id": str(obj.id),
                "kind": obj.kind,
                "title": obj.title,
                "status": obj.status,
                "origin": obj.origin,
                "updated_at": parse_aware_datetime(obj.updated_at).isoformat()
                if parse_aware_datetime(obj.updated_at)
                else None,
                "due_at": parse_aware_datetime(obj.due_at).isoformat()
                if parse_aware_datetime(obj.due_at)
                else None,
                "start_at": parse_aware_datetime(obj.start_at).isoformat()
                if parse_aware_datetime(obj.start_at)
                else None,
            }
            for obj in seed_objects
        ]
        message = (
            "Perform a bounded proactive attention review. "
            f"window_start={window_start.isoformat()} "
            f"window_end={window_end.isoformat()}. "
            "Return exact JSON for ProactiveDecision."
        )
        seed_context = json.dumps({"seed_objects": seed_payload}, ensure_ascii=False)
        job_id = get_current_job_id()
        with ai_trace_session(
            self._user_id,
            WORKLOAD_BACKGROUND_PROACTIVE_REVIEW,
            job_id=job_id,
        ):
            result = provider.run(
                message,
                [],
                seed_context,
                window_end,
                effective.timezone,
                runner,
                system_instructions=PROACTIVE_SYSTEM_INSTRUCTIONS,
                tool_definitions=PROACTIVE_TOOL_DEFINITIONS,
            )
        runner.commit_model_visible_outputs()
        parsed = self._parse_decision(result.answer)
        if parsed is None:
            return None, runner
        parsed = self._bind_seen_ids(
            parsed, runner.seen_object_ids | {obj.id for obj in seed_objects}
        )
        return parsed, runner

    def _parse_decision(self, raw: str | None) -> ProactiveDecision | None:
        if not raw or not raw.strip():
            return None
        try:
            payload = json.loads(raw.strip())
            return ProactiveDecision.model_validate(payload)
        except (json.JSONDecodeError, ValueError):
            logger.info("proactive review returned unusable structured output")
            return None

    def _bind_seen_ids(
        self,
        decision: ProactiveDecision,
        seen_ids: set[UUID],
    ) -> ProactiveDecision | None:
        if decision.decision == "none" or decision.notification is None:
            return decision
        notification = decision.notification
        if notification.confidence < PROACTIVE_MIN_CONFIDENCE:
            return None
        source = self._load_visible_object(notification.source_object_id)
        if source is None or source.id not in seen_ids:
            return None
        related = None
        if notification.related_object_id is not None:
            related = self._load_visible_object(notification.related_object_id)
            if related is None or related.id not in seen_ids:
                return None
        if notification.kind == NOTIFICATION_KIND_TASK_PROPOSAL:
            if source.kind == "task":
                return None
            if self._active_task_references(source.id):
                return None
        return decision

    def _load_visible_object(self, object_id: UUID) -> Object | None:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            return None
        if is_object_hidden_from_active_reads(obj) or obj.state == REJECTED_STATE:
            return None
        return obj

    def _active_task_references(self, source_object_id: UUID) -> bool:
        stmt = select(
            exists(
                select(Object.id)
                .join(Edge, Edge.source_id == Object.id)
                .where(
                    Object.user_id == self._user_id,
                    Object.kind == "task",
                    object_is_active(),
                    Object.state == CONFIRMED_STATE,
                    Object.status.in_((TASK_STATUS_OPEN, TASK_STATUS_IN_PROGRESS)),
                    Edge.user_id == self._user_id,
                    Edge.type == _REFERENCES_EDGE,
                    Edge.state == CONFIRMED_STATE,
                    Edge.target_id == source_object_id,
                )
            )
        )
        return bool(self._session.scalar(stmt))

    def _maybe_notify(self, decision: ProactiveDecision | None) -> None:
        if decision is None or decision.decision != "notify" or decision.notification is None:
            return
        payload = decision.notification
        source = self._load_visible_object(payload.source_object_id)
        if source is None:
            return
        related = None
        if payload.related_object_id is not None:
            related = self._load_visible_object(payload.related_object_id)
            if related is None:
                return
        if self._has_unresolved_same_source(source.id):
            return
        task_due = payload.task.due_at if payload.task is not None else None
        task_start = payload.task.start_at if payload.task is not None else None
        signature = compute_proactive_signature(
            kind=payload.kind,
            source=source,
            related=related,
            task_due_at=task_due,
            task_start_at=task_start,
        )
        if self._has_recent_signature(signature):
            return
        proposal = self._build_proposal(payload, signature)
        self._notifications.create(
            title=payload.title,
            body=payload.body,
            priority=payload.priority,
            proposal=proposal,
            source_object_id=source.id,
            related_object_id=related.id if related is not None else None,
        )

    def _has_unresolved_same_source(self, source_object_id: UUID) -> bool:
        stmt = select(
            exists(
                select(Notification.id).where(
                    Notification.user_id == self._user_id,
                    Notification.source_object_id == source_object_id,
                    Notification.status.in_(_UNRESOLVED_STATUSES),
                    _proactive_proposal_sql(),
                )
            )
        )
        return bool(self._session.scalar(stmt))

    def _has_recent_signature(self, signature: str) -> bool:
        cutoff = utcnow() - PROACTIVE_SIGNATURE_COOLDOWN
        stmt = select(
            exists(
                select(Notification.id).where(
                    Notification.user_id == self._user_id,
                    Notification.created_at >= cutoff,
                    Notification.proposal_["proactive_signature"].as_string() == signature,
                )
            )
        )
        return bool(self._session.scalar(stmt))

    def _build_proposal(
        self,
        payload: ProactiveNotificationPayload,
        signature: str,
    ) -> dict:
        if payload.kind == NOTIFICATION_KIND_INSIGHT:
            return {
                "type": PROPOSAL_TYPE_PROACTIVE_INSIGHT,
                "version": PROACTIVE_SIGNATURE_VERSION,
                "confidence": payload.confidence,
                "proactive": True,
                "proactive_signature": signature,
            }
        task = payload.task
        assert task is not None
        proposal: dict = {
            "type": PROPOSAL_TYPE_TASK,
            "title": task.title,
            "description": task.description,
            "confidence": payload.confidence,
            "proactive": True,
            "proactive_signature": signature,
            "version": PROACTIVE_SIGNATURE_VERSION,
        }
        if task.due_at is not None:
            proposal["due_at"] = task.due_at.isoformat()
        if task.start_at is not None:
            proposal["start_at"] = task.start_at.isoformat()
        return proposal

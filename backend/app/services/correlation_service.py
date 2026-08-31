"""Orchestrates bounded correlation runs."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EdgeCreate
from app.db.models import Object
from app.llm.correlation_judge import CorrelationJudge
from app.services.correlation_candidate_service import CorrelationCandidateService
from app.services.correlation_constants import (
    CORRELATION_ALLOWED_TYPES,
    CORRELATION_MAX_PROPOSED_EDGES,
    CORRELATION_MIN_CONFIDENCE,
    CORRELATION_TRIGGER_KINDS,
    CORRELATION_VERSION,
    SEMANTIC_SUMMARY_METADATA_KEY,
)
from app.services.correlation_models import CorrelationCandidate
from app.services.deterministic_relation_service import DeterministicRelationService
from app.services.edge_dedup import has_equivalent_relation, has_rejected_proposal_signature
from app.services.errors import NotFoundError
from app.services.graph_service import GraphService
from app.services.provenance import AGENT_ORIGIN, PROPOSED_STATE


def correlation_signature(trigger_id: UUID, target_id: UUID, relation_type: str) -> str:
    return f"{CORRELATION_VERSION}:{trigger_id}:{target_id}:{relation_type}"


class CorrelationService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        judge: CorrelationJudge,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._judge = judge
        self._graph = GraphService(session, user_id)
        self._candidates = CorrelationCandidateService(session, user_id)
        self._deterministic = DeterministicRelationService(session, user_id)

    def run_correlation(self, trigger_object_id: UUID) -> int:
        trigger = self._session.scalar(
            select(Object).where(
                Object.id == trigger_object_id,
                Object.user_id == self._user_id,
            )
        )
        if trigger is None:
            raise NotFoundError("object", trigger_object_id)
        if trigger.kind not in CORRELATION_TRIGGER_KINDS:
            return 0
        if trigger.state == "rejected":
            return 0

        self._deterministic.apply_source_relations(trigger_object_id)
        candidate_list = self._candidates.collect_candidates(trigger_object_id)
        if not candidate_list:
            return 0

        trigger_summary = _trigger_summary(trigger)
        judge_result = self._judge.judge(
            trigger_title=trigger.title,
            trigger_kind=trigger.kind,
            trigger_summary=trigger_summary,
            candidates=candidate_list,
        )

        created = 0
        for decision in judge_result.decisions:
            if created >= CORRELATION_MAX_PROPOSED_EDGES:
                break
            if decision.confidence < CORRELATION_MIN_CONFIDENCE:
                continue
            if decision.relation_type not in CORRELATION_ALLOWED_TYPES:
                continue
            if decision.target_object_id == trigger_object_id:
                continue
            target = self._session.scalar(
                select(Object).where(
                    Object.id == decision.target_object_id,
                    Object.user_id == self._user_id,
                )
            )
            if target is None or target.state == "rejected":
                continue
            if has_equivalent_relation(
                self._session,
                self._user_id,
                trigger_object_id,
                decision.target_object_id,
                decision.relation_type,
            ):
                continue
            signature = correlation_signature(
                trigger_object_id,
                decision.target_object_id,
                decision.relation_type,
            )
            if has_rejected_proposal_signature(
                self._session,
                self._user_id,
                trigger_object_id,
                decision.target_object_id,
                decision.relation_type,
                signature,
            ):
                continue
            candidate_reasons = _candidate_reasons(
                candidate_list, decision.target_object_id
            )
            meta = {
                "trigger_object_id": str(trigger_object_id),
                "candidate_reasons": candidate_reasons,
                "rationale": decision.rationale,
                "correlation_version": CORRELATION_VERSION,
                "correlation_signature": signature,
            }
            self._graph.create_edge(
                EdgeCreate(
                    source_id=trigger_object_id,
                    target_id=decision.target_object_id,
                    type=decision.relation_type,
                    origin=AGENT_ORIGIN,
                    state=PROPOSED_STATE,
                    confidence=decision.confidence,
                    metadata=meta,
                )
            )
            created += 1
        return created


def _trigger_summary(trigger: Object) -> str:
    meta = trigger.metadata_ or {}
    semantic = meta.get(SEMANTIC_SUMMARY_METADATA_KEY)
    if isinstance(semantic, str) and semantic.strip():
        return semantic.strip()[:500]
    if trigger.body:
        return trigger.body[:500]
    return trigger.title


def _candidate_reasons(
    candidates: list[CorrelationCandidate],
    target_id: UUID,
) -> list[str]:
    for candidate in candidates:
        if candidate.object_id == target_id:
            return list(candidate.reasons)
    return []

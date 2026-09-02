"""Structured-output correlation judge."""

import json
import logging
from typing import Protocol
from uuid import UUID

from app.services.background_ai_errors import BackgroundAIConfigurationError
from app.services.correlation_constants import CORRELATION_ALLOWED_TYPES
from app.services.correlation_models import (
    CorrelationCandidate,
    CorrelationDecision,
    CorrelationJudgeResult,
)
from app.services.effective_user_settings_service import EffectiveUserSettings

logger = logging.getLogger(__name__)


class CorrelationJudge(Protocol):
    def judge(
        self,
        trigger_title: str,
        trigger_kind: str,
        trigger_summary: str,
        candidates: list[CorrelationCandidate],
    ) -> CorrelationJudgeResult: ...


class FakeCorrelationJudge:
    """Deterministic judge for tests."""

    def __init__(
        self,
        decisions: list[CorrelationDecision] | None = None,
        invented_uuid: UUID | None = None,
    ) -> None:
        self._decisions = decisions or []
        self._invented_uuid = invented_uuid

    def judge(
        self,
        trigger_title: str,
        trigger_kind: str,
        trigger_summary: str,
        candidates: list[CorrelationCandidate],
    ) -> CorrelationJudgeResult:
        allowed_ids = {candidate.object_id for candidate in candidates}
        filtered: list[CorrelationDecision] = []
        for decision in self._decisions:
            if decision.target_object_id not in allowed_ids:
                continue
            if decision.relation_type not in CORRELATION_ALLOWED_TYPES:
                continue
            filtered.append(decision)
        if self._invented_uuid is not None and self._invented_uuid not in allowed_ids:
            filtered.append(
                CorrelationDecision(
                    target_object_id=self._invented_uuid,
                    relation_type="related_to",
                    confidence=0.95,
                    rationale="invented",
                )
            )
        return CorrelationJudgeResult(decisions=tuple(filtered))


class OpenAICorrelationJudge:
    def __init__(
        self,
        api_key: str,
        model: str,
        reasoning_effort: str = "low",
        verbosity: str = "low",
        max_output_tokens: int = 800,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._verbosity = verbosity
        self._max_output_tokens = max_output_tokens

    def judge(
        self,
        trigger_title: str,
        trigger_kind: str,
        trigger_summary: str,
        candidates: list[CorrelationCandidate],
    ) -> CorrelationJudgeResult:
        if not candidates:
            return CorrelationJudgeResult()

        candidate_payload = [
            {
                "object_id": str(candidate.object_id),
                "kind": candidate.kind,
                "title": candidate.title,
                "primary_date": candidate.primary_date,
                "summary": candidate.content_summary,
                "reasons": list(candidate.reasons),
                "existing_relation": candidate.existing_relation,
            }
            for candidate in candidates
        ]
        instructions = (
            "You judge whether candidate objects correlate with a trigger object. "
            "Return JSON only: {\"decisions\":[{\"target_object_id\":\"...\","
            "\"relation_type\":\"related_to|references\",\"confidence\":0.0-1.0,"
            "\"rationale\":\"short Russian explanation\"}]}. "
            "Only use candidate object_ids from the supplied list. "
            "Allowed relation types: related_to, references. "
            "Rationale must be a short user-auditable sentence in Russian, no chain-of-thought."
        )
        user_content = json.dumps(
            {
                "trigger": {
                    "kind": trigger_kind,
                    "title": trigger_title,
                    "summary": trigger_summary,
                },
                "candidates": candidate_payload,
            },
            ensure_ascii=False,
        )
        response = self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=user_content,
            reasoning={"effort": self._reasoning_effort},
            text={"verbosity": self._verbosity},
            max_output_tokens=self._max_output_tokens,
        )
        text = _extract_response_text(response)
        return _parse_judge_response(text, {str(c.object_id) for c in candidates})


def _extract_response_text(response) -> str:
    for item in response.output or []:
        if item.type == "message":
            for content in item.content or []:
                if content.type == "output_text":
                    return content.text
    return ""


def _parse_judge_response(text: str, allowed_ids: set[str]) -> CorrelationJudgeResult:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("correlation judge returned non-json output")
        return CorrelationJudgeResult()
    raw_decisions = payload.get("decisions") if isinstance(payload, dict) else None
    if not isinstance(raw_decisions, list):
        return CorrelationJudgeResult()
    decisions: list[CorrelationDecision] = []
    for row in raw_decisions:
        if not isinstance(row, dict):
            continue
        target_id = str(row.get("target_object_id", ""))
        if target_id not in allowed_ids:
            continue
        relation_type = str(row.get("relation_type", ""))
        if relation_type not in CORRELATION_ALLOWED_TYPES:
            continue
        try:
            confidence = float(row.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        rationale = str(row.get("rationale", "")).strip()
        decisions.append(
            CorrelationDecision(
                target_object_id=UUID(target_id),
                relation_type=relation_type,
                confidence=confidence,
                rationale=rationale[:500],
            )
        )
    return CorrelationJudgeResult(decisions=tuple(decisions))


def create_correlation_judge() -> CorrelationJudge:
    from app.core.config import settings

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for correlation judge")
    return OpenAICorrelationJudge(
        api_key=settings.openai_api_key,
        model=settings.openai_assistant_model,
        reasoning_effort=settings.openai_assistant_reasoning_effort,
        verbosity=settings.openai_assistant_verbosity,
    )


def create_correlation_judge_from_effective(
    effective: EffectiveUserSettings,
) -> CorrelationJudge:
    if not effective.openai_api_key:
        raise BackgroundAIConfigurationError("OpenAI API key is not configured")
    return OpenAICorrelationJudge(
        api_key=effective.openai_api_key,
        model=effective.assistant_model,
        reasoning_effort=effective.assistant_reasoning_effort,
        verbosity=effective.assistant_verbosity,
    )

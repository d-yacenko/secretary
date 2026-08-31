"""Semantic summary generation and metadata mirroring."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Object, Representation
from app.llm.summarizer import FakeSummarizer, Summarizer
from app.services.correlation_constants import (
    SEMANTIC_SUMMARY_MAX_CHARS,
    SEMANTIC_SUMMARY_METADATA_KEY,
    SEMANTIC_SUMMARY_REVISION_KEY,
)
from app.services.errors import NotFoundError
from app.services.representation_service import (
    KIND_FULL,
    KIND_SAMPLE,
    KIND_SCHEMA,
    KIND_STATISTICS,
    KIND_SUMMARY,
    SMALL_TEXT_MAX_CHARS,
    RepresentationService,
)


class SemanticSummaryService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        summarizer: Summarizer | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._summarizer = summarizer or FakeSummarizer(max_chars=SEMANTIC_SUMMARY_MAX_CHARS)
        self._representations = RepresentationService(session, user_id)

    def update_summary_for_object(self, object_id: UUID) -> str | None:
        obj = self._session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == self._user_id)
        )
        if obj is None:
            raise NotFoundError("object", object_id)

        metadata = dict(obj.metadata_ or {})
        content_revision = metadata.get("content_revision")
        if content_revision is None:
            return None

        reps = self._representations.list_for_object(object_id)
        summary_input = self._build_summary_input(obj, reps)
        if not summary_input:
            return None

        if len(summary_input.strip()) <= SMALL_TEXT_MAX_CHARS:
            summary_text = summary_input.strip()[:SEMANTIC_SUMMARY_MAX_CHARS]
        else:
            summary_text = self._summarizer.summarize(summary_input)

        summary_text = summary_text[:SEMANTIC_SUMMARY_MAX_CHARS]
        self._upsert_summary_representation(object_id, summary_text, reps)
        metadata[SEMANTIC_SUMMARY_METADATA_KEY] = summary_text
        metadata[SEMANTIC_SUMMARY_REVISION_KEY] = content_revision
        obj.metadata_ = metadata
        self._session.flush()
        return summary_text

    def _build_summary_input(self, obj: Object, reps: list[Representation]) -> str:
        if obj.kind == "dataset":
            parts: list[str] = []
            for rep in reps:
                if rep.kind in {KIND_SCHEMA, KIND_STATISTICS, KIND_SAMPLE}:
                    parts.append(rep.text)
            return "\n".join(parts).strip()

        full_text = None
        for rep in reps:
            if rep.kind == KIND_FULL:
                full_text = rep.text
                break
        if full_text:
            return full_text
        if obj.body:
            return obj.body
        for rep in reps:
            if rep.kind == KIND_SUMMARY:
                return rep.text
        return obj.title

    def _upsert_summary_representation(
        self,
        object_id: UUID,
        summary_text: str,
        reps: list[Representation],
    ) -> None:
        existing = next((rep for rep in reps if rep.kind == KIND_SUMMARY), None)
        if existing is not None:
            existing.text = summary_text
            return
        if any(rep.kind == KIND_FULL for rep in reps):
            self._session.add(
                Representation(
                    object_id=object_id,
                    kind=KIND_SUMMARY,
                    text=summary_text,
                    metadata_={},
                )
            )
            return
        self._session.execute(
            delete(Representation).where(
                Representation.object_id == object_id,
                Representation.kind == KIND_SUMMARY,
            )
        )
        self._session.add(
            Representation(
                object_id=object_id,
                kind=KIND_SUMMARY,
                text=summary_text,
                metadata_={},
            )
        )

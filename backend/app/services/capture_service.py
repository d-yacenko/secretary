from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import EdgeCreate, ObjectCreate
from app.db.models import Object
from app.services.errors import NotFoundError, ValidationError
from app.services.graph_service import GraphService

MAX_CAPTURE_CONTEXT_IDS = 20
MAX_CAPTURE_DEPENDS_ON_IDS = 20
PINNED_CONTEXT_ROLE = "user_pinned"
PINNED_ADDED_BY = "user"


@dataclass(frozen=True)
class CaptureTaskResult:
    task_id: UUID
    context_edge_ids: list[UUID]
    dependency_edge_ids: list[UUID]


class CaptureService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._graph = GraphService(session, user_id)

    def capture_task(
        self,
        text: str,
        title: str | None = None,
        context_object_ids: list[UUID] | None = None,
        depends_on_ids: list[UUID] | None = None,
    ) -> CaptureTaskResult:
        body = text.strip()
        if not body:
            raise ValidationError("text must not be empty")

        context_ids = list(context_object_ids or [])
        dependency_ids = list(depends_on_ids or [])
        if len(context_ids) > MAX_CAPTURE_CONTEXT_IDS:
            raise ValidationError("context_object_ids exceeds limit")
        if len(dependency_ids) > MAX_CAPTURE_DEPENDS_ON_IDS:
            raise ValidationError("depends_on_ids exceeds limit")

        resolved_title = title.strip() if title else _derive_title(body)
        if not resolved_title:
            raise ValidationError("title could not be derived from text")

        self._validate_owned_objects(context_ids)
        self._validate_owned_objects(dependency_ids)

        task = self._graph.create_object(
            ObjectCreate(
                kind="task",
                title=resolved_title,
                body=body,
                origin="user",
                state="confirmed",
            )
        )

        context_edge_ids: list[UUID] = []
        for context_id in context_ids:
            edge = self._graph.create_edge(
                EdgeCreate(
                    source_id=task.id,
                    target_id=context_id,
                    type="references",
                    origin="user",
                    state="confirmed",
                    metadata={
                        "context_role": PINNED_CONTEXT_ROLE,
                        "added_by": PINNED_ADDED_BY,
                    },
                )
            )
            context_edge_ids.append(edge.id)

        dependency_edge_ids: list[UUID] = []
        for dependency_id in dependency_ids:
            edge = self._graph.create_edge(
                EdgeCreate(
                    source_id=task.id,
                    target_id=dependency_id,
                    type="depends_on",
                    origin="user",
                    state="confirmed",
                )
            )
            dependency_edge_ids.append(edge.id)

        return CaptureTaskResult(
            task_id=task.id,
            context_edge_ids=context_edge_ids,
            dependency_edge_ids=dependency_edge_ids,
        )

    def _validate_owned_objects(self, object_ids: list[UUID]) -> None:
        for object_id in object_ids:
            row = self._session.scalar(
                select(Object).where(
                    Object.id == object_id,
                    Object.user_id == self._user_id,
                )
            )
            if row is None:
                raise NotFoundError("object", object_id)


def _derive_title(text: str, max_len: int = 120) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            if len(stripped) <= max_len:
                return stripped
            if max_len <= 1:
                return "…"
            return stripped[: max_len - 1].rstrip() + "…"
    return ""

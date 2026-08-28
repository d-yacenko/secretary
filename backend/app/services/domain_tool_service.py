from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.schemas import EdgeCreate, ObjectCreate, ObjectOut, ObjectUpdate
from app.llm.embedding_service import EmbeddingService
from app.services.context_service import ContextService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.graph_service import GraphService
from app.services.provenance import AGENT_ORIGIN, PROPOSED_STATE
from app.services.search_service import SearchService
from app.tools.schemas import (
    CreateTaskInput,
    CreateTaskOutput,
    GetContextInput,
    GetContextOutput,
    GetObjectInput,
    GetObjectOutput,
    LinkObjectsInput,
    LinkObjectsOutput,
    ListNeighborsInput,
    ListNeighborsOutput,
    NeighborItem,
    SearchObjectsInput,
    SearchObjectsOutput,
    ToolError,
    UpdateTaskInput,
    UpdateTaskOutput,
)


class DomainToolService:
    def __init__(self, session: Session, embedding_service: EmbeddingService) -> None:
        self._session = session
        self._graph = GraphService(session, embedding_service)
        self._search = SearchService(session, embedding_service)
        self._context = ContextService(session, embedding_service)

    def search_objects(self, input: SearchObjectsInput) -> SearchObjectsOutput:
        objects = self._search.search(
            query=input.query,
            kind=input.kind,
            limit=input.limit,
        )
        return SearchObjectsOutput(
            objects=[obj.model_dump(mode="json") for obj in objects]
        )

    def get_object(self, input: GetObjectInput) -> GetObjectOutput:
        try:
            obj = self._graph.get_object(input.object_id)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        return GetObjectOutput(object=ObjectOut.from_model(obj).model_dump(mode="json"))

    def get_context(self, input: GetContextInput) -> GetContextOutput:
        if input.object_id is None and input.query is None:
            raise ToolError("get_context requires object_id or query")
        if input.object_id is not None:
            try:
                self._graph.get_object(input.object_id)
            except NotFoundError as exc:
                raise ToolError(f"object not found: {exc.entity_id}") from exc
        result = self._context.build_context(
            object_id=input.object_id,
            query=input.query,
            max_chars=input.max_chars,
        )
        return GetContextOutput(
            items=[item.model_dump(mode="json") for item in result.items],
            total_chars=result.total_chars,
            truncated=result.truncated,
        )

    def list_neighbors(self, input: ListNeighborsInput) -> ListNeighborsOutput:
        try:
            rows = self._graph.get_neighbors(input.object_id)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        neighbors = [
            NeighborItem(
                object=ObjectOut.from_model(neighbor).model_dump(mode="json"),
                edge=_edge_to_dict(edge),
                direction=direction,
            )
            for neighbor, edge, direction in rows
        ]
        return ListNeighborsOutput(object_id=input.object_id, neighbors=neighbors)

    def create_task(self, input: CreateTaskInput) -> CreateTaskOutput:
        due_at = _parse_optional_datetime(input.due_at)
        try:
            obj = self._graph.create_object(
                ObjectCreate(
                    kind="task",
                    title=input.title,
                    origin=AGENT_ORIGIN,
                    body=input.body,
                    status=input.status,
                    due_at=due_at,
                    confidence=input.confidence,
                )
            )
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        except ConflictError as exc:
            raise ToolError(exc.message) from exc
        return CreateTaskOutput(object=ObjectOut.from_model(obj).model_dump(mode="json"))

    def update_task(self, input: UpdateTaskInput) -> UpdateTaskOutput:
        try:
            obj = self._graph.get_object(input.object_id)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        if obj.kind != "task":
            raise ToolError("update_task only supports task objects")
        update_data = input.model_dump(exclude={"object_id"}, exclude_none=True)
        if "due_at" in update_data:
            update_data["due_at"] = _parse_optional_datetime(update_data["due_at"])
        if not update_data:
            raise ToolError("update_task requires at least one field to update")
        updates = ObjectUpdate(**update_data)
        try:
            updated = self._graph.update_object(input.object_id, updates)
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        except ConflictError as exc:
            raise ToolError(exc.message) from exc
        return UpdateTaskOutput(object=ObjectOut.from_model(updated).model_dump(mode="json"))

    def link_objects(self, input: LinkObjectsInput) -> LinkObjectsOutput:
        try:
            edge = self._graph.create_edge(
                EdgeCreate(
                    source_id=input.source_id,
                    target_id=input.target_id,
                    type=input.relation_type,
                    origin=AGENT_ORIGIN,
                    state=PROPOSED_STATE,
                    confidence=input.confidence,
                )
            )
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        return LinkObjectsOutput(edge=_edge_to_dict(edge))


def _edge_to_dict(edge) -> dict:
    from app.api.schemas import EdgeOut

    return EdgeOut.from_model(edge).model_dump(mode="json")


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)

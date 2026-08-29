from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.api.schemas import (
    EdgeCreate,
    EdgeOut,
    NotificationOut,
    ObjectCreate,
    ObjectOut,
    ObjectUpdate,
)
from app.core.config import settings
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.llm.embedding_service import EmbeddingService
from app.services.context_service import ContextService
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.graph_service import GraphService
from app.services.job_queue_service import JobQueueService
from app.services.notification_service import NotificationService
from app.services.provenance import AGENT_ORIGIN, PROPOSED_STATE
from app.services.retrieval_service import RetrievalService
from app.services.search_service import SearchService
from app.tools.datetime_utils import normalize_tool_datetime
from app.tools.schemas import (
    CreateTaskInput,
    CreateTaskOutput,
    GetContextInput,
    GetContextOutput,
    GetObjectInput,
    GetObjectOutput,
    GetTodayOutput,
    LinkObjectsInput,
    LinkObjectsOutput,
    ListNeighborsInput,
    ListNeighborsOutput,
    ListNotificationsInput,
    ListNotificationsOutput,
    NeighborItem,
    RetrievalHitOut,
    RetrieveInput,
    RetrieveOutput,
    SearchObjectsInput,
    SearchObjectsOutput,
    ToolError,
    UpdateTaskInput,
    UpdateTaskOutput,
)


class DomainToolService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        embedding_service: EmbeddingService,
        defer_write_embeddings: bool = False,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._graph = GraphService(session, user_id, embedding_service)
        self._search = SearchService(session, user_id)
        self._retrieval = RetrievalService(session, user_id)
        self._context = ContextService(session, user_id, embedding_service)
        self._notifications = NotificationService(session, user_id)
        self._defer_write_embeddings = defer_write_embeddings
        if defer_write_embeddings:
            self._write_graph = GraphService(session, user_id, None)
            self._job_queue = JobQueueService(session)
        else:
            self._write_graph = self._graph
            self._job_queue = None

    def _enqueue_object_embedding(self, object_id: UUID) -> None:
        if self._job_queue is None:
            return
        self._job_queue.enqueue(
            JOB_TYPE_EMBED_OBJECT,
            {"object_id": str(object_id)},
            user_id=self._user_id,
        )

    def list_notifications(self, input: ListNotificationsInput) -> ListNotificationsOutput:
        try:
            rows = self._notifications.list_notifications(
                status=input.status,
                limit=input.limit,
            )
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        return ListNotificationsOutput(
            notifications=[NotificationOut.from_model(row) for row in rows]
        )

    def search_objects(self, input: SearchObjectsInput) -> SearchObjectsOutput:
        objects = self._search.search(
            query=input.query,
            kind=input.kind,
            limit=input.limit,
        )
        return SearchObjectsOutput(objects=objects)

    def retrieve(self, input: RetrieveInput) -> RetrieveOutput:
        try:
            result = self._retrieval.retrieve(
                query=input.query,
                kind=input.kind,
                time_scope=input.time_scope,
                date_from=input.date_from,
                date_to=input.date_to,
                limit=input.limit,
            )
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        hits = [
            RetrievalHitOut(
                object_id=hit.object_id,
                title=hit.title,
                kind=hit.kind,
                provider=hit.provider,
                occurred_at=hit.occurred_at,
                relevance=hit.relevance,
                reasons=hit.reasons,
                excerpt=hit.short_excerpt,
            )
            for hit in result.hits
        ]
        return RetrieveOutput(
            hits=hits,
            time_scope_used=result.time_scope_used,
            horizon_days=result.horizon_days,
            candidate_count=result.candidate_count,
            retrieval_mode=result.retrieval_mode,
            query_atom_count=result.query_atom_count,
            selected_atom_count=result.selected_atom_count,
        )

    def get_object(self, input: GetObjectInput) -> GetObjectOutput:
        try:
            obj = self._graph.get_object(input.object_id)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        return GetObjectOutput(object=ObjectOut.from_model(obj))

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
            items=result.items,
            total_chars=result.total_chars,
            truncated=result.truncated,
        )

    def list_neighbors(self, input: ListNeighborsInput) -> ListNeighborsOutput:
        try:
            rows = self._graph.get_neighbors(input.object_id, limit=input.limit)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        neighbors = [
            NeighborItem(
                object=ObjectOut.from_model(neighbor),
                edge=EdgeOut.from_model(edge),
                direction=direction,
            )
            for neighbor, edge, direction in rows
        ]
        return ListNeighborsOutput(object_id=input.object_id, neighbors=neighbors)

    def create_task(self, input: CreateTaskInput) -> CreateTaskOutput:
        due_at = normalize_tool_datetime(input.due_at)
        try:
            obj = self._write_graph.create_object(
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
        self._enqueue_object_embedding(obj.id)
        return CreateTaskOutput(object=ObjectOut.from_model(obj))

    def update_task(self, input: UpdateTaskInput) -> UpdateTaskOutput:
        try:
            obj = self._graph.get_object(input.object_id)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        if obj.kind != "task":
            raise ToolError("update_task only supports task objects")
        update_data = input.model_dump(exclude={"object_id"}, exclude_none=True)
        if "due_at" in update_data:
            update_data["due_at"] = normalize_tool_datetime(update_data["due_at"])
        if not update_data:
            raise ToolError("update_task requires at least one field to update")
        updates = ObjectUpdate(**update_data)
        try:
            updated = self._write_graph.update_object(input.object_id, updates)
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        except ConflictError as exc:
            raise ToolError(exc.message) from exc
        self._enqueue_object_embedding(updated.id)
        return UpdateTaskOutput(object=ObjectOut.from_model(updated))

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
        return LinkObjectsOutput(edge=EdgeOut.from_model(edge))

    def get_today(self) -> GetTodayOutput:
        tz_name = settings.secretary_timezone
        now = datetime.now(ZoneInfo(tz_name))
        return GetTodayOutput(datetime=now, timezone=tz_name)

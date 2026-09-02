from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    EdgeCreate,
    EdgeOut,
    NotificationOut,
    ObjectCreate,
    ObjectOut,
)
from app.db.models import Edge, Object
from app.domain.task_lifecycle import (
    TASK_STATUS_DELETED,
    TASK_STATUS_OPEN,
    canonical_task_status_for_model,
)
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.llm.embedding_service import EmbeddingService
from app.services.context_service import ContextService
from app.services.domain_write_mode import DomainWriteMode
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.graph_service import GraphService
from app.services.job_queue_service import JobQueueService
from app.services.notification_service import NotificationService
from app.services.object_query_service import ObjectQueryService
from app.services.provenance import (
    AGENT_ORIGIN,
    CONFIRMED_STATE,
    PROPOSED_STATE,
    REJECTED_STATE,
)
from app.services.retrieval_service import RetrievalService
from app.services.search_service import SearchService
from app.services.task_mutation_service import TaskMutationService
from app.tools.datetime_utils import normalize_tool_datetime
from app.tools.schemas import (
    MAX_TASK_EVIDENCE_IDS,
    CreateTaskInput,
    CreateTaskOutput,
    DeleteTaskInput,
    DeleteTaskOutput,
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
    QueryObjectItemOut,
    QueryObjectsInput,
    QueryObjectsOutput,
    RetrievalHitOut,
    RetrieveInput,
    RetrieveOutput,
    SearchObjectsInput,
    SearchObjectsOutput,
    SetTaskStatusInput,
    SetTaskStatusOutput,
    ToolError,
    UpdateTaskInput,
    UpdateTaskOutput,
)


class DomainToolService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        embedding_service: EmbeddingService | None = None,
        defer_write_embeddings: bool = False,
        write_mode: DomainWriteMode = DomainWriteMode.AGENT_PROPOSED,
        client_timezone: str | None = None,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._write_mode = write_mode
        from app.core.client_timezone import get_request_timezone

        self._client_timezone = client_timezone or get_request_timezone()
        self._graph = GraphService(session, user_id, embedding_service)
        self._search = SearchService(session, user_id)
        self._retrieval = RetrievalService(session, user_id)
        self._object_query = ObjectQueryService(session, user_id)
        self._context = ContextService(session, user_id, embedding_service)
        self._notifications = NotificationService(session, user_id)
        self._defer_write_embeddings = defer_write_embeddings
        if defer_write_embeddings:
            self._write_graph = GraphService(session, user_id, None)
            self._job_queue = JobQueueService(session)
        else:
            self._write_graph = self._graph
            self._job_queue = None

    def _task_mutations(self) -> TaskMutationService:
        embedding = self._write_graph._embedding_service
        return TaskMutationService(self._session, self._user_id, embedding)

    def _tool_error_from_mutation(self, exc: Exception) -> ToolError:
        if isinstance(exc, NotFoundError):
            return ToolError(f"object not found: {exc.entity_id}")
        if isinstance(exc, ValidationError):
            return ToolError(exc.message)
        raise exc

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

    def query_objects(self, input: QueryObjectsInput) -> QueryObjectsOutput:
        try:
            rows = self._object_query.query(
                kinds=input.kinds if input.kinds else None,
                providers=input.providers if input.providers else None,
                statuses=input.statuses if input.statuses else None,
                states=input.states if input.states else None,
                due_from=input.due_from,
                due_to=input.due_to,
                start_from=input.start_from,
                start_to=input.start_to,
                occurred_from=input.occurred_from,
                occurred_to=input.occurred_to,
                sort_by=input.sort_by,
                sort_order=input.sort_order,
                limit=input.limit,
            )
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        return QueryObjectsOutput(
            objects=[
                QueryObjectItemOut(
                    object_id=obj.id,
                    title=obj.title,
                    kind=obj.kind,
                    provider=obj.provider,
                    state=obj.state,
                    status=(
                        canonical_task_status_for_model(obj.status)
                        if obj.kind == "task"
                        else obj.status
                    ),
                    due_at=obj.due_at,
                    start_at=obj.start_at,
                    occurred_at=obj.occurred_at,
                    created_at=obj.created_at,
                    updated_at=obj.updated_at,
                )
                for obj in rows
            ]
        )

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
                state=hit.state,
                status=hit.status,
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

    def _dedupe_evidence_ids(self, evidence_ids: list[UUID]) -> list[UUID]:
        if len(evidence_ids) > MAX_TASK_EVIDENCE_IDS:
            raise ToolError(
                f"evidence_object_ids must contain at most {MAX_TASK_EVIDENCE_IDS} ids"
            )
        seen: set[UUID] = set()
        unique: list[UUID] = []
        for object_id in evidence_ids:
            if object_id in seen:
                continue
            seen.add(object_id)
            unique.append(object_id)
        return unique

    def _validate_evidence_objects(self, evidence_ids: list[UUID]) -> list[Object]:
        objects: list[Object] = []
        for object_id in evidence_ids:
            try:
                obj = self._graph.get_object(object_id)
            except NotFoundError as exc:
                raise ToolError(f"evidence object not found: {exc.entity_id}") from exc
            if obj.state == REJECTED_STATE:
                raise ToolError(f"evidence object rejected: {object_id}")
            if obj.status == "deleted":
                raise ToolError(f"evidence object deleted: {object_id}")
            objects.append(obj)
        return objects

    def _new_artifact_state(self) -> str:
        if self._write_mode == DomainWriteMode.APPROVED_CONFIRMED:
            return CONFIRMED_STATE
        return PROPOSED_STATE

    def _attach_evidence_references(
        self,
        task_id: UUID,
        evidence_ids: list[UUID],
        confidence: float,
    ) -> tuple[int, list[UUID], list[UUID]]:
        created = 0
        added_ids: list[UUID] = []
        already_linked_ids: list[UUID] = []
        edge_state = self._new_artifact_state()
        for evidence_id in evidence_ids:
            existing = self._session.scalar(
                select(Edge).where(
                    Edge.user_id == self._user_id,
                    Edge.source_id == task_id,
                    Edge.target_id == evidence_id,
                    Edge.type == "references",
                )
            )
            if existing is not None and existing.state != REJECTED_STATE:
                already_linked_ids.append(evidence_id)
                continue
            self._write_graph.create_edge(
                EdgeCreate(
                    source_id=task_id,
                    target_id=evidence_id,
                    type="references",
                    origin=AGENT_ORIGIN,
                    state=edge_state,
                    confidence=confidence,
                )
            )
            added_ids.append(evidence_id)
            created += 1
        return created, added_ids, already_linked_ids

    def _get_task_for_mutation(self, object_id: UUID, *, allow_deleted: bool = False) -> Object:
        try:
            obj = self._graph.get_object(object_id)
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        if obj.kind != "task":
            raise ToolError("operation only supports task objects")
        if not allow_deleted and obj.status == TASK_STATUS_DELETED:
            raise ToolError("deleted task cannot be modified")
        return obj

    def create_task(self, input: CreateTaskInput) -> CreateTaskOutput:
        evidence_ids = self._dedupe_evidence_ids(input.evidence_object_ids)
        if evidence_ids:
            self._validate_evidence_objects(evidence_ids)
        due_at = normalize_tool_datetime(input.due_at)
        try:
            obj = self._write_graph.create_object(
                ObjectCreate(
                    kind="task",
                    title=input.title,
                    origin=AGENT_ORIGIN,
                    state=self._new_artifact_state(),
                    body=input.body,
                    status=TASK_STATUS_OPEN,
                    due_at=due_at,
                    confidence=input.confidence,
                )
            )
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        except ConflictError as exc:
            raise ToolError(exc.message) from exc
        if evidence_ids:
            _, _, _ = self._attach_evidence_references(
                obj.id, evidence_ids, input.confidence
            )
        self._enqueue_object_embedding(obj.id)
        return CreateTaskOutput(object=ObjectOut.from_model(obj))

    def update_task(self, input: UpdateTaskInput) -> UpdateTaskOutput:
        obj = self._get_task_for_mutation(input.object_id)
        evidence_ids = self._dedupe_evidence_ids(input.evidence_object_ids)
        if evidence_ids:
            if input.object_id in evidence_ids:
                raise ToolError("task cannot reference itself as evidence")
            self._validate_evidence_objects(evidence_ids)

        fields_set = input.model_fields_set
        field_fields = {"title", "body", "due_at"}
        has_field_updates = any(field in fields_set for field in field_fields)

        updated = obj
        fields_changed = False
        if has_field_updates:
            try:
                patch_result = self._task_mutations().patch_task_fields(
                    input.object_id,
                    title=input.title if "title" in fields_set else None,
                    body=input.body if "body" in fields_set else None,
                    due_at=input.due_at if "due_at" in fields_set else None,
                    fields_set=fields_set,
                )
            except (NotFoundError, ValidationError) as exc:
                raise self._tool_error_from_mutation(exc) from exc
            updated = patch_result.object
            fields_changed = patch_result.changed
        elif not evidence_ids:
            raise ToolError("update_task requires at least one field to update")

        evidence_edges_created = 0
        evidence_added_object_ids: list[UUID] = []
        evidence_already_linked_object_ids: list[UUID] = []
        if evidence_ids:
            confidence = updated.confidence if updated.confidence is not None else 0.5
            (
                evidence_edges_created,
                evidence_added_object_ids,
                evidence_already_linked_object_ids,
            ) = self._attach_evidence_references(updated.id, evidence_ids, confidence)
        changed = fields_changed or evidence_edges_created > 0
        if fields_changed:
            self._enqueue_object_embedding(updated.id)
        return UpdateTaskOutput(
            object=ObjectOut.from_model(updated),
            changed=changed,
            evidence_edges_created=evidence_edges_created,
            evidence_added_object_ids=evidence_added_object_ids,
            evidence_already_linked_object_ids=evidence_already_linked_object_ids,
        )

    def set_task_status(self, input: SetTaskStatusInput) -> SetTaskStatusOutput:
        try:
            result = self._task_mutations().set_task_status(input.object_id, input.status)
        except (NotFoundError, ValidationError) as exc:
            raise self._tool_error_from_mutation(exc) from exc
        if result.changed:
            self._enqueue_object_embedding(result.object.id)
        return SetTaskStatusOutput(
            object=ObjectOut.from_model(result.object),
            changed=result.changed,
            previous_status=result.previous_status,
            new_status=result.new_status,
        )

    def delete_task(self, input: DeleteTaskInput) -> DeleteTaskOutput:
        try:
            result = self._task_mutations().soft_delete_task(input.object_id)
        except (NotFoundError, ValidationError) as exc:
            raise self._tool_error_from_mutation(exc) from exc
        if result.changed:
            self._enqueue_object_embedding(result.object.id)
        return DeleteTaskOutput(
            object=ObjectOut.from_model(result.object),
            changed=result.changed,
            previous_status=result.previous_status,
            new_status=result.new_status,
        )

    def link_objects(self, input: LinkObjectsInput) -> LinkObjectsOutput:
        if input.source_id == input.target_id:
            raise ToolError("source and target must differ")
        existing = self._session.scalar(
            select(Edge).where(
                Edge.user_id == self._user_id,
                Edge.source_id == input.source_id,
                Edge.target_id == input.target_id,
                Edge.type == input.relation_type,
                Edge.state != REJECTED_STATE,
            )
        )
        if existing is not None:
            return LinkObjectsOutput(edge=EdgeOut.from_model(existing), created=False)
        try:
            edge = self._graph.create_edge(
                EdgeCreate(
                    source_id=input.source_id,
                    target_id=input.target_id,
                    type=input.relation_type,
                    origin=AGENT_ORIGIN,
                    state=self._new_artifact_state(),
                    confidence=input.confidence,
                )
            )
        except NotFoundError as exc:
            raise ToolError(f"object not found: {exc.entity_id}") from exc
        except ValidationError as exc:
            raise ToolError(exc.message) from exc
        return LinkObjectsOutput(edge=EdgeOut.from_model(edge), created=True)

    def get_today(self) -> GetTodayOutput:
        tz_name = self._client_timezone
        now = datetime.now(ZoneInfo(tz_name))
        return GetTodayOutput(datetime=now, timezone=tz_name)

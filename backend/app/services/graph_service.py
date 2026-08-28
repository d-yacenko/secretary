from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.schemas import EdgeCreate, ObjectCreate, ObjectUpdate
from app.db.models import Edge, Object
from app.llm.embedding_service import EmbeddingService
from app.services.db_errors import is_external_object_unique_violation
from app.services.embedding_index import refresh_object_embedding
from app.services.errors import ConflictError, NotFoundError

_SEARCHABLE_FIELDS = frozenset({"kind", "title", "body", "metadata"})


class GraphService:
    def __init__(
        self,
        session: Session,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._session = session
        self._embedding_service = embedding_service

    def _flush_object(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as exc:
            if is_external_object_unique_violation(exc):
                raise ConflictError("external object already exists") from exc
            raise

    def create_object(self, data: ObjectCreate) -> Object:
        obj = Object(
            kind=data.kind,
            title=data.title,
            origin=data.origin,
            body=data.body,
            provider=data.provider,
            external_id=data.external_id,
            canonical_uri=data.canonical_uri,
            status=data.status,
            start_at=data.start_at,
            due_at=data.due_at,
            metadata_=data.metadata,
            confidence=data.confidence,
        )
        self._session.add(obj)
        self._flush_object()
        self._maybe_refresh_embedding(obj, set(_SEARCHABLE_FIELDS))
        return obj

    def get_object(self, object_id: UUID) -> Object:
        obj = self._session.get(Object, object_id)
        if obj is None:
            raise NotFoundError("object", object_id)
        return obj

    def update_object(self, object_id: UUID, data: ObjectUpdate) -> Object:
        obj = self.get_object(object_id)
        updates = data.model_dump(exclude_unset=True)
        if "metadata" in updates:
            obj.metadata_ = updates.pop("metadata")
        for field, value in updates.items():
            setattr(obj, field, value)
        self._maybe_refresh_embedding(obj, set(updates.keys()))
        self._flush_object()
        return obj

    def _maybe_refresh_embedding(self, obj: Object, changed_fields: set[str]) -> None:
        if self._embedding_service is None:
            return
        if not changed_fields.intersection(_SEARCHABLE_FIELDS):
            return
        refresh_object_embedding(obj, self._embedding_service)
        self._flush_object()

    def delete_object(self, object_id: UUID) -> None:
        obj = self.get_object(object_id)
        edge_count = self._session.scalar(
            select(func.count())
            .select_from(Edge)
            .where(or_(Edge.source_id == object_id, Edge.target_id == object_id))
        )
        if edge_count and edge_count > 0:
            raise ConflictError("object has incident edges")
        self._session.delete(obj)
        self._session.flush()
        self._session.expire_all()

    def create_edge(self, data: EdgeCreate) -> Edge:
        if self._session.get(Object, data.source_id) is None:
            raise NotFoundError("object", data.source_id)
        if self._session.get(Object, data.target_id) is None:
            raise NotFoundError("object", data.target_id)

        edge = Edge(
            source_id=data.source_id,
            target_id=data.target_id,
            type=data.type,
            origin=data.origin,
            state=data.state,
            confidence=data.confidence,
            metadata_=data.metadata,
        )
        self._session.add(edge)
        self._session.flush()
        return edge

    def delete_edge(self, edge_id: UUID) -> None:
        edge = self._session.get(Edge, edge_id)
        if edge is None:
            raise NotFoundError("edge", edge_id)
        self._session.delete(edge)
        self._session.flush()

    def get_neighbors(self, object_id: UUID) -> list[tuple[Object, Edge, str]]:
        self.get_object(object_id)
        edges = self._session.scalars(
            select(Edge).where(
                or_(Edge.source_id == object_id, Edge.target_id == object_id)
            )
        ).all()

        results: list[tuple[Object, Edge, str]] = []
        for edge in edges:
            if edge.source_id == object_id:
                neighbor = self._session.get(Object, edge.target_id)
                direction = "outgoing"
            else:
                neighbor = self._session.get(Object, edge.source_id)
                direction = "incoming"
            if neighbor is not None:
                results.append((neighbor, edge, direction))
        return results

    def get_context(self, object_id: UUID) -> tuple[Object, list[Edge], list[Object]]:
        obj = self.get_object(object_id)
        edges = self._session.scalars(
            select(Edge).where(
                or_(Edge.source_id == object_id, Edge.target_id == object_id)
            )
        ).all()

        neighbor_ids: set[UUID] = set()
        for edge in edges:
            if edge.source_id == object_id:
                neighbor_ids.add(edge.target_id)
            else:
                neighbor_ids.add(edge.source_id)

        neighbors: list[Object] = []
        if neighbor_ids:
            neighbors = list(
                self._session.scalars(select(Object).where(Object.id.in_(neighbor_ids))).all()
            )

        return obj, edges, neighbors

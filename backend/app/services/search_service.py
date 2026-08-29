import logging
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.schemas import ObjectOut
from app.db.models import Edge, Object
from app.llm.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(
        self,
        session: Session,
        user_id: UUID,
        embedding_service: EmbeddingService,
    ) -> None:
        self._session = session
        self._user_id = user_id
        self._embedding_service = embedding_service

    def search(
        self,
        query: str,
        kind: str | None = None,
        provider: str | None = None,
        project_id: UUID | None = None,
        limit: int = 20,
    ) -> list[ObjectOut]:
        limit = max(1, min(limit, 100))
        stmt = select(Object).where(
            Object.user_id == self._user_id,
            or_(Object.status.is_(None), Object.status != "deleted"),
        )
        stmt = self._apply_filters(stmt, kind=kind, provider=provider, project_id=project_id)

        semantic_results: list[Object] = []
        try:
            query_vector = self._embedding_service.embed(query)
            semantic_stmt = stmt.where(Object.embedding.is_not(None)).order_by(
                Object.embedding.cosine_distance(query_vector)
            )
            semantic_results = list(self._session.scalars(semantic_stmt.limit(limit)).all())
        except Exception:  # noqa: BLE001
            logger.warning("semantic search embedding failed; using lexical fallback")

        if len(semantic_results) >= limit:
            return [ObjectOut.from_model(obj) for obj in semantic_results[:limit]]

        lexical_stmt = stmt.where(
            or_(
                Object.title.ilike(f"%{query}%"),
                Object.body.ilike(f"%{query}%"),
            )
        )
        lexical_results = list(self._session.scalars(lexical_stmt.limit(limit)).all())

        combined: list[Object] = []
        seen: set[UUID] = set()
        for obj in semantic_results + lexical_results:
            if obj.id in seen:
                continue
            seen.add(obj.id)
            combined.append(obj)
            if len(combined) >= limit:
                break

        return [ObjectOut.from_model(obj) for obj in combined]

    def _apply_filters(
        self,
        stmt,
        kind: str | None,
        provider: str | None,
        project_id: UUID | None,
    ):
        if kind is not None:
            stmt = stmt.where(Object.kind == kind)
        if provider is not None:
            stmt = stmt.where(Object.provider == provider)
        if project_id is not None:
            linked_ids = (
                select(Edge.target_id)
                .where(Edge.user_id == self._user_id, Edge.source_id == project_id)
                .union_all(
                    select(Edge.source_id).where(
                        Edge.user_id == self._user_id,
                        Edge.target_id == project_id,
                    )
                )
            )
            stmt = stmt.where(Object.id.in_(linked_ids))
        return stmt

from uuid import UUID

from sqlalchemy.orm import Session

from app.api.schemas import ObjectOut
from app.services.retrieval_constants import MAX_FINAL_HITS, TIME_SCOPE_ALL
from app.services.retrieval_service import RetrievalService, load_objects_ordered


class SearchService:
    def __init__(self, session: Session, user_id: UUID) -> None:
        self._session = session
        self._user_id = user_id
        self._retrieval = RetrievalService(session, user_id)

    def search(
        self,
        query: str,
        kind: str | None = None,
        provider: str | None = None,
        project_id: UUID | None = None,
        limit: int = 20,
    ) -> list[ObjectOut]:
        ui_limit = max(1, min(limit, MAX_FINAL_HITS))
        result = self._retrieval.retrieve(
            query=query,
            kind=kind,
            provider=provider,
            project_id=project_id,
            time_scope=TIME_SCOPE_ALL,
            limit=ui_limit,
        )
        objects = load_objects_ordered(self._session, self._user_id, result.hits)
        return [ObjectOut.from_model(obj) for obj in objects]

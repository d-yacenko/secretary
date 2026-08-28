from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Object
from app.db.session import SessionLocal
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.jobs.types import JobHandler
from app.llm.embedding_service import EmbeddingService
from app.llm.embedding_text import build_embedding_text
from app.services.errors import NotFoundError
from app.services.graph_service import GraphService


def _load_embedding_text(object_id: UUID) -> str:
    session = SessionLocal()
    try:
        graph = GraphService(session)
        obj = graph.get_object(object_id)
        return build_embedding_text(obj)
    except NotFoundError as exc:
        raise ValueError(f"object not found: {exc.entity_id}") from exc
    finally:
        session.close()


def _store_object_embedding(object_id: UUID, embedding: list[float]) -> None:
    session = SessionLocal()
    try:
        obj = session.get(Object, object_id)
        if obj is None:
            raise ValueError(f"object not found: {object_id}")
        obj.embedding = embedding
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def handle_embed_object(
    session: Session,
    embedding_service: EmbeddingService,
    payload: dict,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    text = _load_embedding_text(object_id)
    embedding = embedding_service.embed(text)
    _store_object_embedding(object_id, embedding)


HANDLERS: dict[str, JobHandler] = {
    JOB_TYPE_EMBED_OBJECT: handle_embed_object,
}


def get_handler(job_type: str) -> JobHandler | None:
    return HANDLERS.get(job_type)

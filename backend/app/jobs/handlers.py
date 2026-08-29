from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Object
from app.db.session import SessionLocal
from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.jobs.types import JobHandler
from app.llm.embedding_text import build_embedding_text
from app.services.representation_embedding_worker import (
    load_unembedded_chunk_targets,
    store_representation_embeddings,
)


def _load_embedding_text(object_id: UUID, user_id: UUID) -> str:
    session = SessionLocal()
    try:
        obj = session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")
        return build_embedding_text(obj)
    finally:
        session.close()


def _store_object_embedding(object_id: UUID, user_id: UUID, embedding: list[float]) -> None:
    session = SessionLocal()
    try:
        obj = session.scalar(
            select(Object).where(Object.id == object_id, Object.user_id == user_id)
        )
        if obj is None:
            raise ValueError(f"object ownership mismatch: {object_id}")
        obj.embedding = embedding
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def handle_embed_object(
    session: Session,
    embedding_service,
    payload: dict,
    user_id: UUID,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    text = _load_embedding_text(object_id, user_id)
    embedding = embedding_service.embed(text)
    _store_object_embedding(object_id, user_id, embedding)

    chunk_targets = load_unembedded_chunk_targets(object_id, user_id)
    if chunk_targets:
        chunk_embeddings = [
            (target.representation_id, embedding_service.embed(target.text))
            for target in chunk_targets
        ]
        store_representation_embeddings(object_id, user_id, chunk_embeddings)


HANDLERS: dict[str, JobHandler] = {
    JOB_TYPE_EMBED_OBJECT: handle_embed_object,
}


def get_handler(job_type: str) -> JobHandler | None:
    return HANDLERS.get(job_type)

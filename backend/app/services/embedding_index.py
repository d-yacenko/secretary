import logging

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.db.models import Object
from app.llm.embedding_service import EmbeddingService
from app.llm.embedding_text import canonical_embedding_text, embedding_input_signature

logger = logging.getLogger(__name__)


def object_has_current_embedding_provenance(obj: Object, signature: str) -> bool:
    return obj.embedding is not None and obj.embedding_signature == signature


def assign_object_embedding(obj: Object, vector: list[float], signature: str) -> None:
    obj.embedding = vector
    obj.embedding_signature = signature


def clear_object_embedding(obj: Object) -> None:
    obj.embedding = None
    obj.embedding_signature = None


def refresh_object_embedding(
    obj: Object,
    embedding_service: EmbeddingService,
) -> None:
    intended_sig = embedding_input_signature(obj)
    if object_has_current_embedding_provenance(obj, intended_sig):
        return
    try:
        vector = embedding_service.embed(canonical_embedding_text(obj))
    except Exception:  # noqa: BLE001
        logger.warning("embedding refresh failed for object %s", obj.id)
        clear_object_embedding(obj)
        return
    session = object_session(obj)
    if session is None:
        if embedding_input_signature(obj) != intended_sig:
            return
        assign_object_embedding(obj, vector, intended_sig)
        return
    locked = session.scalar(
        select(Object)
        .where(Object.id == obj.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        return
    if embedding_input_signature(locked) != intended_sig:
        from app.services.pipeline_enqueue import enqueue_embed_object

        enqueue_embed_object(session, locked.id, locked.user_id)
        return
    assign_object_embedding(locked, vector, intended_sig)
    session.flush()

import logging

from app.db.models import Object
from app.llm.embedding_service import EmbeddingService
from app.llm.embedding_text import build_embedding_text

logger = logging.getLogger(__name__)


def refresh_object_embedding(
    obj: Object,
    embedding_service: EmbeddingService,
) -> None:
    try:
        obj.embedding = embedding_service.embed(build_embedding_text(obj))
    except Exception:
        logger.warning("embedding refresh failed for object %s", obj.id)
        obj.embedding = None

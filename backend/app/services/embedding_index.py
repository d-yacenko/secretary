from app.db.models import Object
from app.llm.embedding_service import EmbeddingService
from app.llm.embedding_text import build_embedding_text


def refresh_object_embedding(
    obj: Object,
    embedding_service: EmbeddingService,
) -> None:
    obj.embedding = embedding_service.embed(build_embedding_text(obj))

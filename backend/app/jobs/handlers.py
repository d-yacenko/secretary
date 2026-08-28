from uuid import UUID

from sqlalchemy.orm import Session

from app.jobs.constants import JOB_TYPE_EMBED_OBJECT
from app.jobs.types import JobHandler
from app.llm.embedding_service import EmbeddingService
from app.services.embedding_index import refresh_object_embedding
from app.services.graph_service import GraphService


def handle_embed_object(
    session: Session,
    embedding_service: EmbeddingService,
    payload: dict,
) -> None:
    object_id = UUID(str(payload["object_id"]))
    graph = GraphService(session, embedding_service)
    obj = graph.get_object(object_id)
    refresh_object_embedding(obj, embedding_service)
    session.flush()


HANDLERS: dict[str, JobHandler] = {
    JOB_TYPE_EMBED_OBJECT: handle_embed_object,
}


def get_handler(job_type: str) -> JobHandler | None:
    return HANDLERS.get(job_type)

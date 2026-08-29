from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from app.db.session import SessionLocal
from app.llm.embedding_service import create_embedding_service
from app.services.domain_tool_service import DomainToolService


@contextmanager
def assistant_tool_session(user_id: UUID) -> Iterator[DomainToolService]:
    """Short-lived DB session for one Assistant tool invocation."""
    session = SessionLocal()
    try:
        tools = DomainToolService(session, user_id, create_embedding_service())
        yield tools
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

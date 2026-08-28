from contextlib import contextmanager
from collections.abc import Iterator

from app.db.session import SessionLocal
from app.llm.embedding_service import create_embedding_service
from app.services.domain_tool_service import DomainToolService
from app.users.bootstrap import BOOTSTRAP_USER_ID


@contextmanager
def tool_session() -> Iterator[DomainToolService]:
    session = SessionLocal()
    try:
        tools = DomainToolService(session, BOOTSTRAP_USER_ID, create_embedding_service())
        yield tools
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

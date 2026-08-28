from contextlib import contextmanager
from collections.abc import Iterator

from app.db.session import SessionLocal
from app.llm.embedding_service import create_embedding_service
from app.services.domain_tool_service import DomainToolService
from app.users.current_user_provider import resolve_current_user


@contextmanager
def tool_session() -> Iterator[DomainToolService]:
    session = SessionLocal()
    try:
        current_user = resolve_current_user()
        tools = DomainToolService(session, current_user.user_id, create_embedding_service())
        yield tools
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

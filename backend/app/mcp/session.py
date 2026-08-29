from collections.abc import Iterator
from contextlib import contextmanager

from app.auth.errors import AuthenticationError
from app.db.session import SessionLocal
from app.llm.embedding_service import create_embedding_service
from app.services.domain_tool_service import DomainToolService
from app.users.current_user_provider import resolve_current_user


@contextmanager
def tool_session() -> Iterator[DomainToolService]:
    session = SessionLocal()
    try:
        try:
            current_user = resolve_current_user(session)
        except AuthenticationError as exc:
            raise RuntimeError(
                "MCP tools require Authorization: Bearer <token>; enable MCP only with authenticated access"
            ) from exc
        tools = DomainToolService(session, current_user.user_id, create_embedding_service())
        yield tools
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

from collections.abc import Generator
from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.current_user import CurrentUserContext
from app.db.session import SessionLocal
from app.llm.embedding_service import EmbeddingService, create_embedding_service
from app.users.current_user_provider import resolve_current_user


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_embedding_service() -> EmbeddingService:
    return create_embedding_service()


def get_current_user() -> CurrentUserContext:
    return resolve_current_user()


def get_user_id(current_user: CurrentUserContext = Depends(get_current_user)) -> UUID:
    return current_user.user_id

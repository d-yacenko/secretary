from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.errors import AuthenticationError
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


def get_current_user(session: Session = Depends(get_db)) -> CurrentUserContext:
    try:
        return resolve_current_user(session)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc


def get_user_id(current_user: CurrentUserContext = Depends(get_current_user)) -> UUID:
    return current_user.user_id

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.llm.embedding_service import EmbeddingService, create_embedding_service


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

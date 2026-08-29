import os

os.environ.setdefault("MCP_ENABLED", "false")

import pytest
from contextlib import contextmanager
from sqlalchemy.orm import Session

from app.db.engine import engine
from app.db.models import User
from app.llm.embedding_service import FakeEmbeddingService
from app.services.domain_tool_service import DomainToolService
from app.users.bootstrap import BOOTSTRAP_DISPLAY_NAME, BOOTSTRAP_USER_ID


@pytest.fixture(scope="session", autouse=True)
def _ensure_bootstrap_user_exists() -> None:
    if os.environ.get("SKIP_DB_FIXTURES") == "1":
        return
    with Session(engine) as session:
        if session.get(User, BOOTSTRAP_USER_ID) is None:
            session.add(
                User(id=BOOTSTRAP_USER_ID, display_name=BOOTSTRAP_DISPLAY_NAME)
            )
            session.commit()


@pytest.fixture
def bootstrap_user_id():
    return BOOTSTRAP_USER_ID


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def fake_embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def patched_mcp_tool_session(db_session, fake_embedding_service, monkeypatch):
    @contextmanager
    def test_tool_session():
        yield DomainToolService(db_session, BOOTSTRAP_USER_ID, fake_embedding_service)

    monkeypatch.setattr("app.mcp.server.tool_session", test_tool_session)

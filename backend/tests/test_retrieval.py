import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.api.schemas import ObjectCreate
from app.db.models import Object, User
from app.services.graph_service import GraphService
from app.services.provenance import REJECTED_STATE
from app.services.retrieval_constants import (
    MAX_CANDIDATE_POOL,
    MAX_FINAL_HITS,
    TIME_SCOPE_ALL,
    TIME_SCOPE_AUTO,
    TIME_SCOPE_RECENT,
)
from app.services.retrieval_service import RetrievalService
from app.services.search_service import SearchService
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture
def user_b_id(db_session) -> uuid.UUID:
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, display_name="User B"))
    db_session.flush()
    return user_id


def _create_object(
    db_session,
    user_id: uuid.UUID,
    *,
    kind: str,
    title: str,
    body: str | None = None,
    provider: str | None = None,
    occurred_at: datetime | None = None,
    state: str = "confirmed",
    status: str | None = None,
) -> Object:
    graph = GraphService(db_session, user_id, None)
    obj = graph.create_object(
        ObjectCreate(
            kind=kind,
            title=title,
            body=body,
            origin="source",
            provider=provider,
            state=state,
            status=status,
        )
    )
    if occurred_at is not None:
        obj.occurred_at = occurred_at
    db_session.flush()
    return obj


def test_retrieval_user_isolation(db_session, user_b_id) -> None:
    user_a_object = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="event",
        title="Isolation unique Norilsk marker A",
        occurred_at=datetime.now(UTC),
    )
    user_b_object = _create_object(
        db_session,
        user_b_id,
        kind="event",
        title="Isolation unique Norilsk marker B",
        occurred_at=datetime.now(UTC),
    )

    service = RetrievalService(db_session, BOOTSTRAP_USER_ID)
    hits = service.retrieve(
        "Isolation unique Norilsk marker",
        time_scope=TIME_SCOPE_ALL,
        limit=5,
    ).hits
    hit_ids = {hit.object_id for hit in hits}
    assert user_a_object.id in hit_ids
    assert user_b_object.id not in hit_ids


def test_retrieval_top_k_is_maximum_not_target(db_session) -> None:
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="event",
        title="Unique anchor title marker",
        occurred_at=datetime.now(UTC),
    )
    for index in range(10):
        _create_object(
            db_session,
            BOOTSTRAP_USER_ID,
            kind="email",
            title=f"Noise newsletter {index}",
            body="random unrelated newsletter body",
            provider="gmail",
            occurred_at=datetime.now(UTC),
        )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Unique anchor title marker",
        time_scope=TIME_SCOPE_ALL,
        limit=5,
    ).hits
    assert len(hits) == 1


def test_retrieval_nornickel_fixture(db_session) -> None:
    now = datetime.now(UTC)
    event = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="event",
        title="Вопрос по Норникелю",
        body="Обсуждение активности",
        provider="google_calendar",
        occurred_at=now - timedelta(days=3),
    )
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="email",
        title="Re: Норникель quarterly update",
        body="Норникель activity summary for the team",
        provider="gmail",
        occurred_at=now - timedelta(days=2),
    )
    for index in range(12):
        _create_object(
            db_session,
            BOOTSTRAP_USER_ID,
            kind="email",
            title=f"Server status newsletter {index}",
            body="automated server monitoring message",
            provider="gmail",
            occurred_at=now - timedelta(days=1),
        )
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="task",
        title="Тестовая задача из Linux клиента",
        body="linux client smoke marker",
        occurred_at=None,
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "активность по норникелю",
        time_scope=TIME_SCOPE_AUTO,
        limit=5,
    ).hits

    assert len(hits) <= MAX_FINAL_HITS
    assert hits[0].object_id == event.id
    titles = {hit.title for hit in hits}
    assert "Тестовая задача из Linux клиента" not in titles
    assert all("Server status newsletter" not in title for title in titles)


def test_retrieval_recent_horizon_excludes_old_source_noise(db_session) -> None:
    now = datetime.now(UTC)
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="event",
        title="Recent Norilsk planning session",
        occurred_at=now - timedelta(days=5),
    )
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="email",
        title="Old Norilsk archive email",
        body="Norilsk historical mention",
        provider="gmail",
        occurred_at=now - timedelta(days=400),
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Norilsk",
        time_scope=TIME_SCOPE_RECENT,
        limit=5,
    ).hits
    titles = {hit.title for hit in hits}
    assert "Recent Norilsk planning session" in titles
    assert "Old Norilsk archive email" not in titles


def test_retrieval_old_history_fallback(db_session) -> None:
    now = datetime.now(UTC)
    old_email = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="email",
        title="Ancient exact subject Norilsk archive",
        body="little else",
        provider="gmail",
        occurred_at=now - timedelta(days=800),
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Ancient exact subject Norilsk archive",
        time_scope=TIME_SCOPE_AUTO,
        limit=5,
    ).hits
    assert any(hit.object_id == old_email.id for hit in hits)


def test_retrieval_explicit_all_history(db_session) -> None:
    now = datetime.now(UTC)
    old_email = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="email",
        title="Legacy mailbox Norilsk note",
        provider="gmail",
        occurred_at=now - timedelta(days=500),
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Legacy mailbox Norilsk",
        time_scope=TIME_SCOPE_ALL,
        limit=5,
    ).hits
    assert any(hit.object_id == old_email.id for hit in hits)


def test_retrieval_occurred_at_not_created_at_for_recency(db_session) -> None:
    now = datetime.now(UTC)
    old_occurred = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="email",
        title="Historical Norilsk import today",
        provider="gmail",
        occurred_at=now - timedelta(days=600),
    )
    old_occurred.created_at = now
    db_session.flush()

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Historical Norilsk import today",
        time_scope=TIME_SCOPE_RECENT,
        limit=5,
    ).hits
    assert hits == []


def test_retrieval_unknown_source_time_not_recent(db_session) -> None:
    now = datetime.now(UTC)
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="email",
        title="Unknown-time Norilsk email",
        body="Norilsk unknown timestamp",
        provider="gmail",
        occurred_at=None,
    )
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="event",
        title="Known recent Norilsk event",
        occurred_at=now - timedelta(days=2),
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Norilsk",
        time_scope=TIME_SCOPE_RECENT,
        limit=5,
    ).hits
    titles = {hit.title for hit in hits}
    assert "Known recent Norilsk event" in titles
    assert "Unknown-time Norilsk email" not in titles


def test_retrieval_does_not_call_embedding_service(db_session) -> None:
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="note",
        title="Embedding isolation marker",
        body="embedding isolation body",
    )
    RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Embedding isolation marker",
        time_scope=TIME_SCOPE_ALL,
    )
    SearchService(db_session, BOOTSTRAP_USER_ID).search("Embedding isolation marker")


def test_retrieval_excludes_deleted_and_rejected(db_session) -> None:
    active = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="note",
        title="Retrieval visibility marker",
        body="visible",
    )
    deleted = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="note",
        title="Retrieval visibility marker deleted",
        body="hidden deleted",
        status="deleted",
    )
    rejected = _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="note",
        title="Retrieval visibility marker rejected",
        body="hidden rejected",
        state=REJECTED_STATE,
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Retrieval visibility marker",
        time_scope=TIME_SCOPE_ALL,
        limit=10,
    ).hits
    ids = {hit.object_id for hit in hits}
    assert active.id in ids
    assert deleted.id not in ids
    assert rejected.id not in ids


def test_retrieval_candidate_bounds(db_session) -> None:
    now = datetime.now(UTC)
    for index in range(MAX_CANDIDATE_POOL + 25):
        _create_object(
            db_session,
            BOOTSTRAP_USER_ID,
            kind="email",
            title=f"Bound noise email {index}",
            body="bound noise keyword",
            provider="gmail",
            occurred_at=now - timedelta(days=1),
        )
    _create_object(
        db_session,
        BOOTSTRAP_USER_ID,
        kind="event",
        title="Bound noise keyword anchor event",
        occurred_at=now,
    )

    hits = RetrievalService(db_session, BOOTSTRAP_USER_ID).retrieve(
        "Bound noise keyword",
        time_scope=TIME_SCOPE_ALL,
        limit=MAX_FINAL_HITS,
    ).hits
    assert len(hits) <= MAX_FINAL_HITS

"""PHASE 28C-R1 — Recent source feed orders by Object.created_at."""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ObjectCreate
from app.db.models import Object
from app.services.graph_service import GraphService
from app.services.job_queue_service import utcnow
from app.services.object_primary_date import object_primary_search_datetime
from app.services.recent_source_service import (
    RECENT_SOURCE_RESERVED_PER_PROVIDER,
    RecentSourceService,
)
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture(autouse=True)
def _isolate_recent_objects(db_session: Session) -> None:
    db_session.execute(
        Object.__table__.delete().where(Object.user_id == BOOTSTRAP_USER_ID)
    )
    db_session.commit()


def _create_source_object(
    graph: GraphService,
    db_session: Session,
    *,
    title: str,
    provider: str,
    kind: str = "email",
    created_at: datetime,
    updated_at: datetime | None = None,
    occurred_at: datetime | None = None,
) -> Object:
    when = occurred_at or created_at
    graph.create_object(
        ObjectCreate(
            kind=kind,
            title=title,
            origin="source",
            state="observed",
            provider=provider,
            external_id=f"ext-{uuid.uuid4()}",
            occurred_at=when,
        )
    )
    obj = db_session.scalar(select(Object).where(Object.title == title))
    obj.created_at = created_at
    obj.updated_at = updated_at or created_at
    if occurred_at is not None:
        obj.occurred_at = occurred_at
    return obj


def test_recent_source_newer_created_at_wins_over_newer_updated_at(
    db_session: Session,
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    base = utcnow()
    _create_source_object(
        graph,
        db_session,
        title="Older ingest newer touch",
        provider="gmail",
        created_at=base,
        updated_at=base + timedelta(hours=2),
    )
    _create_source_object(
        graph,
        db_session,
        title="Newer ingest",
        provider="gmail",
        created_at=base + timedelta(hours=1),
        updated_at=base + timedelta(minutes=30),
    )
    db_session.commit()

    rows = RecentSourceService(db_session, BOOTSTRAP_USER_ID).list_recent(limit=5)
    assert [row.title for row in rows[:2]] == ["Newer ingest", "Older ingest newer touch"]


def test_recent_source_updated_old_object_does_not_promote_above_newer_created(
    db_session: Session,
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    base = utcnow()
    _create_source_object(
        graph,
        db_session,
        title="Fresh ingest",
        provider="gmail",
        created_at=base,
        updated_at=base,
    )
    _create_source_object(
        graph,
        db_session,
        title="Stale ingest",
        provider="gmail",
        created_at=base - timedelta(hours=2),
        updated_at=base - timedelta(hours=2),
    )
    db_session.commit()

    stale = db_session.scalar(select(Object).where(Object.title == "Stale ingest"))
    stale.updated_at = base + timedelta(hours=3)
    db_session.commit()

    rows = RecentSourceService(db_session, BOOTSTRAP_USER_ID).list_recent(limit=5)
    assert rows[0].title == "Fresh ingest"


def test_recent_source_provider_ranking_uses_max_created_at(db_session: Session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    base = utcnow()
    for index in range(5):
        _create_source_object(
            graph,
            db_session,
            title=f"GC old ingest {index}",
            provider="google_calendar",
            kind="event",
            created_at=base - timedelta(days=1, seconds=index),
            updated_at=base + timedelta(hours=1),
        )
    _create_source_object(
        graph,
        db_session,
        title="Gmail fresh ingest",
        provider="gmail",
        created_at=base,
        updated_at=base - timedelta(hours=2),
    )
    db_session.commit()

    rows = RecentSourceService(db_session, BOOTSTRAP_USER_ID).list_recent(limit=10)
    providers = [row.provider for row in rows]
    assert providers[0] == "gmail"
    assert "google_calendar" in providers


def test_recent_source_reserved_rows_use_created_at(db_session: Session) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    base = utcnow()
    for index in range(RECENT_SOURCE_RESERVED_PER_PROVIDER + 2):
        _create_source_object(
            graph,
            db_session,
            title=f"Gmail reserved {index}",
            provider="gmail",
            created_at=base - timedelta(minutes=index),
            updated_at=base + timedelta(hours=index),
        )
    db_session.commit()

    rows = RecentSourceService(db_session, BOOTSTRAP_USER_ID).list_recent(limit=30)
    gmail_rows = [row for row in rows if row.provider == "gmail"]
    assert len(gmail_rows) >= RECENT_SOURCE_RESERVED_PER_PROVIDER
    titles = [row.title for row in gmail_rows[:RECENT_SOURCE_RESERVED_PER_PROVIDER]]
    assert titles == [f"Gmail reserved {index}" for index in range(RECENT_SOURCE_RESERVED_PER_PROVIDER)]


def test_inbox_recent_primary_at_uses_domain_date_not_created_at(
    auth_client,
    db_session: Session,
) -> None:
    graph = GraphService(db_session, BOOTSTRAP_USER_ID)
    ingest = utcnow()
    domain = ingest - timedelta(days=30)
    graph.create_object(
        ObjectCreate(
            kind="email",
            title="Historical email",
            origin="source",
            state="observed",
            provider="gmail",
            external_id=f"ext-{uuid.uuid4()}",
            occurred_at=domain,
        )
    )
    obj = db_session.scalar(select(Object).where(Object.title == "Historical email"))
    obj.created_at = ingest
    obj.updated_at = ingest
    obj.occurred_at = domain
    db_session.commit()

    expected_primary = object_primary_search_datetime(obj)
    response = auth_client.get("/inbox")
    assert response.status_code == 200
    body = response.json()
    recent = body["recent_source_objects"]
    row = next(item for item in recent if item["title"] == "Historical email")
    assert row["primary_at"] is not None
    assert row["primary_at"].startswith(expected_primary.isoformat()[:10])

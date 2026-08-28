import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.schemas import ObjectCreate
from app.db.engine import engine
from app.db.models import Job, Object
from app.jobs.constants import (
    JOB_STATUS_DONE,
    JOB_STATUS_FAILED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RUNNING,
    JOB_TYPE_EMBED_OBJECT,
    MAX_JOB_ATTEMPTS,
)
from app.jobs.handlers import get_handler
from app.jobs.worker import process_one_job
from app.llm.embedding_service import FakeEmbeddingService
from app.services.graph_service import GraphService
from app.services.job_queue_service import JobQueueService, utcnow


def _persist_enqueue(job_type: str, payload: dict) -> uuid.UUID:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    job_id = JobQueueService(session).enqueue(job_type, payload).id
    trans.commit()
    conn.close()
    return job_id


def _delete_job(job_id: uuid.UUID) -> None:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    session.execute(delete(Job).where(Job.id == job_id))
    trans.commit()
    conn.close()


def _get_job(job_id: uuid.UUID) -> Job | None:
    conn = engine.connect()
    session = Session(bind=conn)
    job = session.get(Job, job_id)
    conn.close()
    return job


def _persist_object() -> uuid.UUID:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    obj = GraphService(session, FakeEmbeddingService()).create_object(
        ObjectCreate(
            kind="task",
            title=f"Persisted job object {uuid.uuid4()}",
            origin="user",
        )
    )
    obj_id = obj.id
    trans.commit()
    conn.close()
    return obj_id


def _delete_object(object_id: uuid.UUID) -> None:
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    obj = session.get(Object, object_id)
    if obj is not None:
        session.delete(obj)
    trans.commit()
    conn.close()


@pytest.fixture(autouse=True)
def cleanup_persisted_job_fixtures() -> None:
    yield
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    session.execute(delete(Job))
    session.execute(delete(Object).where(Object.title.like("Persisted job object %")))
    trans.commit()
    conn.close()


@pytest.fixture
def fake_embedding_service() -> FakeEmbeddingService:
    return FakeEmbeddingService()


@pytest.fixture
def queue(db_session) -> JobQueueService:
    return JobQueueService(db_session)


def _create_object(db_session) -> Object:
    graph = GraphService(db_session)
    return graph.create_object(ObjectCreate(kind="task", title="Job test object", origin="user"))


def test_enqueue_creates_pending_job(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    assert job.status == JOB_STATUS_PENDING
    assert job.attempts == 0


def test_claim_marks_running_and_increments_attempts(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed.id == job.id
    stored = queue.get_job(job.id)
    assert stored is not None
    assert stored.status == JOB_STATUS_RUNNING
    assert stored.attempts == 1
    assert stored.locked_at is not None


def test_mark_done_sets_status_done(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    claimed = queue.claim_next()
    assert claimed is not None
    queue.mark_done(claimed.id)
    stored = queue.get_job(job.id)
    assert stored is not None
    assert stored.status == JOB_STATUS_DONE
    assert stored.locked_at is None


def test_failure_schedules_retry_with_future_run_after(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    claimed = queue.claim_next()
    assert claimed is not None
    before = utcnow()
    queue.mark_retry(claimed.id, "temporary failure")
    stored = queue.get_job(job.id)
    assert stored is not None
    assert stored.status == JOB_STATUS_PENDING
    assert stored.run_after > before
    assert stored.last_error == "temporary failure"


def test_final_failure_marks_failed(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    for attempt in range(MAX_JOB_ATTEMPTS):
        stored = queue.get_job(job.id)
        assert stored is not None
        if stored.status == JOB_STATUS_PENDING:
            stored.run_after = utcnow()
        claimed = queue.claim_next()
        assert claimed is not None
        queue.mark_retry(claimed.id, f"failure {attempt + 1}")
    stored = queue.get_job(job.id)
    assert stored is not None
    assert stored.status == JOB_STATUS_FAILED
    assert stored.attempts == MAX_JOB_ATTEMPTS


def test_future_run_after_job_is_not_claimed_early(queue) -> None:
    future = utcnow() + timedelta(hours=1)
    queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())}, run_after=future)
    assert queue.claim_next() is None


def test_stale_running_job_can_be_recovered(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    claimed = queue.claim_next()
    assert claimed is not None
    stored = queue.get_job(job.id)
    assert stored is not None
    stored.locked_at = utcnow() - timedelta(minutes=16)
    stored.status = JOB_STATUS_RUNNING
    recovered = queue.claim_next()
    assert recovered is not None
    assert recovered.id == job.id
    assert recovered.attempts == 2


def test_unknown_job_type_has_no_handler() -> None:
    assert get_handler("sync_connector") is None


def test_unknown_job_type_fails_cleanly(fake_embedding_service) -> None:
    job_id = _persist_enqueue("sync_connector", {"connector": "mail"})
    try:
        processed = process_one_job(fake_embedding_service)
        assert processed
        stored = _get_job(job_id)
        assert stored is not None
        assert stored.status == JOB_STATUS_FAILED
        assert stored.last_error == "unknown job type"
    finally:
        _delete_job(job_id)


def test_worker_continues_after_one_failed_job(fake_embedding_service) -> None:
    bad_id = _persist_enqueue("sync_connector", {"connector": "mail"})
    obj_id = _persist_object()
    good_id = _persist_enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(obj_id)})
    try:
        assert process_one_job(fake_embedding_service)
        stored_bad = _get_job(bad_id)
        assert stored_bad is not None
        assert stored_bad.status == JOB_STATUS_FAILED

        assert process_one_job(fake_embedding_service)
        stored_good = _get_job(good_id)
        assert stored_good is not None
        assert stored_good.status == JOB_STATUS_DONE
    finally:
        _delete_job(bad_id)
        _delete_job(good_id)
        _delete_object(obj_id)


def test_embed_object_job_refreshes_embedding(fake_embedding_service) -> None:
    obj_id = _persist_object()
    job_id = _persist_enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(obj_id)})
    try:
        assert process_one_job(fake_embedding_service)
        conn = engine.connect()
        session = Session(bind=conn)
        obj = session.get(Object, obj_id)
        assert obj is not None
        assert obj.embedding is not None
        assert len(obj.embedding) > 0
        stored = _get_job(job_id)
        assert stored is not None
        assert stored.status == JOB_STATUS_DONE
        conn.close()
    finally:
        _delete_job(job_id)
        _delete_object(obj_id)


def test_job_payload_stays_small_reference_based(queue) -> None:
    object_id = uuid.uuid4()
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(object_id)})
    assert job.payload == {"object_id": str(object_id)}
    assert len(str(job.payload)) < 200


def test_two_claimers_do_not_receive_same_job() -> None:
    setup_conn = engine.connect()
    setup_trans = setup_conn.begin()
    setup_session = Session(bind=setup_conn)
    job_id = JobQueueService(setup_session).enqueue(
        JOB_TYPE_EMBED_OBJECT,
        {"object_id": str(uuid.uuid4())},
    ).id
    setup_trans.commit()
    setup_conn.close()

    conn1 = engine.connect()
    conn2 = engine.connect()
    trans1 = conn1.begin()
    trans2 = conn2.begin()
    s1 = Session(bind=conn1)
    s2 = Session(bind=conn2)
    try:
        claimed1 = JobQueueService(s1).claim_next()
        claimed2 = JobQueueService(s2).claim_next()
        assert claimed1 is not None
        assert claimed2 is None
        trans1.commit()
        trans2.commit()
    finally:
        conn1.close()
        conn2.close()

    cleanup_conn = engine.connect()
    cleanup_trans = cleanup_conn.begin()
    cleanup_session = Session(bind=cleanup_conn)
    cleanup_session.execute(delete(Job).where(Job.id == job_id))
    cleanup_trans.commit()
    cleanup_conn.close()


class FailingEmbeddingService:
    def embed(self, text: str) -> list[float]:
        raise RuntimeError("embedding provider unavailable")


def test_embedding_failure_schedules_retry_not_done() -> None:
    obj_id = _persist_object()
    job_id = _persist_enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(obj_id)})
    before = utcnow()
    try:
        assert process_one_job(FailingEmbeddingService())
        stored = _get_job(job_id)
        assert stored is not None
        assert stored.status == JOB_STATUS_PENDING
        assert stored.attempts == 1
        assert stored.run_after > before
        assert stored.last_error == "embedding provider unavailable"
    finally:
        _delete_job(job_id)
        _delete_object(obj_id)


def test_stale_running_job_at_max_attempts_marks_failed(queue) -> None:
    job = queue.enqueue(JOB_TYPE_EMBED_OBJECT, {"object_id": str(uuid.uuid4())})
    claimed = queue.claim_next()
    assert claimed is not None
    stored = queue.get_job(job.id)
    assert stored is not None
    stored.attempts = MAX_JOB_ATTEMPTS
    stored.status = JOB_STATUS_RUNNING
    stored.locked_at = utcnow() - timedelta(minutes=16)

    assert queue.claim_next() is None
    stored = queue.get_job(job.id)
    assert stored is not None
    assert stored.status == JOB_STATUS_FAILED
    assert stored.locked_at is None


"""Unit tests for evidence snippet matching and ranking."""

from app.services.evidence_snippet import (
    build_query_centered_snippet,
    lexical_match_score,
    representation_evidence_rank_key,
)
from app.services.retrieval_query_atoms import probe_atom_selectivity
from app.services.retrieval_service import _best_representation_row
from app.users.bootstrap import BOOTSTRAP_USER_ID


def test_lexical_match_score_weak_partial_does_not_count_as_exact() -> None:
    query = "перед активацией важно исключить split-brain"
    chunk_a = "совершенно unrelated content before важно and after unrelated noise"
    chunk_b = (
        "перед активацией важно исключить split brain related operational guidance "
        "for cluster maintenance"
    )

    exact_a, coverage_a = lexical_match_score(chunk_a, query)
    exact_b, coverage_b = lexical_match_score(chunk_b, query)

    assert exact_a == 0.0
    assert exact_b == 0.0
    assert coverage_b > coverage_a


def test_short_exact_query_centers_far_from_prefix() -> None:
    source = ("x" * 9500) + "\n[slide 115]\nADB\n" + ("y" * 5000)
    snippet = build_query_centered_snippet(source, "ADB", 300)
    assert "ADB" in snippet
    assert not snippet.startswith("x" * 20)


def test_representation_probe_counts_distinct_objects(db_session) -> None:
    from app.api.schemas import ObjectCreate
    from app.db.models import Representation
    from app.services.graph_service import GraphService
    from app.services.representation_service import KIND_CHUNK

    graph = GraphService(db_session, BOOTSTRAP_USER_ID, None)
    obj = graph.create_object(
        ObjectCreate(kind="document", title="probe doc", origin="source", state="observed")
    )
    for index in range(25):
        db_session.add(
            Representation(
                object_id=obj.id,
                kind=KIND_CHUNK,
                text=f"RES_GROUP block {index} " + ("z" * 200),
                part_index=index,
                metadata_={},
            )
        )
    db_session.flush()

    selectivity = probe_atom_selectivity(
        db_session,
        BOOTSTRAP_USER_ID,
        "res_group",
        "",
        {
            "user_id": BOOTSTRAP_USER_ID,
            "kind": None,
            "provider": None,
            "project_id": None,
            "horizon_cutoff": None,
            "date_from": None,
            "date_to": None,
        },
    )
    assert selectivity == 1


def test_representation_evidence_tie_break_is_stable() -> None:
    rows = [
        {
            "text": "shared evidence token alpha beta",
            "kind": "chunk",
            "part_index": 1,
            "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        },
        {
            "text": "shared evidence token alpha beta",
            "kind": "chunk",
            "part_index": 0,
            "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        },
    ]
    first = _best_representation_row(rows, "shared evidence token", None)
    second = _best_representation_row(list(reversed(rows)), "shared evidence token", None)
    assert first is not None
    assert second is not None
    assert first["part_index"] == 0
    assert second["part_index"] == 0
    assert representation_evidence_rank_key(
        text=str(first["text"]),
        query="shared evidence token",
        atoms=None,
        kind=str(first["kind"]),
        part_index=first["part_index"],
        rep_id=str(first["id"]),
    ) == representation_evidence_rank_key(
        text=str(second["text"]),
        query="shared evidence token",
        atoms=None,
        kind=str(second["kind"]),
        part_index=second["part_index"],
        rep_id=str(second["id"]),
    )

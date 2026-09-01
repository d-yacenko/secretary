"""PHASE 27C-R3: explicit local folder intake — one folder Object, no child import."""

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_db, get_embedding_service
from app.db.models import Object, User
from app.llm.embedding_service import FakeEmbeddingService
from app.local.client_paths import compute_client_content_revision
from app.local.constants import PROVIDER_LOCAL_DEVICE
from app.main import app
from app.services.correlation_constants import FOLDER_KIND
from app.services.folder_object_service import (
    EXPLICIT_LOCAL_INTAKE_MODE,
    build_folder_external_id,
)
from app.services.open_target_service import OpenTargetService
from app.services.recent_source_service import RecentSourceService
from app.users.bootstrap import BOOTSTRAP_USER_ID


@pytest.fixture
def phase27c_local_client(db_session, auth_headers, tmp_path: Path):
    from tests.conftest import AuthTestClient

    local_mirror = tmp_path / "local-mirror"
    local_mirror.mkdir()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()
    with (
        patch("app.core.config.settings.local_files_root", str(local_mirror)),
        TestClient(app) as client,
    ):
        yield AuthTestClient(client, auth_headers)
    app.dependency_overrides.clear()


def _folder_payload(
    device_key: str = "desk-local",
    root_path: str = "home/user/projects",
    client_source_path: str = "/home/user/projects",
) -> dict:
    return {
        "device_key": device_key,
        "root_path": root_path,
        "client_source_path": client_source_path,
    }


def _intake_folder(client, **overrides) -> dict:
    payload = _folder_payload(**overrides)
    resp = client.post("/local/folders/client-intake", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _folder_objects(db_session, device_key: str = "desk-local") -> list[Object]:
    return list(
        db_session.scalars(
            select(Object).where(
                Object.user_id == BOOTSTRAP_USER_ID,
                Object.provider == PROVIDER_LOCAL_DEVICE,
                Object.kind == FOLDER_KIND,
                Object.external_id.like(f"folder:{device_key}:%"),
            )
        )
    )


def _child_file_objects(db_session) -> list[Object]:
    return list(
        db_session.scalars(
            select(Object).where(
                Object.user_id == BOOTSTRAP_USER_ID,
                Object.provider == PROVIDER_LOCAL_DEVICE,
                Object.kind == "file",
            )
        )
    )


def _revision(
    source_path: str = "/home/user/notes.md",
    size: int = 12,
    modified_at: str = "2026-01-01T10:00:00Z",
    content_hash: str | None = None,
) -> str:
    return compute_client_content_revision(source_path, size, modified_at, content_hash)


def _file_intake_payload(**overrides) -> dict:
    source_path = overrides.get("source_path", "/home/user/notes.md")
    size = overrides.get("size", 12)
    modified_at = overrides.get("modified_at", "2026-01-01T10:00:00Z")
    content_hash = overrides.get("content_hash")
    base = {
        "device_key": "desk-26b",
        "source_path": source_path,
        "filename": "notes.md",
        "size": size,
        "modified_at": modified_at,
        "content_revision": overrides.get(
            "content_revision",
            _revision(source_path, size, modified_at, content_hash),
        ),
        "representations": [{"kind": "full", "text": "hello world"}],
        "metadata_only": False,
    }
    base.update(overrides)
    return base


def test_explicit_local_folder_intake_creates_one_folder_object(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "my-project"
    folder.mkdir()
    (folder / "readme.md").write_text("hello", encoding="utf-8")

    body = _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=str(folder),
    )

    folders = _folder_objects(db_session)
    assert len(folders) == 1
    assert str(folders[0].id) == body["object_id"]
    assert body["status"] == "created"
    assert folders[0].metadata_["intake_mode"] == EXPLICIT_LOCAL_INTAKE_MODE
    assert folders[0].metadata_["client_source_path"] == str(folder)
    assert _child_file_objects(db_session) == []


def test_empty_folder_still_creates_folder_object(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "empty-dir"
    folder.mkdir()

    body = _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=str(folder),
    )

    folders = _folder_objects(db_session)
    assert len(folders) == 1
    assert str(folders[0].id) == body["object_id"]
    assert _child_file_objects(db_session) == []


def test_folder_with_many_files_creates_only_folder_object(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "big-dir"
    folder.mkdir()
    for i in range(120):
        (folder / f"file-{i}.txt").write_text(f"content-{i}", encoding="utf-8")

    _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=str(folder),
    )

    assert len(_folder_objects(db_session)) == 1
    assert _child_file_objects(db_session) == []


def test_repeated_same_folder_returns_same_object(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "repeat-dir"
    folder.mkdir()

    first = _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=str(folder),
    )
    second = _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=str(folder),
    )

    assert second["object_id"] == first["object_id"]
    assert second["status"] == "unchanged"
    assert len(_folder_objects(db_session)) == 1


def test_normalized_root_path_is_idempotent(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "norm-dir"
    folder.mkdir()
    rel = str(folder.relative_to(tmp_path))

    first = _intake_folder(
        phase27c_local_client,
        root_path=f"/{rel}",
        client_source_path=str(folder),
    )
    second = _intake_folder(
        phase27c_local_client,
        root_path=rel.replace("/", "\\"),
        client_source_path=str(folder),
    )

    assert second["object_id"] == first["object_id"]
    assert len(_folder_objects(db_session)) == 1


def test_cross_user_isolation(
    db_session, issue_bearer, tmp_path: Path
) -> None:
    from tests.conftest import AuthTestClient

    other_user = uuid.uuid4()
    db_session.add(User(id=other_user, display_name="other"))
    db_session.flush()

    local_mirror = tmp_path / "mirror"
    local_mirror.mkdir()
    folder = tmp_path / "shared-name"
    folder.mkdir()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingService()

    with (
        patch("app.core.config.settings.local_files_root", str(local_mirror)),
        TestClient(app) as raw,
    ):
        bootstrap_client = AuthTestClient(
            raw,
            {"Authorization": f"Bearer {issue_bearer(BOOTSTRAP_USER_ID)}"},
        )
        other_client = AuthTestClient(
            raw,
            {"Authorization": f"Bearer {issue_bearer(other_user)}"},
        )

        bootstrap_body = _intake_folder(
            bootstrap_client,
            root_path=str(folder.relative_to(tmp_path)),
            client_source_path=str(folder),
        )
        other_body = _intake_folder(
            other_client,
            root_path=str(folder.relative_to(tmp_path)),
            client_source_path=str(folder),
        )

    app.dependency_overrides.clear()

    assert bootstrap_body["object_id"] != other_body["object_id"]
    bootstrap_obj = db_session.get(Object, uuid.UUID(bootstrap_body["object_id"]))
    other_obj = db_session.get(Object, uuid.UUID(other_body["object_id"]))
    assert bootstrap_obj is not None and other_obj is not None
    assert bootstrap_obj.user_id == BOOTSTRAP_USER_ID
    assert other_obj.user_id == other_user


def test_client_source_path_preserved(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "client-path-dir"
    folder.mkdir()
    client_path = str(folder)

    _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=client_path,
    )

    obj = _folder_objects(db_session)[0]
    assert obj.metadata_["client_source_path"] == client_path


def test_local_folder_open_target_uses_client_source_path(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "open-target-dir"
    folder.mkdir()
    client_path = str(folder)

    body = _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=client_path,
    )

    target = OpenTargetService(db_session, BOOTSTRAP_USER_ID).resolve(
        uuid.UUID(body["object_id"])
    )
    assert target.available is True
    assert target.action == "local_folder"
    assert target.local_path == client_path
    assert target.device_key == "desk-local"


def test_local_folder_visible_in_recent_source_feed(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "inbox-dir"
    folder.mkdir()

    _intake_folder(
        phase27c_local_client,
        root_path=str(folder.relative_to(tmp_path)),
        client_source_path=str(folder),
    )

    obj = _folder_objects(db_session)[0]
    assert obj.origin == "source"
    assert obj.state == "observed"

    titles = {row.title for row in RecentSourceService(db_session, BOOTSTRAP_USER_ID).list_recent()}
    assert obj.title in titles


def test_existing_local_single_file_intake_regression(
    phase27c_local_client, db_session
) -> None:
    resp = phase27c_local_client.post(
        "/local/devices/register",
        json={"device_key": "desk-26b", "display_name": "Test desktop"},
    )
    assert resp.status_code == 201

    intake_resp = phase27c_local_client.post(
        "/local/files/client-intake",
        json=_file_intake_payload(),
    )
    assert intake_resp.status_code == 201
    body = intake_resp.json()
    obj = db_session.get(Object, uuid.UUID(body["object_id"]))
    assert obj is not None
    assert obj.kind in {"file", "document"}


def test_folder_external_id_matches_canonical_identity(
    phase27c_local_client, db_session, tmp_path: Path
) -> None:
    folder = tmp_path / "canonical-dir"
    folder.mkdir()
    rel = str(folder.relative_to(tmp_path))

    body = _intake_folder(
        phase27c_local_client,
        root_path=rel,
        client_source_path=str(folder),
    )

    obj = db_session.get(Object, uuid.UUID(body["object_id"]))
    assert obj is not None
    expected_external = build_folder_external_id("desk-local", rel)
    assert obj.external_id == expected_external
    assert obj.provider == PROVIDER_LOCAL_DEVICE
    assert obj.kind == FOLDER_KIND

    count = db_session.scalar(
        select(func.count())
        .select_from(Object)
        .where(
            Object.user_id == BOOTSTRAP_USER_ID,
            Object.provider == PROVIDER_LOCAL_DEVICE,
            Object.external_id == expected_external,
        )
    )
    assert count == 1

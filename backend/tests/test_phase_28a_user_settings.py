"""PHASE 28A — user profile and per-user settings foundation."""

import uuid
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import User, UserOpenAICredential, UserSettings
from app.main import app
from app.services.assistant_service import create_assistant_provider_from_effective
from app.services.effective_user_settings_service import EffectiveUserSettingsService
from app.users.bootstrap import BOOTSTRAP_USER_ID
from tests.conftest import AuthTestClient


def _credential_key() -> str:
    return Fernet.generate_key().decode("utf-8")


@pytest.fixture
def credential_key(monkeypatch) -> str:
    key = _credential_key()
    monkeypatch.setattr(settings, "secretary_credential_key", key)
    return key


@pytest.fixture
def profile_client(db_session, auth_headers, credential_key):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as raw:
        yield AuthTestClient(raw, auth_headers)
    app.dependency_overrides.clear()


@pytest.fixture
def second_user(db_session) -> tuple[UUID, dict[str, str]]:
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, display_name="Second user"))
    db_session.flush()
    from app.auth.token_service import AuthTokenService

    service = AuthTokenService(db_session)
    token, _ = service.issue_token(user_id, label="pytest-second")
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, headers


def test_user_without_settings_gets_deployment_defaults(profile_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_assistant_model", "gpt-5.6-luna")
    monkeypatch.setattr(settings, "openai_assistant_reasoning_effort", "low")
    monkeypatch.setattr(settings, "openai_assistant_verbosity", "medium")
    monkeypatch.setattr(settings, "secretary_timezone", "Europe/Moscow")
    response = profile_client.get("/me/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Europe/Moscow"
    assert body["assistant_model"] == "gpt-5.6-luna"
    assert body["assistant_reasoning_effort"] == "low"
    assert body["assistant_verbosity"] == "medium"
    assert body["openai_key_configured"] is False
    assert "gpt-5.6-luna" in body["allowed_assistant_models"]


def test_settings_row_one_per_user(profile_client, db_session) -> None:
    profile_client.patch("/me/settings", json={"timezone": "Europe/Amsterdam"})
    rows = db_session.scalars(select(UserSettings)).all()
    bootstrap_rows = [row for row in rows if row.user_id == BOOTSTRAP_USER_ID]
    assert len(bootstrap_rows) == 1


def test_patch_settings_updates_current_user_only(
    profile_client, db_session, second_user, credential_key
) -> None:
    user_b_id, user_b_headers = second_user
    profile_client.patch("/me/settings", json={"timezone": "Asia/Yekaterinburg"})
    response_b = profile_client.get("/me/settings", headers=user_b_headers)
    assert response_b.status_code == 200
    assert response_b.json()["timezone"] == settings.secretary_timezone
    row_a = db_session.get(UserSettings, BOOTSTRAP_USER_ID)
    row_b = db_session.get(UserSettings, user_b_id)
    assert row_a is not None
    assert row_a.timezone == "Asia/Yekaterinburg"
    assert row_b is None


def test_patch_me_updates_display_name(profile_client) -> None:
    response = profile_client.patch("/me", json={"display_name": "Новое имя"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Новое имя"
    me = profile_client.get("/me")
    assert me.json()["display_name"] == "Новое имя"


def test_patch_me_cannot_modify_other_user(profile_client, second_user) -> None:
    _, user_b_headers = second_user
    profile_client.patch("/me", json={"display_name": "User A name"})
    response = profile_client.get("/me", headers=user_b_headers)
    assert response.json()["display_name"] == "Second user"


def test_valid_timezone_accepted(profile_client) -> None:
    response = profile_client.patch("/me/settings", json={"timezone": "Europe/Amsterdam"})
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Amsterdam"


def test_invalid_timezone_rejected(profile_client) -> None:
    response = profile_client.patch("/me/settings", json={"timezone": "Not/AZone"})
    assert response.status_code == 422


def test_assistant_model_outside_allowlist_rejected(profile_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_assistant_model", "gpt-5.6-luna")
    monkeypatch.setattr(settings, "openai_allowed_assistant_models", "gpt-5.6-luna")
    response = profile_client.patch(
        "/me/settings",
        json={"assistant_model": "gpt-5.6-terra"},
    )
    assert response.status_code == 422


def test_reasoning_validation(profile_client) -> None:
    bad = profile_client.patch("/me/settings", json={"assistant_reasoning_effort": "turbo"})
    assert bad.status_code == 422
    good = profile_client.patch("/me/settings", json={"assistant_reasoning_effort": "high"})
    assert good.status_code == 200
    assert good.json()["assistant_reasoning_effort"] == "high"


def test_verbosity_validation(profile_client) -> None:
    bad = profile_client.patch("/me/settings", json={"assistant_verbosity": "verbose"})
    assert bad.status_code == 422
    good = profile_client.patch("/me/settings", json={"assistant_verbosity": "medium"})
    assert good.status_code == 200
    assert good.json()["assistant_verbosity"] == "medium"


def test_openai_key_stored_encrypted(profile_client, db_session) -> None:
    plaintext = "sk-user-test-key-28a"
    response = profile_client.put("/me/credentials/openai", json={"api_key": plaintext})
    assert response.status_code == 200
    row = db_session.get(UserOpenAICredential, BOOTSTRAP_USER_ID)
    assert row is not None
    assert row.api_key_encrypted != plaintext
    assert "sk-user" not in row.api_key_encrypted


def test_get_settings_never_returns_plaintext_key(profile_client) -> None:
    profile_client.put("/me/credentials/openai", json={"api_key": "sk-secret-user-key"})
    response = profile_client.get("/me/settings")
    body = response.json()
    assert "api_key" not in body
    assert "sk-secret" not in str(body)


def test_put_key_returns_configured_only(profile_client) -> None:
    response = profile_client.put("/me/credentials/openai", json={"api_key": "sk-test"})
    assert response.status_code == 200
    assert response.json() == {"configured": True}


def test_replacing_openai_key_works(profile_client, db_session, credential_key) -> None:
    profile_client.put("/me/credentials/openai", json={"api_key": "sk-first"})
    profile_client.put("/me/credentials/openai", json={"api_key": "sk-second"})
    store = EffectiveUserSettingsService.build(db_session)
    effective = store.get_effective_settings(BOOTSTRAP_USER_ID)
    assert effective.openai_api_key == "sk-second"


def test_deleting_openai_key_works(profile_client, db_session) -> None:
    profile_client.put("/me/credentials/openai", json={"api_key": "sk-delete-me"})
    response = profile_client.delete("/me/credentials/openai")
    assert response.status_code == 200
    assert response.json() == {"configured": False}
    assert db_session.get(UserOpenAICredential, BOOTSTRAP_USER_ID) is None
    settings_resp = profile_client.get("/me/settings")
    assert settings_resp.json()["openai_key_configured"] is False


def test_user_key_overrides_deployment_fallback(
    profile_client, db_session, monkeypatch, credential_key
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "sk-deployment")
    profile_client.put("/me/credentials/openai", json={"api_key": "sk-user"})
    service = EffectiveUserSettingsService.build(db_session)
    effective = service.get_effective_settings(BOOTSTRAP_USER_ID)
    assert effective.openai_api_key == "sk-user"


def test_no_user_key_falls_back_to_deployment(
    profile_client, db_session, monkeypatch, credential_key
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "sk-deployment-only")
    service = EffectiveUserSettingsService.build(db_session)
    effective = service.get_effective_settings(BOOTSTRAP_USER_ID)
    assert effective.openai_api_key == "sk-deployment-only"


def test_user_a_credential_not_used_for_user_b(
    profile_client, db_session, second_user, monkeypatch, credential_key
) -> None:
    user_b_id, _ = second_user
    monkeypatch.setattr(settings, "openai_api_key", "sk-deployment")
    profile_client.put("/me/credentials/openai", json={"api_key": "sk-user-a"})
    service = EffectiveUserSettingsService.build(db_session)
    effective_b = service.get_effective_settings(user_b_id)
    assert effective_b.openai_api_key == "sk-deployment"
    assert effective_b.openai_key_configured is False


def test_create_assistant_provider_from_effective_uses_user_settings(
    db_session, monkeypatch, credential_key
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "sk-deployment")
    service = EffectiveUserSettingsService.build(db_session)
    service.update_settings(
        BOOTSTRAP_USER_ID,
        assistant_reasoning_effort="medium",
        assistant_verbosity="high",
    )
    service._credential_store.upsert(BOOTSTRAP_USER_ID, "sk-user-assistant")
    effective = service.get_effective_settings(BOOTSTRAP_USER_ID)
    provider = create_assistant_provider_from_effective(effective)
    assert provider._model == effective.assistant_model
    assert provider._reasoning_effort == "medium"
    assert provider._verbosity == "high"


def test_create_assistant_provider_from_effective_without_key_raises(
    db_session, monkeypatch, credential_key
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = EffectiveUserSettingsService.build(db_session)
    effective = service.get_effective_settings(BOOTSTRAP_USER_ID)
    from app.services.assistant_service import AssistantConfigurationError

    with pytest.raises(AssistantConfigurationError):
        create_assistant_provider_from_effective(effective)

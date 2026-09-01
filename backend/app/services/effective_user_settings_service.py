from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.assistant_openai_config import (
    AssistantOpenAIConfigError,
    validate_assistant_model,
    validate_assistant_reasoning_effort,
    validate_assistant_verbosity,
    validated_assistant_openai_settings,
)
from app.core.config import settings
from app.db.models import UserSettings
from app.services.errors import ValidationError
from app.services.user_openai_credential_store import UserOpenAICredentialStore


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class EffectiveUserSettings:
    timezone: str
    assistant_model: str
    assistant_reasoning_effort: str
    assistant_verbosity: str
    openai_api_key: str | None
    openai_key_configured: bool
    allowed_assistant_models: list[str]


class EffectiveUserSettingsService:
    def __init__(
        self,
        session: Session,
        credential_store: UserOpenAICredentialStore,
    ) -> None:
        self._session = session
        self._credential_store = credential_store

    def get_effective_settings(self, user_id: UUID) -> EffectiveUserSettings:
        deployment = validated_assistant_openai_settings(settings)
        row = self._session.get(UserSettings, user_id)
        timezone = self._resolve_timezone(row)
        assistant_model = (
            row.assistant_model.strip()
            if row is not None and row.assistant_model
            else deployment.model
        )
        assistant_reasoning_effort = (
            row.assistant_reasoning_effort.strip().lower()
            if row is not None and row.assistant_reasoning_effort
            else deployment.reasoning_effort
        )
        assistant_verbosity = (
            row.assistant_verbosity.strip().lower()
            if row is not None and row.assistant_verbosity
            else deployment.verbosity
        )
        user_key = self._credential_store.get_api_key(user_id)
        openai_key_configured = user_key is not None
        deployment_key = settings.openai_api_key.strip() or None
        resolved_key = user_key or deployment_key
        allowed_models = settings.allowed_assistant_models
        return EffectiveUserSettings(
            timezone=timezone,
            assistant_model=assistant_model,
            assistant_reasoning_effort=assistant_reasoning_effort,
            assistant_verbosity=assistant_verbosity,
            openai_api_key=resolved_key,
            openai_key_configured=openai_key_configured,
            allowed_assistant_models=list(allowed_models),
        )

    def get_or_create_settings_row(self, user_id: UUID) -> UserSettings:
        row = self._session.get(UserSettings, user_id)
        if row is None:
            row = UserSettings(user_id=user_id)
            self._session.add(row)
            self._session.flush()
        return row

    def update_settings(
        self,
        user_id: UUID,
        timezone: str | None = None,
        assistant_model: str | None = None,
        assistant_reasoning_effort: str | None = None,
        assistant_verbosity: str | None = None,
    ) -> EffectiveUserSettings:
        row = self.get_or_create_settings_row(user_id)
        allowed_models = settings.allowed_assistant_models
        if timezone is not None:
            self._validate_timezone(timezone)
            row.timezone = timezone.strip()
        if assistant_model is not None:
            try:
                row.assistant_model = validate_assistant_model(
                    assistant_model, allowed_models
                )
            except AssistantOpenAIConfigError as exc:
                raise ValidationError(str(exc)) from exc
        if assistant_reasoning_effort is not None:
            try:
                row.assistant_reasoning_effort = validate_assistant_reasoning_effort(
                    assistant_reasoning_effort
                )
            except AssistantOpenAIConfigError as exc:
                raise ValidationError(str(exc)) from exc
        if assistant_verbosity is not None:
            try:
                row.assistant_verbosity = validate_assistant_verbosity(assistant_verbosity)
            except AssistantOpenAIConfigError as exc:
                raise ValidationError(str(exc)) from exc
        row.updated_at = utcnow()
        self._session.flush()
        return self.get_effective_settings(user_id)

    def _resolve_timezone(self, row: UserSettings | None) -> str:
        if row is not None and row.timezone:
            return row.timezone.strip()
        server_tz = settings.secretary_timezone.strip()
        return server_tz if server_tz else "Europe/Amsterdam"

    def _validate_timezone(self, timezone: str) -> str:
        text = timezone.strip()
        if not text:
            raise ValidationError("timezone cannot be blank")
        try:
            ZoneInfo(text)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValidationError(f"invalid timezone: {timezone}") from exc
        return text

    @staticmethod
    def build(session: Session) -> EffectiveUserSettingsService:
        credential_store = UserOpenAICredentialStore.build_from_settings(session)
        return EffectiveUserSettingsService(session, credential_store)

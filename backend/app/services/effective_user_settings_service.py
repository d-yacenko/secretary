from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.assistant_openai_config import (
    ALLOWED_ASSISTANT_REASONING_EFFORTS,
    ALLOWED_ASSISTANT_VERBOSITY,
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
    openai_key_configured: bool
    allowed_assistant_models: list[str]
    openai_api_key: str | None = field(default=None, repr=False)


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
        allowed_models = list(settings.allowed_assistant_models)
        timezone = self._resolve_timezone(row)
        assistant_model = self._resolve_assistant_model(row, deployment.model, allowed_models)
        assistant_reasoning_effort = self._resolve_reasoning_effort(
            row, deployment.reasoning_effort
        )
        assistant_verbosity = self._resolve_verbosity(row, deployment.verbosity)
        openai_key_configured = self._credential_store.is_configured(user_id)
        resolved_key = self._resolve_openai_api_key(user_id, openai_key_configured)
        return EffectiveUserSettings(
            timezone=timezone,
            assistant_model=assistant_model,
            assistant_reasoning_effort=assistant_reasoning_effort,
            assistant_verbosity=assistant_verbosity,
            openai_key_configured=openai_key_configured,
            allowed_assistant_models=allowed_models,
            openai_api_key=resolved_key,
        )

    def get_settings_view(self, user_id: UUID) -> EffectiveUserSettings:
        """Safe settings for GET /me/settings — never decrypts stored credentials."""
        deployment = validated_assistant_openai_settings(settings)
        row = self._session.get(UserSettings, user_id)
        allowed_models = list(settings.allowed_assistant_models)
        openai_key_configured = self._credential_store.is_configured(user_id)
        return EffectiveUserSettings(
            timezone=self._resolve_timezone(row),
            assistant_model=self._resolve_assistant_model(row, deployment.model, allowed_models),
            assistant_reasoning_effort=self._resolve_reasoning_effort(
                row, deployment.reasoning_effort
            ),
            assistant_verbosity=self._resolve_verbosity(row, deployment.verbosity),
            openai_key_configured=openai_key_configured,
            allowed_assistant_models=allowed_models,
            openai_api_key=None,
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
        return self.get_settings_view(user_id)

    def resolve_openai_api_key(self, user_id: UUID) -> str | None:
        """Resolve decrypted OpenAI API key without creating a settings row."""
        return self._resolve_openai_api_key(
            user_id,
            self._credential_store.is_configured(user_id),
        )

    def _resolve_openai_api_key(
        self,
        user_id: UUID,
        openai_key_configured: bool,
    ) -> str | None:
        if openai_key_configured:
            return self._credential_store.get_api_key(user_id)
        deployment_key = settings.openai_api_key.strip() or None
        return deployment_key

    def _resolve_assistant_model(
        self,
        row: UserSettings | None,
        deployment_model: str,
        allowed_models: list[str],
    ) -> str:
        if row is not None and row.assistant_model:
            stored = row.assistant_model.strip()
            if stored in allowed_models:
                return stored
        return deployment_model

    def _resolve_reasoning_effort(
        self,
        row: UserSettings | None,
        deployment_effort: str,
    ) -> str:
        if row is not None and row.assistant_reasoning_effort:
            stored = row.assistant_reasoning_effort.strip().lower()
            if stored in ALLOWED_ASSISTANT_REASONING_EFFORTS:
                return stored
        return deployment_effort

    def _resolve_verbosity(
        self,
        row: UserSettings | None,
        deployment_verbosity: str,
    ) -> str:
        if row is not None and row.assistant_verbosity:
            stored = row.assistant_verbosity.strip().lower()
            if stored in ALLOWED_ASSISTANT_VERBOSITY:
                return stored
        return deployment_verbosity

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

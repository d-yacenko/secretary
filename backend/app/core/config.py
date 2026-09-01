from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SOURCE_SYNC_INTERVAL_SECONDS = 60


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "secretary"
    postgres_user: str = "secretary"
    postgres_password: str = "secretary"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_model: str = "gpt-5.6-terra"
    openai_assistant_model: str = "gpt-5.6-luna"
    openai_assistant_reasoning_effort: str = "low"
    openai_assistant_verbosity: str = "low"
    openai_assistant_max_output_tokens: int = 1600
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    secretary_timezone: str = "Europe/Amsterdam"
    mcp_enabled: bool = False
    google_oauth_client_file: str = "/run/secrets/google-oauth-client.json"
    google_redirect_uri: str = "http://localhost:18080/auth/google/callback"
    secretary_credential_key: str = ""
    gmail_sync_default_limit: int = 50
    gmail_sync_max_limit: int = 100
    gmail_sync_days: int = 30
    calendar_sync_days_back: int = 60
    calendar_sync_days_forward: int = 90
    calendar_sync_default_limit: int = 100
    calendar_sync_max_limit: int = 100
    calendar_sync_max_calendars: int = 10
    google_drive_max_items_per_run: int = 500
    yandex_mail_sync_days: int = 30
    yandex_mail_sync_default_limit: int = 50
    yandex_mail_sync_max_limit: int = 100
    mattermost_allowed_base_urls: str = ""
    mattermost_sync_days: int = 14
    mattermost_sync_max_channels: int = 50
    mattermost_sync_initial_posts_per_channel: int = 100
    mattermost_sync_max_posts_per_run: int = 500
    mattermost_sync_overlap_seconds: int = 300
    source_sync_gmail_interval_seconds: int = 120
    source_sync_yandex_mail_interval_seconds: int = 120
    source_sync_google_calendar_interval_seconds: int = 300
    source_sync_google_drive_interval_seconds: int = 300
    source_sync_yandex_calendar_interval_seconds: int = 300
    source_sync_mattermost_interval_seconds: int = 120
    source_sync_scheduler_interval_seconds: int = 60
    source_sync_failed_rearm_seconds: int = 3600
    resource_upload_root: str = "/var/lib/secretary/resources"
    local_files_root: str = "/var/lib/secretary/local-files"

    @field_validator(
        "source_sync_gmail_interval_seconds",
        "source_sync_yandex_mail_interval_seconds",
        "source_sync_google_calendar_interval_seconds",
        "source_sync_google_drive_interval_seconds",
        "source_sync_yandex_calendar_interval_seconds",
        "source_sync_mattermost_interval_seconds",
    )
    @classmethod
    def _validate_source_sync_interval(cls, value: int) -> int:
        if value < MIN_SOURCE_SYNC_INTERVAL_SECONDS:
            raise ValueError(
                f"source sync interval must be >= {MIN_SOURCE_SYNC_INTERVAL_SECONDS} seconds"
            )
        return value

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    yandex_mail_sync_days: int = 30
    yandex_mail_sync_default_limit: int = 50
    yandex_mail_sync_max_limit: int = 100
    resource_upload_root: str = "/var/lib/secretary/resources"
    local_files_root: str = "/var/lib/secretary/local-files"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

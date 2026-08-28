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

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()

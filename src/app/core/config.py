from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path
from pydantic import PostgresDsn, Field


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    POSTGRES_DB: str
    POSTGRES_DB_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    DATABASE_URL: PostgresDsn = Field(..., env="DATABASE_URL")

    SECRET_KEY_ACCESS: str
    SECRET_KEY_REFRESH: str
    JWT_SIGNING_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    EMAIL_USE_TLS: bool

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: Optional[str] = None

    DEFAULT_GROUP_ID: int = 1
    BACKEND_URL: str

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_DB_PORT}/"
            f"{self.POSTGRES_DB}"
        )


settings = Settings()

from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=True,
        extra="ignore",
    )

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    PROVIDER_URL: str = 'http://provider-simulator:8081'
    PROVIDER_TIMEOUT_SECONDS: float = 5.0
    LOG_LEVEL: Literal['DEBUG', 'INFO',
                       'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG'

    RETRY_BASE_DELAY: float = 2.0
    RETRY_MAX_DELAY: float = 8.0
    RETRY_JITTER_MAX: float = 0.5
    RETRY_MAX_ATTEMPTS: int = 10
    WORKER_POLL_INTERVAL: float = 1.0
    INTENT_STALE_SECONDS: float = 60.0

    LOG_JSON: bool = False

    METRICS_POLL_INTERVAL: int = 30

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @computed_field
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()

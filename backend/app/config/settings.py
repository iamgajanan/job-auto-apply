from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]

ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    APP_NAME: str

    APP_ENV: str

    DATABASE_URL: str

    REDIS_URL: str

    JWT_SECRET: str

    BACKEND_HOST: str

    BACKEND_PORT: int

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore"
    )


settings = Settings()
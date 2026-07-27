from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]
class Settings(BaseSettings):
    APP_NAME: str
    APP_ENV: str

    DATABASE_URL: str
    REDIS_URL: str

    BACKEND_HOST: str
    BACKEND_PORT: int

    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

settings = Settings()
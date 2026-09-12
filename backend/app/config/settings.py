from pathlib import Path
from typing import Self
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str = "Job Auto Apply"
    APP_ENV: str = "production"

    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_URL: str = ""

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = Field(default=8004, ge=1, le=65535)

    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    CORS_ORIGINS: str = "http://localhost:3000"
    SCRAPER_PROXY_URL: str = ""

    @property
    def supabase_auth_key(self) -> str:
        return self.SUPABASE_PUBLISHABLE_KEY or self.SUPABASE_ANON_KEY

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @staticmethod
    def _validate_url(value: str, field_name: str, allowed_schemes: set[str]) -> None:
        if not value:
            return
        parsed = urlparse(value)
        if parsed.scheme not in allowed_schemes or not parsed.netloc:
            schemes = ", ".join(sorted(allowed_schemes))
            raise ValueError(f"{field_name} must be a valid URL using: {schemes}")

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        if self.APP_ENV not in {"development", "test", "staging", "production"}:
            raise ValueError("APP_ENV must be development, test, staging, or production")

        self._validate_url(self.REDIS_URL, "REDIS_URL", {"redis", "rediss"})
        self._validate_url(self.SUPABASE_URL, "SUPABASE_URL", {"http", "https"})
        self._validate_url(self.SCRAPER_PROXY_URL, "SCRAPER_PROXY_URL", {"http", "https", "socks5"})

        if not self.supabase_auth_key and self.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY requires SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY")

        if not self.cors_origins_list:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        if any(origin == "*" for origin in self.cors_origins_list) and self.APP_ENV == "production":
            raise ValueError("Wildcard CORS_ORIGINS is not allowed in production")

        return self

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


settings = Settings()

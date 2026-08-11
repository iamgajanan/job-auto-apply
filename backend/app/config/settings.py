from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    APP_NAME: str
    APP_ENV: str

    REDIS_URL: str

    DATABASE_URL: str = ""

    BACKEND_HOST: str
    BACKEND_PORT: int

    # Legacy app JWT settings are kept for compatibility with existing config.
    # User authentication is handled by Supabase Auth and its access tokens.
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Supabase Auth
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""

    # Razorpay. Secrets stay on the Raspberry Pi runtime and are never sent to the frontend.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Comma-separated list, e.g. "http://localhost:3000,https://app.example.com"
    CORS_ORIGINS: str = "http://localhost:3000"

    # Optional HTTP(S) proxy for Naukri/LinkedIn scraping.
    SCRAPER_PROXY_URL: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


settings = Settings()

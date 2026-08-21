from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config.settings import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create the application database engine lazily with a reusable pool."""
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")

    return create_engine(
        url,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        pool_recycle=1800,
        pool_pre_ping=True,
    )


def check_database_connection() -> bool:
    """Return True only when the configured Postgres database is reachable."""
    engine = get_engine()
    with engine.connect() as connection:
        return connection.execute(text("select 1")).scalar_one() == 1

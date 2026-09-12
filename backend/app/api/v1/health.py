from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.db.connection import check_database_connection

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


def _check_redis_connection() -> bool:
    """Check Redis with a short-lived client so health probes cannot reuse stale state."""
    import redis

    client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )
    try:
        return client.ping() is True
    finally:
        client.close()


@router.get("")
def liveness() -> dict[str, str]:
    """Process liveness probe; does not require external dependencies."""
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> JSONResponse:
    """Dependency readiness probe with bounded database and Redis checks."""
    checks: dict[str, str] = {}

    try:
        checks["database"] = "ok" if check_database_connection() else "failed"
    except Exception:
        checks["database"] = "failed"

    try:
        checks["redis"] = "ok" if _check_redis_connection() else "failed"
    except Exception:
        checks["redis"] = "failed"

    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "not_ready", "checks": checks},
    )


@router.get("/database")
def database_health() -> JSONResponse:
    try:
        check_database_connection()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "failed", "database": "unavailable"},
        )

    return JSONResponse(status_code=200, content={"status": "ok", "database": "connected"})

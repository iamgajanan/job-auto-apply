"""Simple Redis-backed rate limiter as a FastAPI dependency.

Usage:
    @router.post("/login")
    def login(request: LoginRequest, _: None = Depends(auth_rate_limit)):
        ...
"""
from __future__ import annotations

import logging

import redis
from fastapi import Depends, HTTPException, Request

from app.config.settings import settings

logger = logging.getLogger(__name__)

# Shared Redis pool (lazy init, same pattern as auth cache).
_redis_pool: redis.ConnectionPool | None = None
_redis_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _redis_pool, _redis_client
    if _redis_client is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_client = redis.Redis(connection_pool=_redis_pool)
    return _redis_client


def _check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Increment the counter for `key`; raise 429 if limit is exceeded.

    Uses a simple sliding-window counter backed by Redis INCR + EXPIRE.
    On Redis failure the check is skipped (fail-open) so an outage doesn't
    lock every user out.
    """
    try:
        client = _redis()
        current = client.incr(key)
        if current == 1:
            client.expire(key, window_seconds)
        if current > limit:
            ttl = max(client.ttl(key), 1)
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {ttl} seconds.",
                headers={"Retry-After": str(ttl)},
            )
    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.warning("Rate limit Redis error (fail-open): %s", exc)


class AuthRateLimiter:
    """5 attempts per IP per minute on auth endpoints (login / signup)."""

    LIMIT = 5
    WINDOW = 60  # seconds

    def __call__(self, request: Request) -> None:
        client_ip = (request.client.host if request.client else "unknown").replace(":", "_")
        path_slug = request.url.path.replace("/", "_").strip("_")
        key = f"rl:auth:{path_slug}:{client_ip}"
        _check_rate_limit(key, self.LIMIT, self.WINDOW)


class PasswordResetRateLimiter:
    """3 password-reset emails per IP per 10 minutes — prevents email flooding."""

    LIMIT = 3
    WINDOW = 600  # 10 minutes

    def __call__(self, request: Request) -> None:
        client_ip = (request.client.host if request.client else "unknown").replace(":", "_")
        key = f"rl:pwreset:{client_ip}"
        _check_rate_limit(key, self.LIMIT, self.WINDOW)


# Singleton instances used as FastAPI dependencies.
auth_rate_limit = AuthRateLimiter()
password_reset_rate_limit = PasswordResetRateLimiter()

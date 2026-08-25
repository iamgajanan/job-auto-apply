from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.auth.schemas import CurrentUser, UserProfile
from app.auth.service import SupabaseAuthError, auth_service
from app.config.settings import settings
from app.db.connection import get_engine

logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

# ── Redis-backed caches (shared across all uvicorn workers) ───────────────────
# Previously these were module-level dicts, which meant each worker had its own
# isolated cache and logout in worker A would not invalidate worker B's cache.
# Moving to Redis fixes both the stale-cache and the logout-race bugs.

AUTH_CACHE_TTL_SECONDS     = 60      # seconds to cache Supabase token validation
PROFILE_CACHE_TTL_SECONDS  = 30      # seconds to cache DB profile row

_redis_pool: redis.ConnectionPool | None = None
_redis_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    """Return a shared Redis client, creating the pool lazily on first use.

    A lazy init means the app still starts even if Redis is temporarily
    unavailable — the first authenticated request will fail fast with a
    503 instead of crashing the entire process at import time.
    """
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


def _auth_cache_key(token: str) -> str:
    # Store only first 16 chars of token in the key to avoid huge Redis keys
    # while keeping enough entropy to be unique.
    return f"auth:token:{token[:64]}"


def _profile_cache_key(user_id: str) -> str:
    return f"auth:profile:{user_id}"


def _cache_get(token: str) -> dict[str, Any] | None:
    try:
        raw = _redis().get(_auth_cache_key(token))
        return json.loads(raw) if raw else None
    except redis.RedisError as exc:
        logger.warning("Auth cache GET failed (Redis): %s", exc)
        return None


def _cache_put(token: str, user: dict[str, Any]) -> None:
    try:
        _redis().setex(
            _auth_cache_key(token),
            AUTH_CACHE_TTL_SECONDS,
            json.dumps(user, default=str),
        )
    except redis.RedisError as exc:
        logger.warning("Auth cache SET failed (Redis): %s", exc)


def _profile_cache_get(user_id: UUID) -> UserProfile | None:
    try:
        raw = _redis().get(_profile_cache_key(str(user_id)))
        if raw:
            return UserProfile(**json.loads(raw))
        return None
    except (redis.RedisError, Exception) as exc:
        logger.warning("Profile cache GET failed: %s", exc)
        return None


def _profile_cache_put(profile: UserProfile) -> None:
    try:
        _redis().setex(
            _profile_cache_key(profile.id),
            PROFILE_CACHE_TTL_SECONDS,
            profile.model_dump_json(),
        )
    except redis.RedisError as exc:
        logger.warning("Profile cache SET failed (Redis): %s", exc)


def invalidate_auth_cache(token: str) -> None:
    try:
        _redis().delete(_auth_cache_key(token))
    except redis.RedisError as exc:
        logger.warning("Auth cache DELETE failed (Redis): %s", exc)


def invalidate_profile_cache(user_id: str | UUID) -> None:
    try:
        _redis().delete(_profile_cache_key(str(user_id)))
    except redis.RedisError as exc:
        logger.warning("Profile cache DELETE failed (Redis): %s", exc)


def _http_error(exc: SupabaseAuthError) -> HTTPException:
    if exc.status_code in (401, 403):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if exc.status_code == 429:
        return HTTPException(status_code=429, detail="Too many authentication requests")
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def load_profile(user_id: UUID, email: str | None, full_name: str | None) -> UserProfile:
    """Read an existing profile; upsert on first login."""
    with get_engine().connect() as connection:
        row = connection.execute(text("""
            select id, email, full_name, role, status, plan_code
            from public.profiles
            where id = :id
        """), {"id": str(user_id)}).mappings().one_or_none()
        if row:
            data = dict(row)
            data["id"] = str(data["id"])
            profile = UserProfile(**data)
            _profile_cache_put(profile)
            return profile

    with get_engine().begin() as connection:
        row = connection.execute(text("""
            insert into public.profiles (id, email, full_name, role, status, plan_code)
            values (:id, :email, :full_name,
                case when exists (
                    select 1 from public.admin_allowlist
                    where lower(email) = lower(:email) and is_active = true
                ) then 'super_admin' else 'user' end,
                'active', 'free')
            on conflict (id) do update
            set email      = coalesce(excluded.email,      public.profiles.email),
                full_name  = coalesce(excluded.full_name,  public.profiles.full_name),
                role       = excluded.role,
                updated_at = timezone('utc', now())
            returning id, email, full_name, role, status, plan_code
        """), {"id": str(user_id), "email": email, "full_name": full_name}).mappings().one()
    data = dict(row)
    data["id"] = str(data["id"])
    profile = UserProfile(**data)
    _profile_cache_put(profile)
    return profile


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    auth_user = _cache_get(token)
    if auth_user is None:
        try:
            auth_user = auth_service.get_user(token)
        except SupabaseAuthError as exc:
            raise _http_error(exc) from exc
        _cache_put(token, auth_user)

    raw_user = auth_user.get("user") if isinstance(auth_user.get("user"), dict) else auth_user
    if not raw_user:
        raise HTTPException(status_code=401, detail="Invalid authentication response")
    try:
        user_id = UUID(str(raw_user["id"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication subject") from exc

    profile = _profile_cache_get(user_id) or load_profile(
        user_id,
        raw_user.get("email"),
        (raw_user.get("user_metadata") or {}).get("full_name"),
    )
    if profile.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    return CurrentUser(id=str(user_id), email=raw_user.get("email"), profile=profile)


def require_super_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.profile.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")

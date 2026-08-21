from __future__ import annotations

from time import monotonic
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.auth.schemas import CurrentUser, UserProfile
from app.auth.service import SupabaseAuthError, auth_service
from app.db.connection import get_engine

bearer_scheme = HTTPBearer(auto_error=False)
AUTH_CACHE_TTL_SECONDS = 60.0
AUTH_CACHE_MAX_ENTRIES = 512
PROFILE_CACHE_TTL_SECONDS = 30.0
PROFILE_CACHE_MAX_ENTRIES = 512
_auth_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_profile_cache: dict[str, tuple[float, UserProfile]] = {}


def _http_error(exc: SupabaseAuthError) -> HTTPException:
    if exc.status_code in (401, 403):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    if exc.status_code == 429:
        return HTTPException(status_code=429, detail="Too many authentication requests")
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _cache_get(token: str) -> dict[str, Any] | None:
    item = _auth_cache.get(token)
    if item is None:
        return None
    created_at, user = item
    if monotonic() - created_at >= AUTH_CACHE_TTL_SECONDS:
        _auth_cache.pop(token, None)
        return None
    return user


def _cache_put(token: str, user: dict[str, Any]) -> None:
    if len(_auth_cache) >= AUTH_CACHE_MAX_ENTRIES:
        oldest_token = min(_auth_cache, key=lambda key: _auth_cache[key][0])
        _auth_cache.pop(oldest_token, None)
    _auth_cache[token] = (monotonic(), user)


def _profile_cache_get(user_id: UUID) -> UserProfile | None:
    key = str(user_id)
    item = _profile_cache.get(key)
    if item is None:
        return None
    created_at, profile = item
    if monotonic() - created_at >= PROFILE_CACHE_TTL_SECONDS:
        _profile_cache.pop(key, None)
        return None
    return profile


def _profile_cache_put(profile: UserProfile) -> None:
    key = str(profile.id)
    if len(_profile_cache) >= PROFILE_CACHE_MAX_ENTRIES:
        oldest_key = min(_profile_cache, key=lambda key: _profile_cache[key][0])
        _profile_cache.pop(oldest_key, None)
    _profile_cache[key] = (monotonic(), profile)


def invalidate_auth_cache(token: str) -> None:
    _auth_cache.pop(token, None)


def invalidate_profile_cache(user_id: str | UUID) -> None:
    _profile_cache.pop(str(user_id), None)


def load_profile(user_id: UUID, email: str | None, full_name: str | None) -> UserProfile:
    """Read an existing profile without turning every authenticated request into a write transaction."""
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
                case when exists (select 1 from public.admin_allowlist where lower(email) = lower(:email) and is_active = true)
                then 'super_admin' else 'user' end, 'active', 'free')
            on conflict (id) do update
            set email = coalesce(excluded.email, public.profiles.email),
                full_name = coalesce(excluded.full_name, public.profiles.full_name),
                role = excluded.role,
                updated_at = timezone('utc', now())
            returning id, email, full_name, role, status, plan_code
        """), {"id": str(user_id), "email": email, "full_name": full_name}).mappings().one()
    data = dict(row)
    data["id"] = str(data["id"])
    profile = UserProfile(**data)
    _profile_cache_put(profile)
    return profile


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> CurrentUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
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
    profile = _profile_cache_get(user_id) or load_profile(user_id, raw_user.get("email"), (raw_user.get("user_metadata") or {}).get("full_name"))
    if profile.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    return CurrentUser(id=str(user_id), email=raw_user.get("email"), profile=profile)


def require_super_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current_user.profile.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")

from __future__ import annotations

from dataclasses import dataclass
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

# Auth verification is the slowest common dependency because every protected
# endpoint otherwise performs a network round-trip to Supabase Auth. A very
# short, in-process cache lets the several API calls made while a page loads
# reuse the same verification result without making authentication sticky.
AUTH_CACHE_TTL_SECONDS = 8.0
AUTH_CACHE_MAX_ENTRIES = 512
_auth_cache: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    email: str | None
    profile: UserProfile


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


def invalidate_auth_cache(token: str) -> None:
    """Immediately invalidate a token after an explicit logout."""
    _auth_cache.pop(token, None)


def load_profile(user_id: UUID, email: str | None, full_name: str | None) -> UserProfile:
    """Ensure the profile is current and return it in one database round-trip."""
    with get_engine().begin() as connection:
        row = connection.execute(
            text(
                """
                insert into public.profiles (id, email, full_name, role, status, plan_code)
                values (
                    :id,
                    :email,
                    :full_name,
                    case when exists (
                        select 1
                        from public.admin_allowlist
                        where lower(email) = lower(:email)
                          and is_active = true
                    ) then 'super_admin' else 'user' end,
                    'active',
                    'free'
                )
                on conflict (id) do update
                set email = coalesce(excluded.email, public.profiles.email),
                    full_name = coalesce(excluded.full_name, public.profiles.full_name),
                    role = excluded.role,
                    updated_at = timezone('utc', now())
                returning id, email, full_name, role, status, plan_code
                """
            ),
            {"id": str(user_id), "email": email, "full_name": full_name},
        ).mappings().one()

    data = dict(row)
    data["id"] = str(data["id"])
    return UserProfile(**data)


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

    profile = load_profile(
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
    return current_user

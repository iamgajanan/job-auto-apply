from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from app.auth.schemas import CurrentUser, UserProfile
from app.auth.service import SupabaseAuthError, auth_service
from app.db.connection import get_engine

bearer_scheme = HTTPBearer(auto_error=False)


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


def load_profile(user_id: UUID, email: str | None, full_name: str | None) -> UserProfile:
    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                insert into public.profiles (id, email, full_name, role, status, plan_code)
                values (:id, :email, :full_name, 'user', 'active', 'free')
                on conflict (id) do update
                set email = coalesce(excluded.email, public.profiles.email),
                    full_name = coalesce(excluded.full_name, public.profiles.full_name),
                    updated_at = timezone('utc', now())
                """
            ),
            {"id": str(user_id), "email": email, "full_name": full_name},
        )

        allowlisted = connection.execute(
            text(
                """
                select exists(
                    select 1
                    from public.admin_allowlist
                    where lower(email) = lower(:email)
                      and is_active = true
                )
                """
            ),
            {"email": email or ""},
        ).scalar_one()

        role = "super_admin" if allowlisted else "user"
        connection.execute(
            text(
                """
                update public.profiles
                set role = :role,
                    updated_at = timezone('utc', now())
                where id = :id
                """
            ),
            {"role": role, "id": str(user_id)},
        )

        row = connection.execute(
            text(
                """
                select id, email, full_name, role, status, plan_code
                from public.profiles
                where id = :id
                """
            ),
            {"id": str(user_id)},
        ).mappings().one()

    return UserProfile(**dict(row))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        auth_user: dict[str, Any] = auth_service.get_user(credentials.credentials)
    except SupabaseAuthError as exc:
        raise _http_error(exc) from exc

    # /auth/v1/user returns the user object directly. Supporting a nested user
    # object as well keeps this adapter tolerant of SDK-style response shapes.
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

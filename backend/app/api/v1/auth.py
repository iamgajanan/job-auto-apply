from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import bearer_scheme, get_current_user
from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    Session,
    SignupRequest,
    CurrentUser,
)
from app.auth.service import SupabaseAuthError, auth_service
from app.db.connection import get_engine
from sqlalchemy import text

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _session(payload: dict) -> Session | None:
    if not payload.get("access_token"):
        return None
    return Session(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token", ""),
        token_type=payload.get("token_type", "bearer"),
        expires_in=payload.get("expires_in"),
        expires_at=payload.get("expires_at"),
    )


def _profile_for_user(user_id: str):
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                select id, email, full_name, role, status, plan_code
                from public.profiles
                where id = :id
                """
            ),
            {"id": user_id},
        ).mappings().one()
    from app.auth.schemas import UserProfile

    return UserProfile(**dict(row))


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest):
    try:
        payload = auth_service.signup(
            request.email.lower(),
            request.password,
            request.full_name,
        )
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    user = payload.get("user") or {}
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=502, detail="Supabase did not return a user")

    # The database trigger creates the free profile/quota atomically.
    profile = _profile_for_user(user_id)
    return AuthResponse(
        user=profile,
        session=_session(payload),
        email_confirmation_required=payload.get("session") is None,
    )


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    try:
        payload = auth_service.login(request.email.lower(), request.password)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Invalid email or password") from exc

    user = payload.get("user") or {}
    if not user.get("id"):
        raise HTTPException(status_code=502, detail="Supabase did not return a user")

    # get_current_user performs the same role/status synchronization on the next protected call.
    profile = _profile_for_user(user["id"])
    return AuthResponse(user=profile, session=_session(payload))


@router.post("/refresh", response_model=Session)
def refresh(request: RefreshRequest):
    try:
        payload = auth_service.refresh(request.refresh_token)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Refresh token is invalid or expired") from exc

    session = _session(payload)
    if not session:
        raise HTTPException(status_code=502, detail="Supabase did not return a refreshed session")
    return session


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        return
    try:
        auth_service.logout(credentials.credentials)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Unable to sign out") from exc


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)):
    return current_user

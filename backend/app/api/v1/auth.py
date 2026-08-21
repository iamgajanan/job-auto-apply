from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import text

from app.auth.dependencies import bearer_scheme, get_current_user, invalidate_auth_cache, load_profile
from app.auth.schemas import AuthResponse, CurrentUser, LoginRequest, PasswordResetRequest, PasswordUpdateRequest, RefreshRequest, Session, SignupRequest, UserProfile
from app.auth.service import SupabaseAuthError, auth_service
from app.db.connection import get_engine

router = APIRouter(prefix="/auth", tags=["Authentication"])
_AUTH_LOOKUP_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auth-profile")


def _session(payload: dict) -> Session | None:
    if not payload.get("access_token"):
        return None
    return Session(access_token=payload["access_token"], refresh_token=payload.get("refresh_token", ""), token_type=payload.get("token_type", "bearer"), expires_in=payload.get("expires_in"), expires_at=payload.get("expires_at"))


def _profile_for_user(user_id: str, email: str | None = None, full_name: str | None = None):
    with get_engine().connect() as connection:
        row = connection.execute(text("select id, email, full_name, role, status, plan_code from public.profiles where id = :id"), {"id": user_id}).mappings().one_or_none()
    if row:
        data = dict(row)
        data["id"] = str(data["id"])
        return UserProfile(**data)
    return load_profile(UUID(user_id), email, full_name)


def _profile_for_email(email: str):
    with get_engine().connect() as connection:
        row = connection.execute(text("select id, email, full_name, role, status, plan_code from public.profiles where lower(email) = lower(:email)"), {"email": email}).mappings().one_or_none()
    if not row:
        return None
    data = dict(row)
    data["id"] = str(data["id"])
    return UserProfile(**data)


def _unauthorized_status(exc: SupabaseAuthError) -> int:
    return status.HTTP_401_UNAUTHORIZED if exc.status_code in (401, 403) else exc.status_code


def _login_error(exc: SupabaseAuthError) -> tuple[int, str]:
    if exc.status_code in (429, 500, 502, 503):
        return exc.status_code, str(exc)
    if exc.status_code == 400 and str(exc).strip().lower() == "email not confirmed":
        return status.HTTP_403_FORBIDDEN, "Email confirmation required"
    return status.HTTP_401_UNAUTHORIZED, "Invalid email or password"


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(request: SignupRequest):
    try:
        payload = auth_service.signup(request.email.lower(), request.password, request.full_name)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    user = payload.get("user") or {}
    user_id = user.get("id")
    if not user_id:
        profile = _profile_for_email(request.email.lower())
        if not profile:
            raise HTTPException(status_code=502, detail="Supabase signup completed without a user profile")
        return AuthResponse(user=profile, session=None, email_confirmation_required=True)

    # New accounts are created by the Supabase trigger with these application
    # defaults. Avoid an extra profile round-trip on the signup critical path.
    user_metadata = user.get("user_metadata") or {}
    profile = UserProfile(
        id=str(user_id),
        email=user.get("email") or request.email.lower(),
        full_name=user_metadata.get("full_name") or request.full_name,
        role="user",
        status="active",
        plan_code="free",
    )
    return AuthResponse(user=profile, session=_session(payload), email_confirmation_required=payload.get("session") is None)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest):
    email = request.email.lower()
    profile_future = _AUTH_LOOKUP_EXECUTOR.submit(_profile_for_email, email)
    try:
        payload = auth_service.login(email, request.password)
    except SupabaseAuthError as exc:
        error_status, detail = _login_error(exc)
        raise HTTPException(status_code=error_status, detail=detail) from exc

    user = payload.get("user") or {}
    if not user.get("id"):
        raise HTTPException(status_code=502, detail="Supabase did not return a user")

    try:
        profile = profile_future.result()
    except Exception:
        profile = None
    user_id = str(user["id"])
    if profile is None or profile.id != user_id:
        profile = load_profile(UUID(user_id), user.get("email"), (user.get("user_metadata") or {}).get("full_name"))
    if profile.status != "active":
        raise HTTPException(status_code=403, detail="Account is not active")
    return AuthResponse(user=profile, session=_session(payload))


@router.post("/refresh", response_model=Session)
def refresh(request: RefreshRequest):
    try:
        payload = auth_service.refresh(request.refresh_token)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=_unauthorized_status(exc), detail="Refresh token is invalid or expired") from exc
    session = _session(payload)
    if not session:
        raise HTTPException(status_code=502, detail="Supabase did not return a refreshed session")
    return session


@router.post("/password-reset", status_code=status.HTTP_202_ACCEPTED)
def password_reset(request: PasswordResetRequest):
    try:
        auth_service.request_password_reset(request.email.lower(), request.redirect_to)
    except SupabaseAuthError:
        pass
    return {"message": "If the account exists, password reset instructions will be sent."}


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(request: PasswordUpdateRequest, credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        auth_service.update_password(credentials.credentials, request.password)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=_unauthorized_status(exc), detail="Unable to update password") from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not credentials:
        return
    try:
        auth_service.logout(credentials.credentials)
    except SupabaseAuthError as exc:
        raise HTTPException(status_code=_unauthorized_status(exc), detail="Unable to sign out") from exc
    finally:
        invalidate_auth_cache(credentials.credentials)


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)):
    return current_user

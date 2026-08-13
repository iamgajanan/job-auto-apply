from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from app.auth.dependencies import load_profile, require_super_admin
from app.auth.schemas import CurrentUser
from app.config.settings import settings
from app.db.connection import get_engine

router = APIRouter(prefix="/admin", tags=["Admin"])


class GrantQuotaRequest(BaseModel):
    searches: int = Field(gt=0, le=1_000_000)
    plan_code: str = Field(default="free", min_length=1, max_length=50)


class UpdateUserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|deleted)$")


class UpdatePlanRequest(BaseModel):
    price_inr_paise: int = Field(ge=0)
    search_limit: int = Field(gt=0)
    is_active: bool = True


class AllowlistEmailRequest(BaseModel):
    email: EmailStr


@router.get("/users")
def list_users(
    limit: int = 100,
    _: CurrentUser = Depends(require_super_admin),
):
    limit = min(max(limit, 1), 500)
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                select
                    p.id,
                    p.email,
                    p.full_name,
                    p.role,
                    p.status,
                    p.plan_code,
                    coalesce(sum(qa.granted_searches), 0)::int as granted_searches,
                    coalesce(sum(qa.used_searches), 0)::int as used_searches,
                    coalesce(sum(qa.granted_searches - qa.used_searches), 0)::int as remaining_searches,
                    p.created_at
                from public.profiles p
                left join public.quota_allocations qa
                  on qa.user_id = p.id
                 and qa.starts_at <= timezone('utc', now())
                 and (qa.ends_at is null or qa.ends_at > timezone('utc', now()))
                group by p.id
                order by p.created_at desc
                limit :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return {"users": [dict(row) for row in rows]}


@router.post("/users/{user_id}/quota")
def grant_quota(
    user_id: UUID,
    request: GrantQuotaRequest,
    _: CurrentUser = Depends(require_super_admin),
):
    with get_engine().begin() as connection:
        user_exists = connection.execute(
            text("select exists(select 1 from public.profiles where id = :id)"),
            {"id": str(user_id)},
        ).scalar_one()
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found")

        plan_exists = connection.execute(
            text("select exists(select 1 from public.plans where code = :code)"),
            {"code": request.plan_code},
        ).scalar_one()
        if not plan_exists:
            raise HTTPException(status_code=404, detail="Plan not found")

        connection.execute(
            text(
                """
                insert into public.quota_allocations (
                    user_id, plan_code, granted_searches, source, starts_at
                ) values (:user_id, :plan_code, :searches, 'admin', timezone('utc', now()))
                """
            ),
            {
                "user_id": str(user_id),
                "plan_code": request.plan_code,
                "searches": request.searches,
            },
        )
    return {"status": "granted", "user_id": str(user_id), "searches": request.searches}


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: UUID,
    request: UpdateUserStatusRequest,
    _: CurrentUser = Depends(require_super_admin),
):
    with get_engine().begin() as connection:
        result = connection.execute(
            text(
                """
                update public.profiles
                set status = :status, updated_at = timezone('utc', now())
                where id = :id
                """
            ),
            {"id": str(user_id), "status": request.status},
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="User not found")
    return {"status": request.status, "user_id": str(user_id)}


@router.patch("/plans/{plan_code}")
def update_plan(
    plan_code: str,
    request: UpdatePlanRequest,
    _: CurrentUser = Depends(require_super_admin),
):
    with get_engine().begin() as connection:
        result = connection.execute(
            text(
                """
                update public.plans
                set price_inr_paise = :price,
                    search_limit = :search_limit,
                    is_active = :is_active,
                    updated_at = timezone('utc', now())
                where code = :code
                """
            ),
            {
                "code": plan_code,
                "price": request.price_inr_paise,
                "search_limit": request.search_limit,
                "is_active": request.is_active,
            },
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "updated", "plan_code": plan_code}


@router.get("/allowlist")
def list_allowlist(_: CurrentUser = Depends(require_super_admin)):
    with get_engine().connect() as connection:
        rows = connection.execute(
            text("select email, is_active, created_at from public.admin_allowlist order by email")
        ).mappings().all()
    return {"emails": [dict(row) for row in rows]}


@router.post("/allowlist")
def add_allowlist_email(
    request: AllowlistEmailRequest,
    _: CurrentUser = Depends(require_super_admin),
):
    email = request.email.lower()
    with get_engine().begin() as connection:
        connection.execute(
            text(
                """
                insert into public.admin_allowlist (email, is_active)
                values (:email, true)
                on conflict (email) do update set is_active = true
                """
            ),
            {"email": email},
        )
    return {"status": "active", "email": email}


@router.delete("/allowlist/{email}")
def remove_allowlist_email(
    email: str,
    _: CurrentUser = Depends(require_super_admin),
):
    normalized = email.lower()
    with get_engine().begin() as connection:
        result = connection.execute(
            text("update public.admin_allowlist set is_active = false where email = :email"),
            {"email": normalized},
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="Email not found in admin allowlist")
    return {"status": "inactive", "email": normalized}


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = Field(default=None, max_length=200)
    plan_code: str = Field(default="free", min_length=1, max_length=50)
    plan_searches: int | None = Field(default=None, gt=0, le=1_000_000)


@router.post("/users", status_code=201)
def create_user(
    request: CreateUserRequest,
    _: CurrentUser = Depends(require_super_admin),
):
    """Create a user via the Supabase Admin API from a trusted admin request."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Supabase admin credentials are not configured",
        )

    # Validate the requested plan before creating the Auth user. This prevents
    # an invalid plan from leaving an orphaned Auth account.
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                select search_limit
                from public.plans
                where code = :code and is_active = true
                """
            ),
            {"code": request.plan_code},
        ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Plan '{request.plan_code}' not found or inactive")

    plan_searches = request.plan_searches if request.plan_searches is not None else row[0]
    email = request.email.lower()
    admin_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    body: dict = {
        "email": email,
        "password": request.password,
        "email_confirm": True,
    }
    if request.full_name:
        body["user_metadata"] = {"full_name": request.full_name}

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(admin_url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Supabase Admin API unavailable") from exc

    try:
        response_json = resp.json()
    except ValueError:
        response_json = {}

    if resp.status_code >= 400:
        detail = response_json.get("msg") or response_json.get("message") or "Failed to create user"
        status_code = 409 if resp.status_code in (400, 422) and "already" in detail.lower() else resp.status_code
        raise HTTPException(status_code=status_code, detail=detail)

    user_id = response_json.get("id")
    if not user_id:
        raise HTTPException(status_code=502, detail="Supabase did not return a user ID")

    # Supabase Auth creation and PostgreSQL quota/profile writes cannot share a
    # database transaction. If our DB setup fails, delete the Auth user again
    # so this endpoint does not leave a partially-created account behind.
    try:
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    insert into public.profiles (id, email, full_name, role, status, plan_code)
                    values (:id, :email, :full_name, 'user', 'active', :plan_code)
                    on conflict (id) do update
                    set email = excluded.email,
                        full_name = coalesce(excluded.full_name, public.profiles.full_name),
                        plan_code = excluded.plan_code,
                        updated_at = timezone('utc', now())
                    """
                ),
                {
                    "id": user_id,
                    "email": email,
                    "full_name": request.full_name,
                    "plan_code": request.plan_code,
                },
            )
            connection.execute(
                text(
                    """
                    update public.quota_allocations
                    set ends_at = timezone('utc', now())
                    where user_id = :uid
                      and source = 'signup'
                      and plan_code = 'free'
                      and (ends_at is null or ends_at > timezone('utc', now()))
                    """
                ),
                {"uid": user_id},
            )
            connection.execute(
                text(
                    """
                    insert into public.quota_allocations
                        (user_id, plan_code, granted_searches, source, starts_at)
                    values
                        (:uid, :plan_code, :searches, 'admin_create', timezone('utc', now()))
                    """
                ),
                {
                    "uid": user_id,
                    "plan_code": request.plan_code,
                    "searches": plan_searches,
                },
            )
    except Exception as exc:
        try:
            with httpx.Client(timeout=15.0) as client:
                rollback = client.delete(
                    f"{admin_url}/{user_id}",
                    headers=headers,
                )
            if rollback.status_code >= 400:
                raise RuntimeError(f"Supabase rollback failed with HTTP {rollback.status_code}")
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="User creation failed and cleanup could not be completed; check server logs",
            ) from exc
        raise HTTPException(status_code=500, detail="User creation failed; the Auth user was rolled back") from exc

    return {
        "user_id": user_id,
        "email": email,
        "full_name": request.full_name,
        "plan_code": request.plan_code,
        "granted_searches": plan_searches,
    }

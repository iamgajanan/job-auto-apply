from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.auth.schemas import AccountResponse, CurrentUser, UsageResponse
from app.db.connection import get_engine

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("/me", response_model=AccountResponse)
def account_me(current_user: CurrentUser = Depends(get_current_user)):
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                select
                    p.code as plan_code,
                    p.name as plan_name,
                    coalesce(sum(qa.granted_searches), 0)::int as granted_searches,
                    coalesce(sum(qa.used_searches), 0)::int as used_searches,
                    coalesce(sum(qa.granted_searches - qa.used_searches), 0)::int as remaining_searches
                from public.plans p
                left join public.quota_allocations qa
                  on qa.user_id = :user_id
                 and qa.starts_at <= timezone('utc', now())
                 and (qa.ends_at is null or qa.ends_at > timezone('utc', now()))
                where p.code = :plan_code
                group by p.code, p.name
                """
            ),
            {"user_id": current_user.id, "plan_code": current_user.profile.plan_code},
        ).mappings().one()

    return AccountResponse(
        user=current_user.profile,
        usage=UsageResponse(**dict(row)),
    )

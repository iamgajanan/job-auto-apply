from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.auth.dependencies import require_super_admin
from app.auth.schemas import CurrentUser
from app.db.connection import get_engine
from app.features.payments.schemas import AdminPaymentHistoryResponse

router = APIRouter(prefix="/admin/payments", tags=["Admin Payments"])


@router.get("", response_model=AdminPaymentHistoryResponse)
def admin_payment_history(
    limit: int = Query(default=100, ge=1, le=500),
    _: CurrentUser = Depends(require_super_admin),
):
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                select
                    pay.id,
                    pay.user_id,
                    profile.email as user_email,
                    pay.plan_code,
                    coalesce(plan.name, pay.plan_code) as plan_name,
                    pay.provider,
                    pay.provider_order_id,
                    pay.provider_payment_id,
                    pay.amount_inr_paise,
                    pay.currency,
                    pay.status,
                    coalesce(
                        sum(ref.amount_inr_paise) filter (where ref.status = 'processed'),
                        0
                    )::bigint as refunded_inr_paise,
                    pay.paid_at,
                    pay.created_at
                from public.payments pay
                left join public.profiles profile on profile.id = pay.user_id
                left join public.plans plan on plan.code = pay.plan_code
                left join public.payment_refunds ref on ref.payment_id = pay.id
                group by pay.id, profile.email, plan.name
                order by pay.created_at desc
                limit :limit
                """
            ),
            {"limit": limit},
        ).mappings().all()
    return {"payments": [dict(row) for row in rows]}

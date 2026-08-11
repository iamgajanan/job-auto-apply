from fastapi import APIRouter
from sqlalchemy import text

from app.db.connection import get_engine

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("")
def list_plans():
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                select
                    code,
                    name,
                    price_inr_paise,
                    search_limit,
                    billing_interval,
                    metadata
                from public.plans
                where is_active = true
                order by sort_order, price_inr_paise
                """
            )
        ).mappings().all()

    return {"plans": [dict(row) for row in rows]}

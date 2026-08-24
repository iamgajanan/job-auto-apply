from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.config.settings import settings
from app.db.connection import get_engine
from app.features.payments.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    PaymentHistoryResponse,
    PaymentResult,
    VerifyPaymentRequest,
)
from app.features.payments.service import payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/orders", response_model=CreateOrderResponse)
def create_order(
    request: CreateOrderRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return payment_service.create_order(current_user.id, request.plan_code)


@router.post("/verify", response_model=PaymentResult)
def verify_payment(
    request: VerifyPaymentRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return payment_service.finalize_payment(
        current_user.id,
        request.razorpay_order_id,
        request.razorpay_payment_id,
        request.razorpay_signature,
    )


@router.get("/history", response_model=PaymentHistoryResponse)
def payment_history(
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=500),
):
    with get_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                select
                    pay.id::text as id,
                    pay.plan_code,
                    coalesce(plan.name, pay.plan_code) as plan_name,
                    pay.provider,
                    pay.provider_order_id,
                    pay.provider_payment_id,
                    pay.amount_inr_paise,
                    pay.currency,
                    pay.status,
                    coalesce(
                        (
                            select sum(ref.amount_inr_paise)
                            from public.payment_refunds ref
                            where ref.payment_id = pay.id
                              and ref.status = 'processed'
                        ),
                        0
                    )::bigint as refunded_inr_paise,
                    pay.paid_at,
                    pay.created_at
                from public.payments pay
                left join public.plans plan on plan.code = pay.plan_code
                where pay.user_id = :user_id
                order by pay.created_at desc
                limit :limit
                """
            ),
            {"user_id": current_user.id, "limit": limit},
        ).mappings().all()
    return {"payments": [dict(row) for row in rows]}


@router.post("/webhook")
async def razorpay_webhook(
    http_request: Request,
    x_razorpay_signature: str | None = Header(default=None),
):
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Razorpay webhook is not configured")
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay webhook signature")

    raw_body = await http_request.body()
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    # NOTE: hmac.new is the correct stdlib call (alias for hmac.HMAC constructor)
    if not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc

    event_type = payload.get("event", "")
    provider_event_id = payload.get("id") or payload.get("event_id") or ""

    supported_events = {
        "payment.captured",
        "payment.failed",
        "refund.created",
        "refund.processed",
        "refund.failed",
    }
    if event_type not in supported_events:
        return {"received": True, "processed": False, "reason": "unhandled_event"}

    payment_entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    refund_entity = ((payload.get("payload") or {}).get("refund") or {}).get("entity") or {}

    if event_type.startswith("payment."):
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")
        if not order_id or not payment_id:
            raise HTTPException(status_code=400, detail="Webhook is missing payment identifiers")

        with get_engine().connect() as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, status, amount_inr_paise
                    from public.payments
                    where provider = 'razorpay' and provider_order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).mappings().one_or_none()

        if not row:
            return {"received": True, "processed": False, "reason": "unknown_order"}
    else:
        payment_id = refund_entity.get("payment_id")
        refund_id = refund_entity.get("id")
        if not payment_id or not refund_id:
            raise HTTPException(status_code=400, detail="Refund webhook is missing payment/refund identifiers")

        with get_engine().connect() as connection:
            row = connection.execute(
                text(
                    """
                    select id, user_id, status, amount_inr_paise
                    from public.payments
                    where provider = 'razorpay' and provider_payment_id = :payment_id
                    """
                ),
                {"payment_id": payment_id},
            ).mappings().one_or_none()

        if not row:
            return {"received": True, "processed": False, "reason": "unknown_payment"}

    event_id = provider_event_id or f"razorpay_{event_type}_{payment_id}"

    try:
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    insert into public.webhook_events (
                        provider, provider_event_id, event_type, payment_id, raw_payload
                    ) values (
                        'razorpay',
                        :event_id,
                        :event_type,
                        :payment_id,
                        cast(:raw as jsonb)
                    )
                    """
                ),
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payment_id": str(row["id"]),
                    "raw": json.dumps(payload),
                },
            )
    except IntegrityError as exc:
        if "webhook_events_provider_event_unique" in str(exc.orig):
            return {"received": True, "processed": False, "reason": "duplicate_event"}
        raise

    try:
        if event_type == "payment.failed":
            with get_engine().begin() as connection:
                connection.execute(
                    text(
                        """
                        update public.payments
                        set status = 'failed',
                            provider_payment_id = :payment_id,
                            updated_at = timezone('utc', now())
                        where id = :id
                          and status not in ('captured', 'refunded')
                        """
                    ),
                    {"payment_id": payment_id, "id": str(row["id"])},
                )
            return {"received": True, "processed": True, "event": event_type}

        if event_type in ("refund.created", "refund.processed", "refund.failed"):
            refund_status = event_type.removeprefix("refund.")
            refund_id = refund_entity["id"]
            refund_amount = int(refund_entity.get("amount", 0))
            if refund_amount <= 0:
                raise HTTPException(status_code=400, detail="Refund amount must be greater than zero")

            with get_engine().begin() as connection:
                connection.execute(
                    text(
                        """
                        insert into public.payment_refunds (
                            payment_id,
                            provider,
                            provider_refund_id,
                            amount_inr_paise,
                            currency,
                            status,
                            raw_payload
                        ) values (
                            :payment_id,
                            'razorpay',
                            :refund_id,
                            :amount,
                            :currency,
                            :status,
                            cast(:raw as jsonb)
                        )
                        on conflict (provider, provider_refund_id) do update
                        set amount_inr_paise = excluded.amount_inr_paise,
                            currency = excluded.currency,
                            status = excluded.status,
                            raw_payload = excluded.raw_payload,
                            updated_at = timezone('utc', now())
                        """
                    ),
                    {
                        "payment_id": str(row["id"]),
                        "refund_id": refund_id,
                        "amount": refund_amount,
                        "currency": refund_entity.get("currency") or "INR",
                        "status": refund_status,
                        "raw": json.dumps(payload),
                    },
                )

                if refund_status == "processed":
                    refunded = connection.execute(
                        text(
                            """
                            select coalesce(sum(amount_inr_paise), 0)::bigint
                            from public.payment_refunds
                            where payment_id = :payment_id
                              and status = 'processed'
                            """
                        ),
                        {"payment_id": str(row["id"])},
                    ).scalar_one()
                    original_amount = int(row["amount_inr_paise"])
                    new_status = "refunded" if refunded >= original_amount else "partially_refunded"
                    connection.execute(
                        text(
                            """
                            update public.payments
                            set status = :status,
                                updated_at = timezone('utc', now())
                            where id = :id
                            """
                        ),
                        {"status": new_status, "id": str(row["id"])},
                    )

            return {"received": True, "processed": True, "event": event_type}

        result = payment_service.finalize_payment(
            str(row["user_id"]),
            order_id,
            payment_id,
            None,
        )
        return {"received": True, "processed": True, "event": "payment.captured", "result": result}
    except Exception:
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    delete from public.webhook_events
                    where provider = 'razorpay' and provider_event_id = :event_id
                    """
                ),
                {"event_id": event_id},
            )
        raise

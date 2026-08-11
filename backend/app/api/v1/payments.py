from __future__ import annotations

import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.config.settings import settings
from app.db.connection import get_engine
from app.features.payments.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
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
    if not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid Razorpay webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc

    if payload.get("event") != "payment.captured":
        return {"received": True, "processed": False}

    entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    order_id = entity.get("order_id")
    payment_id = entity.get("id")
    if not order_id or not payment_id:
        raise HTTPException(status_code=400, detail="Webhook is missing payment identifiers")

    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                """
                select user_id
                from public.payments
                where provider = 'razorpay' and provider_order_id = :order_id
                """
            ),
            {"order_id": order_id},
        ).mappings().one_or_none()

    if not row:
        return {"received": True, "processed": False}

    result = payment_service.finalize_payment(
        str(row["user_id"]),
        order_id,
        payment_id,
        None,
    )
    return {"received": True, "processed": True, "result": result}

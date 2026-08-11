from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from app.config.settings import settings
from app.db.connection import get_engine

RAZORPAY_API = "https://api.razorpay.com/v1"


class PaymentService:
    def _require_keys(self) -> None:
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise HTTPException(status_code=503, detail="Razorpay is not configured")

    def _client(self) -> httpx.Client:
        self._require_keys()
        return httpx.Client(
            base_url=RAZORPAY_API,
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            timeout=15.0,
        )

    def create_order(self, user_id: str, plan_code: str) -> dict[str, Any]:
        with get_engine().connect() as connection:
            plan = connection.execute(
                text(
                    """
                    select code, name, price_inr_paise, search_limit, billing_interval
                    from public.plans
                    where code = :code and is_active = true
                    """
                ),
                {"code": plan_code},
            ).mappings().one_or_none()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if plan["price_inr_paise"] <= 0:
            raise HTTPException(status_code=400, detail="The free plan does not require payment")

        self._require_keys()
        receipt = f"jobauto_{user_id[:8]}_{plan_code}_{int(datetime.now(timezone.utc).timestamp())}"
        payload = {
            "amount": int(plan["price_inr_paise"]),
            "currency": "INR",
            "receipt": receipt,
            "notes": {"user_id": user_id, "plan_code": plan_code},
        }

        try:
            with self._client() as client:
                response = client.post("/orders", json=payload)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Razorpay is temporarily unavailable") from exc

        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Razorpay order creation failed")

        order = response.json()
        order_id = order.get("id")
        if not order_id:
            raise HTTPException(status_code=502, detail="Razorpay returned an invalid order")

        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    insert into public.payments (
                        user_id,
                        plan_code,
                        provider,
                        provider_order_id,
                        amount_inr_paise,
                        currency,
                        status,
                        metadata
                    ) values (
                        :user_id,
                        :plan_code,
                        'razorpay',
                        :order_id,
                        :amount,
                        'INR',
                        'created',
                        cast(:metadata as jsonb)
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "plan_code": plan_code,
                    "order_id": order_id,
                    "amount": int(plan["price_inr_paise"]),
                    "metadata": '{"receipt":"' + receipt + '"}',
                },
            )

        return {
            "order_id": order_id,
            "amount_inr_paise": int(plan["price_inr_paise"]),
            "currency": "INR",
            "plan_code": plan["code"],
            "plan_name": plan["name"],
            "search_limit": int(plan["search_limit"]),
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        }

    @staticmethod
    def verify_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
        expected = hmac.new(
            secret.encode("utf-8"),
            f"{order_id}|{payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _fetch_payment(self, payment_id: str) -> dict[str, Any]:
        try:
            with self._client() as client:
                response = client.get(f"/payments/{payment_id}")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Unable to verify Razorpay payment") from exc

        if response.status_code >= 400:
            raise HTTPException(status_code=400, detail="Razorpay payment could not be verified")
        return response.json()

    def finalize_payment(
        self,
        user_id: str,
        order_id: str,
        payment_id: str,
        signature: str,
        *,
        require_captured: bool = True,
    ) -> dict[str, Any]:
        self._require_keys()

        with get_engine().begin() as connection:
            payment = connection.execute(
                text(
                    """
                    select
                        id,
                        user_id,
                        plan_code,
                        amount_inr_paise,
                        status
                    from public.payments
                    where provider = 'razorpay'
                      and provider_order_id = :order_id
                      and user_id = :user_id
                    for update
                    """
                ),
                {"order_id": order_id, "user_id": user_id},
            ).mappings().one_or_none()

            if not payment:
                raise HTTPException(status_code=404, detail="Payment order not found")

            if payment["status"] == "captured":
                remaining = connection.execute(
                    text(
                        """
                        select coalesce(sum(granted_searches - used_searches), 0)::int
                        from public.quota_allocations
                        where user_id = :user_id
                          and starts_at <= timezone('utc', now())
                          and (ends_at is null or ends_at > timezone('utc', now()))
                        """
                    ),
                    {"user_id": user_id},
                ).scalar_one()
                return {
                    "status": "captured",
                    "plan_code": payment["plan_code"],
                    "granted_searches": 0,
                    "remaining_searches": remaining,
                }

            if not self.verify_signature(order_id, payment_id, signature, settings.RAZORPAY_KEY_SECRET):
                raise HTTPException(status_code=400, detail="Invalid Razorpay payment signature")

            razorpay_payment = self._fetch_payment(payment_id)
            if razorpay_payment.get("order_id") != order_id:
                raise HTTPException(status_code=400, detail="Payment does not belong to this order")
            if int(razorpay_payment.get("amount", 0)) != int(payment["amount_inr_paise"]):
                raise HTTPException(status_code=400, detail="Payment amount does not match the order")
            if require_captured and razorpay_payment.get("status") != "captured":
                raise HTTPException(status_code=409, detail="Payment is not captured yet")

            plan = connection.execute(
                text(
                    """
                    select code, search_limit
                    from public.plans
                    where code = :code and is_active = true
                    """
                ),
                {"code": payment["plan_code"]},
            ).mappings().one_or_none()
            if not plan:
                raise HTTPException(status_code=409, detail="Purchased plan is no longer active")

            connection.execute(
                text(
                    """
                    update public.payments
                    set provider_payment_id = :payment_id,
                        provider_signature = :signature,
                        status = 'captured',
                        paid_at = timezone('utc', now()),
                        updated_at = timezone('utc', now())
                    where id = :id
                    """
                ),
                {
                    "payment_id": payment_id,
                    "signature": signature,
                    "id": payment["id"],
                },
            )

            connection.execute(
                text(
                    """
                    insert into public.quota_allocations (
                        user_id,
                        plan_code,
                        granted_searches,
                        source,
                        starts_at
                    ) values (
                        :user_id,
                        :plan_code,
                        :search_limit,
                        'payment',
                        timezone('utc', now())
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "plan_code": plan["code"],
                    "search_limit": int(plan["search_limit"]),
                },
            )

            connection.execute(
                text(
                    """
                    update public.profiles
                    set plan_code = :plan_code,
                        updated_at = timezone('utc', now())
                    where id = :user_id
                    """
                ),
                {"plan_code": plan["code"], "user_id": user_id},
            )

            remaining = connection.execute(
                text(
                    """
                    select coalesce(sum(granted_searches - used_searches), 0)::int
                    from public.quota_allocations
                    where user_id = :user_id
                      and starts_at <= timezone('utc', now())
                      and (ends_at is null or ends_at > timezone('utc', now()))
                    """
                ),
                {"user_id": user_id},
            ).scalar_one()

        return {
            "status": "captured",
            "plan_code": plan["code"],
            "granted_searches": int(plan["search_limit"]),
            "remaining_searches": int(remaining),
        }


payment_service = PaymentService()

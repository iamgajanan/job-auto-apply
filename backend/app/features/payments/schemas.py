from datetime import datetime

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    plan_code: str = Field(min_length=1, max_length=50)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount_inr_paise: int
    currency: str
    plan_code: str
    plan_name: str
    search_limit: int
    razorpay_key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=5)
    razorpay_payment_id: str = Field(min_length=5)
    razorpay_signature: str = Field(min_length=10)


class PaymentResult(BaseModel):
    status: str
    plan_code: str
    granted_searches: int
    remaining_searches: int


class PaymentHistoryItem(BaseModel):
    id: str
    plan_code: str
    plan_name: str
    provider: str
    provider_order_id: str | None
    provider_payment_id: str | None
    amount_inr_paise: int
    currency: str
    status: str
    refunded_inr_paise: int
    paid_at: datetime | None
    created_at: datetime


class PaymentHistoryResponse(BaseModel):
    payments: list[PaymentHistoryItem]


class AdminPaymentHistoryItem(PaymentHistoryItem):
    user_id: str
    user_email: str | None


class AdminPaymentHistoryResponse(BaseModel):
    payments: list[AdminPaymentHistoryItem]

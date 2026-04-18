"""
Billing Models — Pydantic schemas for subscription state and webhook events.
"""

from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
try:
    from pydantic import EmailStr
except ImportError:
    EmailStr = str  # type: ignore


class SubscriptionTier(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    ELITE = "elite"
    TEAM = "team"
    UNKNOWN = "unknown"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    UNPAID = "unpaid"


class BillingInterval(str, Enum):
    MONTHLY = "month"
    ANNUAL = "year"


class SubscriptionRecord(BaseModel):
    """Full subscription state stored in DB."""
    customer_id: str
    email: Optional[str] = None
    stripe_subscription_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    interval: BillingInterval
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(use_enum_values=True)


class WebhookEventRecord(BaseModel):
    """Idempotency record for processed webhook events."""
    event_id: str            # Stripe event ID (evt_xxx)
    event_type: str
    processed_at: datetime
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None


class CheckoutSessionData(BaseModel):
    """Extracted data from checkout.session.completed."""
    session_id: str
    customer_id: str
    subscription_id: str
    email: Optional[str] = None
    tier: SubscriptionTier
    interval: BillingInterval


class SubscriptionChangeData(BaseModel):
    """Data extracted from subscription update/delete events."""
    subscription_id: str
    customer_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    interval: BillingInterval
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False


class InvoiceData(BaseModel):
    """Data extracted from invoice events."""
    invoice_id: str
    customer_id: str
    subscription_id: Optional[str] = None
    amount_paid: int       # In cents
    currency: str
    status: str            # 'paid' | 'open' | 'uncollectible'
    next_payment_attempt: Optional[datetime] = None

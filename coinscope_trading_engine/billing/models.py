"""
billing/models.py — CoinScopeAI Stripe Billing Pydantic Models
================================================================
Request/response schemas used by the billing API router.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlanTier(str, Enum):
    STARTER = "starter"   # $19/mo  — 5 pairs, alerts, basic signals
    PRO     = "pro"       # $49/mo  — 20 pairs, all signals, Telegram
    ELITE   = "elite"     # $99/mo  — unlimited pairs, ML signals, API access
    TEAM    = "team"      # $299/mo — everything + 5 seats + white-label


class SubscriptionStatus(str, Enum):
    ACTIVE             = "active"
    TRIALING           = "trialing"
    PAST_DUE           = "past_due"
    CANCELED           = "canceled"
    UNPAID             = "unpaid"
    INCOMPLETE         = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED             = "paused"
    NONE               = "none"          # no subscription yet


# ---------------------------------------------------------------------------
# Plan catalogue
# ---------------------------------------------------------------------------

class PlanInfo(BaseModel):
    tier:        PlanTier
    name:        str
    price_usd:   float
    description: str
    features:    list[str]
    price_id:    str = ""              # filled at runtime from settings


PLAN_CATALOGUE: list[PlanInfo] = [
    PlanInfo(
        tier        = PlanTier.STARTER,
        name        = "Starter",
        price_usd   = 19.0,
        description = "For individual traders getting started with algorithmic signals.",
        features    = [
            "5 trading pairs",
            "ML signal alerts (Telegram)",
            "Basic confluence scoring",
            "Daily performance report",
        ],
    ),
    PlanInfo(
        tier        = PlanTier.PRO,
        name        = "Pro",
        price_usd   = 49.0,
        description = "For active traders who want full signal coverage and automation.",
        features    = [
            "20 trading pairs",
            "All confluence signals",
            "Telegram + webhook alerts",
            "Regime detection",
            "Risk gate dashboard",
            "Trade journal (Notion sync)",
        ],
    ),
    PlanInfo(
        tier        = PlanTier.ELITE,
        name        = "Elite",
        price_usd   = 99.0,
        description = "Full ML-powered engine with direct API access.",
        features    = [
            "Unlimited trading pairs",
            "V3 LightGBM ML signals",
            "API key access (REST)",
            "Walk-forward validation reports",
            "Priority Telegram support",
            "Custom scan intervals",
        ],
    ),
    PlanInfo(
        tier        = PlanTier.TEAM,
        name        = "Team",
        price_usd   = 299.0,
        description = "Institutional grade — for prop desks and fund managers.",
        features    = [
            "Everything in Elite",
            "5 seats",
            "White-label dashboard",
            "Dedicated onboarding",
            "SLA 99.9% uptime",
            "Custom signal thresholds",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    tier:             PlanTier
    customer_email:   EmailStr
    customer_name:    Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "tier": "pro",
                "customer_email": "trader@example.com",
                "customer_name": "Mohammed A.",
            }
        }


class PortalRequest(BaseModel):
    customer_email: EmailStr

    class Config:
        json_schema_extra = {
            "example": {"customer_email": "trader@example.com"}
        }


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id:   str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionInfo(BaseModel):
    status:              SubscriptionStatus
    tier:                Optional[PlanTier] = None
    customer_id:         Optional[str]      = None
    subscription_id:     Optional[str]      = None
    current_period_end:  Optional[int]      = None   # Unix timestamp
    cancel_at_period_end: bool              = False


class WebhookResponse(BaseModel):
    received: bool = True

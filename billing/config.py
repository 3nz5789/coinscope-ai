"""
CoinScopeAI Billing — Pricing Configuration
============================================
Canonical pricing tiers. Price IDs are created in Stripe Dashboard (Test Mode)
and set as environment variables.

Tier      Monthly   Annual (20% off)
──────────────────────────────────────
Starter   $19/mo    $190/yr
Pro       $49/mo    $490/yr  ← Most Popular
Elite     $99/mo    $990/yr
Team      $299/mo   Custom

All amounts in USD cents for Stripe API.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PriceConfig:
    tier: str
    display_name: str
    monthly_usd: int          # in cents
    annual_usd: int           # in cents
    monthly_price_id: str     # Stripe Price ID (from env)
    annual_price_id: str      # Stripe Price ID (from env)
    most_popular: bool = False
    features: list = field(default_factory=list)


# ── Canonical Plan Registry ───────────────────────────────────────────────────

PLANS: dict[str, PriceConfig] = {
    "starter": PriceConfig(
        tier="starter",
        display_name="Starter",
        monthly_usd=1900,
        annual_usd=19000,
        monthly_price_id=os.getenv("STRIPE_PRICE_STARTER_MONTHLY", ""),
        annual_price_id=os.getenv("STRIPE_PRICE_STARTER_ANNUAL", ""),
        features=[
            "5 pairs monitored",
            "4h scan interval",
            "Telegram alerts",
            "Trade journal (30 days)",
            "Basic risk gate",
        ],
    ),
    "pro": PriceConfig(
        tier="pro",
        display_name="Pro",
        monthly_usd=4900,
        annual_usd=49000,
        monthly_price_id=os.getenv("STRIPE_PRICE_PRO_MONTHLY", ""),
        annual_price_id=os.getenv("STRIPE_PRICE_PRO_ANNUAL", ""),
        most_popular=True,
        features=[
            "25 pairs monitored",
            "1h scan interval",
            "ML regime detection (v3)",
            "Telegram + email alerts",
            "Trade journal (unlimited)",
            "Kelly position sizing",
            "Walk-forward validation",
        ],
    ),
    "elite": PriceConfig(
        tier="elite",
        display_name="Elite",
        monthly_usd=9900,
        annual_usd=99000,
        monthly_price_id=os.getenv("STRIPE_PRICE_ELITE_MONTHLY", ""),
        annual_price_id=os.getenv("STRIPE_PRICE_ELITE_ANNUAL", ""),
        features=[
            "Unlimited pairs",
            "15min scan interval",
            "Multi-exchange (Binance, Bybit, OKX, Hyperliquid)",
            "CVD + whale flow signals",
            "API access (full engine)",
            "Priority Telegram support",
            "Alpha decay monitoring",
        ],
    ),
    "team": PriceConfig(
        tier="team",
        display_name="Team",
        monthly_usd=29900,
        annual_usd=299000,          # placeholder — custom pricing in practice
        monthly_price_id=os.getenv("STRIPE_PRICE_TEAM_MONTHLY", ""),
        annual_price_id=os.getenv("STRIPE_PRICE_TEAM_ANNUAL", ""),
        features=[
            "Everything in Elite",
            "Up to 5 seats",
            "Dedicated onboarding",
            "Custom regime tuning",
            "SLA support",
        ],
    ),
}


def get_price_id(tier: str, interval: str) -> str:
    """
    Return the Stripe Price ID for a given tier + billing interval.

    Args:
        tier:     "starter" | "pro" | "elite" | "team"
        interval: "monthly" | "annual"

    Raises:
        ValueError if tier unknown or Price ID not configured.
    """
    plan = PLANS.get(tier.lower())
    if not plan:
        raise ValueError(f"Unknown tier '{tier}'. Valid: {list(PLANS.keys())}")

    price_id = plan.monthly_price_id if interval == "monthly" else plan.annual_price_id

    if not price_id:
        raise ValueError(
            f"Stripe Price ID for {tier}/{interval} not configured. "
            f"Set STRIPE_PRICE_{tier.upper()}_{interval.upper()} in .env"
        )

    return price_id


def list_plans() -> list[dict]:
    """Serialisable plan list for the /billing/plans endpoint."""
    result = []
    for plan in PLANS.values():
        result.append({
            "tier": plan.tier,
            "display_name": plan.display_name,
            "most_popular": plan.most_popular,
            "monthly_usd_cents": plan.monthly_usd,
            "annual_usd_cents": plan.annual_usd,
            "monthly_usd": plan.monthly_usd / 100,
            "annual_usd": plan.annual_usd / 100,
            "annual_savings_pct": 20,
            "features": plan.features,
            "price_ids_configured": {
                "monthly": bool(plan.monthly_price_id),
                "annual": bool(plan.annual_price_id),
            },
        })
    return result

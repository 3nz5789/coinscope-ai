#!/usr/bin/env python3
"""
CoinScopeAI — Stripe TEST MODE product & price setup
=====================================================
Run this ONCE on a machine with internet access to create all products
and prices in your Stripe test environment.

Usage:
    pip install stripe
    python3 scripts/setup_stripe_test_products.py

After running, copy the printed STRIPE_PRICE_* values into:
    coinscope_trading_engine/.env     (existing keys section)
    billing/.env                      (if separate — see billing_server.py)

Requirements:
    - STRIPE_SECRET_KEY set in env OR hardcoded below (test key only)
    - stripe>=5.0.0
"""

import os
import json
import stripe

# ── Key config ────────────────────────────────────────────────────────────────
# STRIPE_SECRET_KEY must be provided via the environment (.env or shell).
# No hardcoded fallback — committing a test key, even partial, is a security anti-pattern.
STRIPE_TEST_SECRET = os.getenv("STRIPE_SECRET_KEY")

if not STRIPE_TEST_SECRET:
    raise SystemExit("❌ ERROR: STRIPE_SECRET_KEY is not set. Put sk_test_... in .env and re-run.")

if not STRIPE_TEST_SECRET.startswith("sk_test_"):
    raise SystemExit("❌ ERROR: Key must start with sk_test_. Do NOT run with live keys.")

stripe.api_key = STRIPE_TEST_SECRET

# ── Canonical pricing — MUST match billing/config.py ─────────────────────────
TIERS = [
    {
        "name": "CoinScopeAI Starter",
        "env_prefix": "STARTER",
        "monthly_cents": 1900,    # $19.00/mo
        "annual_cents": 19000,    # $190.00/yr  (≈16% off)
        "description": (
            "Entry-level access. 5 pairs monitored, 4h scan interval, "
            "Telegram alerts, 30-day trade journal, basic risk gate."
        ),
    },
    {
        "name": "CoinScopeAI Pro",
        "env_prefix": "PRO",
        "monthly_cents": 4900,    # $49.00/mo
        "annual_cents": 49000,    # $490.00/yr  (≈17% off)
        "description": (
            "25 pairs monitored, 1h scan interval, ML regime detection v3, "
            "Telegram + email alerts, unlimited trade journal, Kelly position sizing."
        ),
    },
    {
        "name": "CoinScopeAI Elite",
        "env_prefix": "ELITE",
        "monthly_cents": 9900,    # $99.00/mo
        "annual_cents": 99000,    # $990.00/yr  (≈16% off)
        "description": (
            "Unlimited pairs, 15min scan interval, multi-exchange "
            "(Binance/Bybit/OKX/Hyperliquid), CVD + whale flow signals, "
            "full engine API access, priority support."
        ),
    },
    {
        "name": "CoinScopeAI Team",
        "env_prefix": "TEAM",
        "monthly_cents": 29900,   # $299.00/mo
        "annual_cents": 299000,   # $2,990.00/yr (≈17% off)
        "description": (
            "Everything in Elite. Up to 5 seats, dedicated onboarding, "
            "custom regime tuning, SLA support."
        ),
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def find_or_create_product(name: str, description: str) -> str:
    """Return existing active test-mode product ID, or create new."""
    existing = stripe.Product.search(query=f'name:"{name}" AND active:"true"')
    for p in existing.data:
        if p.name == name and not p.livemode:
            print(f"  ✓ exists  {name} ({p.id})")
            return p.id
        elif p.name == name and p.livemode:
            # Found in live mode — skip, we want test mode only
            continue

    product = stripe.Product.create(name=name, description=description)
    assert not product.livemode, "Created product in live mode — aborting"
    print(f"  + created {name} ({product.id})")
    return product.id


def find_or_create_price(
    product_id: str,
    unit_amount: int,
    interval: str,
    tier_name: str,
) -> str:
    """Return existing matching active price ID, or create new."""
    existing = stripe.Price.list(product=product_id, active=True, limit=20)
    for p in existing.data:
        r = p.recurring
        if (
            p.unit_amount == unit_amount
            and p.currency == "usd"
            and r
            and r.interval == interval
            and r.interval_count == 1
        ):
            print(f"    ✓ exists  ${unit_amount/100:.2f}/{interval} ({p.id})")
            return p.id

    price = stripe.Price.create(
        product=product_id,
        unit_amount=unit_amount,
        currency="usd",
        recurring={"interval": interval, "interval_count": 1},
        lookup_key=f"coinscopeai_{tier_name.lower()}_{interval}",
        transfer_lookup_key=True,
    )
    print(f"    + created ${unit_amount/100:.2f}/{interval} ({price.id})")
    return price.id


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    sep = "=" * 62
    print(sep)
    print("CoinScopeAI — Stripe TEST MODE product/price setup")
    print(sep)

    # Safety check — confirm test mode
    acct = stripe.Account.retrieve()
    livemode_flag = getattr(acct, "livemode", True)
    print(f"\nAccount ID : {acct.id}")
    print(f"Livemode   : {livemode_flag}  ← must be False for test mode\n")

    env_out: dict[str, str] = {}

    for tier in TIERS:
        print(f"── {tier['name']} ──")
        prod_id = find_or_create_product(tier["name"], tier["description"])
        monthly_id = find_or_create_price(
            prod_id, tier["monthly_cents"], "month", tier["env_prefix"]
        )
        annual_id = find_or_create_price(
            prod_id, tier["annual_cents"], "year", tier["env_prefix"]
        )
        env_out[f"STRIPE_PRICE_{tier['env_prefix']}_MONTHLY"] = monthly_id
        env_out[f"STRIPE_PRICE_{tier['env_prefix']}_ANNUAL"] = annual_id
        print()

    print(sep)
    print("✅ Done — copy these into coinscope_trading_engine/.env\n")
    print("── .env block ──────────────────────────────────────────────")
    for k, v in env_out.items():
        print(f"{k}={v}")

    print("\n── JSON (for scripts) ──────────────────────────────────────")
    print(json.dumps(env_out, indent=2))

    # Write to a local file for convenience
    output_path = "stripe_test_price_ids.json"
    with open(output_path, "w") as f:
        json.dump(env_out, f, indent=2)
    print(f"\nAlso saved to: {output_path}")


if __name__ == "__main__":
    main()

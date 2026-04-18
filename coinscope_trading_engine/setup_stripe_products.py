#!/usr/bin/env python3
"""
setup_stripe_products.py — CoinScopeAI Stripe Product & Price Setup
=====================================================================
Run this ONCE to create the four CoinScopeAI subscription products and
monthly prices in your Stripe account (test or live).

After running, copy the printed Price IDs into your .env file:
    STRIPE_STARTER_PRICE_ID=price_...
    STRIPE_PRO_PRICE_ID=price_...
    STRIPE_ELITE_PRICE_ID=price_...
    STRIPE_TEAM_PRICE_ID=price_...

Usage
-----
    cd coinscope_trading_engine
    python setup_stripe_products.py

    # Dry-run (no API calls, just shows what would be created)
    python setup_stripe_products.py --dry-run

    # Use live keys instead of test keys
    python setup_stripe_products.py --live
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Load .env before importing settings
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import stripe


PLANS = [
    {
        "tier":        "starter",
        "name":        "CoinScopeAI — Starter",
        "description": "5 pairs · ML alerts · Basic confluence scoring · Daily report",
        "price_usd":   1900,   # Stripe uses cents
        "metadata":    {"tier": "starter", "source": "coinscopeai"},
    },
    {
        "tier":        "pro",
        "name":        "CoinScopeAI — Pro",
        "description": "20 pairs · All signals · Telegram + webhook · Regime detection · Trade journal",
        "price_usd":   4900,
        "metadata":    {"tier": "pro", "source": "coinscopeai"},
    },
    {
        "tier":        "elite",
        "name":        "CoinScopeAI — Elite",
        "description": "Unlimited pairs · V3 LightGBM ML · API access · Walk-forward validation",
        "price_usd":   9900,
        "metadata":    {"tier": "elite", "source": "coinscopeai"},
    },
    {
        "tier":        "team",
        "name":        "CoinScopeAI — Team",
        "description": "Everything in Elite · 5 seats · White-label · Dedicated onboarding · SLA",
        "price_usd":   29900,
        "metadata":    {"tier": "team", "source": "coinscopeai"},
    },
]


def create_products(dry_run: bool = False) -> dict[str, str]:
    """
    Creates Stripe Products and Prices for each plan.
    Returns a dict mapping tier name → price_id.
    """
    results: dict[str, str] = {}

    for plan in PLANS:
        tier = plan["tier"]
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Creating: {plan['name']} (${plan['price_usd']//100}/mo)")

        if dry_run:
            results[tier] = f"price_DRY_RUN_{tier.upper()}"
            print(f"  → Would create product + price for {tier}")
            continue

        # Check if product already exists
        existing = stripe.Product.search(query=f"metadata['tier']:'{tier}' AND metadata['source']:'coinscopeai'")
        if existing.data:
            product = existing.data[0]
            print(f"  → Reusing existing product: {product.id}")
        else:
            product = stripe.Product.create(
                name        = plan["name"],
                description = plan["description"],
                metadata    = plan["metadata"],
            )
            print(f"  → Created product: {product.id}")

        # Check if a monthly price already exists for this product
        prices = stripe.Price.list(product=product.id, active=True)
        monthly = [p for p in prices.data if p.recurring and p.recurring.interval == "month"]

        if monthly:
            price = monthly[0]
            print(f"  → Reusing existing price: {price.id} (${price.unit_amount//100}/mo)")
        else:
            price = stripe.Price.create(
                product            = product.id,
                unit_amount        = plan["price_usd"],
                currency           = "usd",
                recurring          = {"interval": "month"},
                metadata           = plan["metadata"],
            )
            print(f"  → Created price: {price.id} (${price.unit_amount//100}/mo)")

        results[tier] = price.id

    return results


def print_env_block(results: dict[str, str]) -> None:
    """Print the .env snippet to paste."""
    print("\n" + "=" * 60)
    print("Add these lines to your .env file:")
    print("=" * 60)
    print(f"STRIPE_STARTER_PRICE_ID={results.get('starter', '')}")
    print(f"STRIPE_PRO_PRICE_ID={results.get('pro', '')}")
    print(f"STRIPE_ELITE_PRICE_ID={results.get('elite', '')}")
    print(f"STRIPE_TEAM_PRICE_ID={results.get('team', '')}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create CoinScopeAI Stripe products")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without calling Stripe API")
    parser.add_argument("--live",    action="store_true", help="Use STRIPE_SECRET_KEY (sk_live_...)")
    args = parser.parse_args()

    # Pick the right key
    if args.live:
        key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not key.startswith("sk_live_"):
            print("ERROR: --live requires STRIPE_SECRET_KEY=sk_live_... in .env")
            sys.exit(1)
        print("⚠️  Using LIVE Stripe key — charges will be real!")
    else:
        key = os.environ.get("STRIPE_SECRET_KEY", "")
        if not key:
            print("ERROR: STRIPE_SECRET_KEY not set in .env")
            sys.exit(1)
        if not key.startswith("sk_test_"):
            print(f"WARNING: Key does not start with sk_test_. Got: {key[:12]}...")
        print(f"Using TEST Stripe key: {key[:20]}...")

    if not args.dry_run:
        stripe.api_key = key

    print(f"\nCoinScopeAI Stripe Product Setup {'(DRY RUN)' if args.dry_run else ''}")
    print("-" * 50)

    results = create_products(dry_run=args.dry_run)
    print_env_block(results)

    if not args.dry_run:
        print("\n✅ Done! Copy the Price IDs above into your .env file.")
        print("   Then set STRIPE_WEBHOOK_SECRET after registering your webhook endpoint:")
        print("   https://dashboard.stripe.com/webhooks")
        print("   Webhook URL: https://your-domain.com/billing/webhook")
        print("   Events to subscribe:")
        print("     • checkout.session.completed")
        print("     • customer.subscription.updated")
        print("     • customer.subscription.deleted")
        print("     • invoice.payment_succeeded")
        print("     • invoice.payment_failed")


if __name__ == "__main__":
    main()

"""
Stripe Webhook Handler — FastAPI application for billing events.

Security model:
  1. Every request MUST pass stripe.Webhook.construct_event() signature check.
  2. Signature check uses STRIPE_WEBHOOK_SECRET (whsec_...) from env.
  3. Invalid signatures → HTTP 400 (not 401/403 — Stripe expects 4xx to retry).
  4. Each event is checked for prior processing (idempotency) before any DB write.
  5. All event handlers are idempotent — safe to replay on retry.

Handled events:
  checkout.session.completed      → New customer provisioned
  customer.subscription.updated   → Tier change / renewal / cancellation flagged
  customer.subscription.deleted   → Access revoked
  invoice.payment_succeeded       → Renewal confirmed, send receipt notification
  invoice.payment_failed          → Alert + mark past_due

Price → Tier resolution:
  Reads STRIPE_PRICE_{TIER}_{INTERVAL} env vars to build the lookup table.
  Falls back to 'unknown' tier if price ID is not in the map.

Runs on port 8002 (separate from main engine on 8001).
"""

import os
import json
import logging
import stripe
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    SubscriptionRecord,
    SubscriptionTier,
    SubscriptionStatus,
    BillingInterval,
)
from .subscription_store import SubscriptionStore
from .notifications import BillingNotifier
from .customer_portal import router as portal_router

logger = logging.getLogger(__name__)

# ── Stripe client ─────────────────────────────────────────────────────────────
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
if not stripe.api_key:
    logger.warning("[Billing] STRIPE_SECRET_KEY not set — Stripe calls will fail")


def _webhook_secret() -> str:
    """Read STRIPE_WEBHOOK_SECRET lazily so test fixtures can override it."""
    return os.getenv("STRIPE_WEBHOOK_SECRET", "")


# ── Price ID → Tier/Interval lookup ──────────────────────────────────────────

def _build_price_map() -> dict[str, tuple[SubscriptionTier, BillingInterval]]:
    """
    Build reverse map: price_xxx → (tier, interval).
    Reads STRIPE_PRICE_<TIER>_<INTERVAL> env vars.
    """
    mapping: dict[str, tuple[SubscriptionTier, BillingInterval]] = {}
    pairs = [
        ("STARTER", SubscriptionTier.STARTER),
        ("PRO",     SubscriptionTier.PRO),
        ("ELITE",   SubscriptionTier.ELITE),
        ("TEAM",    SubscriptionTier.TEAM),
    ]
    for env_tier, tier_enum in pairs:
        for env_interval, interval_enum in [
            ("MONTHLY", BillingInterval.MONTHLY),
            ("ANNUAL",  BillingInterval.ANNUAL),
        ]:
            price_id = os.getenv(f"STRIPE_PRICE_{env_tier}_{env_interval}", "")
            if price_id and price_id.startswith("price_"):
                mapping[price_id] = (tier_enum, interval_enum)
    return mapping

PRICE_MAP: dict[str, tuple[SubscriptionTier, BillingInterval]] = _build_price_map()

def resolve_price(price_id: str) -> tuple[SubscriptionTier, BillingInterval]:
    """Return (tier, interval) for a Stripe price ID, or (UNKNOWN, MONTHLY)."""
    return PRICE_MAP.get(price_id, (SubscriptionTier.UNKNOWN, BillingInterval.MONTHLY))

# ── App + dependencies ────────────────────────────────────────────────────────

app = FastAPI(
    title="CoinScopeAI Billing Webhook",
    version="1.0.0",
    docs_url="/billing/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount Customer Portal router (POST /billing/portal/session, GET /billing/portal/config)
app.include_router(portal_router)

# Initialized lazily on first request (allows test patching)
_store_instance: "SubscriptionStore | None" = None
_notifier_instance: "BillingNotifier | None" = None


def _get_store() -> SubscriptionStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = SubscriptionStore()
    return _store_instance


def _get_notifier() -> BillingNotifier:
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = BillingNotifier()
    return _notifier_instance

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/billing/health")
async def health():
    """Health check — confirms billing server is live."""
    return {
        "status": "ok",
        "service": "billing-webhook",
        "timestamp": datetime.utcnow().isoformat(),
        "stripe_configured": bool(stripe.api_key),
        "webhook_secret_configured": bool(_webhook_secret()),
        "price_ids_loaded": len(PRICE_MAP),
    }

@app.get("/billing/subscriptions")
async def list_subscriptions():
    """Internal endpoint — list all active subscriptions."""
    subs = _get_store().list_active_subscriptions()
    return {
        "count": len(subs),
        "subscriptions": [s.model_dump(mode="json") for s in subs],
    }

@app.get("/billing/customer/{customer_id}")
async def get_customer(customer_id: str):
    """Internal endpoint — lookup subscription by Stripe customer ID."""
    sub = _get_store().get_subscription_by_customer(customer_id)
    if not sub:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return sub.model_dump(mode="json")

# ── Main webhook endpoint ─────────────────────────────────────────────────────

@app.post("/billing/webhook")
async def stripe_webhook(request: Request):
    """
    Receives all Stripe events.

    Security:
      - Reads raw body BEFORE any parsing (required for signature check)
      - stripe.Webhook.construct_event() verifies HMAC-SHA256 signature
      - Returns 400 on bad signature so Stripe will retry
      - Returns 200 immediately once signature passes (prevents timeout)
      - All processing happens synchronously within the request lifetime
        (acceptable for webhook scale; upgrade to background tasks if needed)
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # ── 1. Signature verification ─────────────────────────────────────────
    webhook_secret = _webhook_secret()
    if webhook_secret:
        try:
            # construct_event verifies the HMAC-SHA256 signature.
            # In stripe SDK v15 it returns a typed object — we use it only
            # for sig verification, then parse the raw payload as a plain dict.
            stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning(f"[Billing] Invalid signature: {exc}")
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
        except Exception as exc:
            logger.error(f"[Billing] Webhook parse error: {exc}")
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        # Dev fallback — skipping sig check (NEVER use in production)
        logger.warning("[Billing] STRIPE_WEBHOOK_SECRET not set — skipping signature check")

    # Parse payload as plain dict for handler compatibility (SDK-version agnostic)
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id   = event.get("id", "unknown")
    event_type = event.get("type", "unknown")
    logger.info(f"[Billing] Received event {event_id} ({event_type})")

    # ── 2. Idempotency check ──────────────────────────────────────────────
    if _get_store().is_event_processed(event_id):
        logger.info(f"[Billing] Duplicate event {event_id} — ignoring")
        return JSONResponse({"received": True, "duplicate": True})

    # ── 3. Route to handler ───────────────────────────────────────────────
    try:
        data = event.get("data", {}).get("object", {})
        handler = EVENT_HANDLERS.get(event_type)
        if handler:
            handler(event_id, event_type, data)
        else:
            logger.debug(f"[Billing] Unhandled event type: {event_type}")

    except Exception as exc:
        logger.exception(f"[Billing] Handler error for {event_id}: {exc}")
        _get_notifier().webhook_error(event_id, str(exc))
        # Return 500 so Stripe retries — do NOT swallow silently
        raise HTTPException(status_code=500, detail="Internal handler error")

    return JSONResponse({"received": True, "event_id": event_id})

# ── Event handlers ────────────────────────────────────────────────────────────

def _handle_checkout_completed(event_id: str, event_type: str, data: dict):
    """
    checkout.session.completed
    Fired when a customer completes the Stripe Checkout flow.
    Creates the subscription record and sends the welcome notification.
    """
    session_id       = data.get("id", "")
    customer_id      = data.get("customer", "")
    subscription_id  = data.get("subscription", "")
    customer_email   = data.get("customer_details", {}).get("email") or data.get("customer_email")
    mode             = data.get("mode", "")

    if mode != "subscription":
        logger.info(f"[Billing] checkout.session.completed non-subscription mode ({mode}) — skipping")
        _get_store().mark_event_processed(event_id, event_type, customer_id)
        return

    if not subscription_id:
        logger.warning(f"[Billing] No subscription_id in checkout session {session_id}")
        _get_store().mark_event_processed(event_id, event_type, customer_id)
        return

    # Resolve tier from line items — fetch subscription from Stripe to get price_id
    tier, interval = _resolve_tier_from_subscription_id(subscription_id)

    now = datetime.now(timezone.utc)
    record = SubscriptionRecord(
        customer_id=customer_id,
        email=customer_email,
        stripe_subscription_id=subscription_id,
        tier=tier,
        status=SubscriptionStatus.ACTIVE,
        interval=interval,
        cancel_at_period_end=False,
        created_at=now,
        updated_at=now,
    )
    _get_store().upsert_subscription(record)
    _get_store().mark_event_processed(event_id, event_type, customer_id, subscription_id)

    _get_notifier().new_subscription(
        email=customer_email,
        tier=str(tier),
        interval=str(interval),
        customer_id=customer_id,
    )
    logger.info(f"[Billing] New subscription provisioned: {customer_id} / {tier}")


def _handle_subscription_updated(event_id: str, event_type: str, data: dict):
    """
    customer.subscription.updated
    Covers: tier upgrades, downgrades, renewals, cancel_at_period_end flag changes.
    Fetches existing record to detect tier changes for notification routing.
    """
    subscription_id      = data.get("id", "")
    customer_id          = data.get("customer", "")
    status_raw           = data.get("status", "incomplete")
    cancel_at_period_end = data.get("cancel_at_period_end", False)
    current_period_end   = _ts_to_dt(data.get("current_period_end"))

    # Resolve tier from plan items
    tier, interval = _resolve_tier_from_sub_object(data)

    try:
        status = SubscriptionStatus(status_raw)
    except ValueError:
        status = SubscriptionStatus.INCOMPLETE

    # Check existing record for tier-change notification
    existing = _get_store().get_subscription_by_stripe_id(subscription_id)
    old_tier = getattr(existing.tier, "value", existing.tier) if existing else None

    now = datetime.now(timezone.utc)
    record = SubscriptionRecord(
        customer_id=customer_id,
        email=existing.email if existing else None,
        stripe_subscription_id=subscription_id,
        tier=tier,
        status=status,
        interval=interval,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
    _get_store().upsert_subscription(record)
    _get_store().mark_event_processed(event_id, event_type, customer_id, subscription_id)

    tier_str = getattr(tier, "value", tier)
    email    = existing.email if existing else None

    # Tier change notifications
    if old_tier and old_tier != tier_str and old_tier != "unknown":
        tier_order = {"starter": 1, "pro": 2, "elite": 3, "team": 4, "unknown": 0}
        if tier_order.get(tier_str, 0) > tier_order.get(old_tier, 0):
            _get_notifier().subscription_upgraded(email, old_tier, tier_str, customer_id)
        else:
            _get_notifier().subscription_downgraded(email, old_tier, tier_str, customer_id)

    # Past-due notification
    if status == SubscriptionStatus.PAST_DUE:
        _get_notifier().subscription_past_due(customer_id, email, tier_str)

    logger.info(
        f"[Billing] Subscription updated: {customer_id} / {tier_str} / {status_raw}"
    )


def _handle_subscription_deleted(event_id: str, event_type: str, data: dict):
    """
    customer.subscription.deleted
    Access should be revoked at period end (cancel_at_period_end=True was set)
    or immediately if canceled mid-cycle.
    """
    subscription_id = data.get("id", "")
    customer_id     = data.get("customer", "")

    existing = _get_store().get_subscription_by_stripe_id(subscription_id)
    email    = existing.email if existing else None
    tier     = str(existing.tier) if existing else "unknown"

    _get_store().cancel_subscription(customer_id)
    _get_store().mark_event_processed(event_id, event_type, customer_id, subscription_id)

    _get_notifier().subscription_canceled(
        email=email,
        tier=tier,
        customer_id=customer_id,
        at_period_end=data.get("cancel_at_period_end", False),
    )
    logger.info(f"[Billing] Subscription deleted: {customer_id}")


def _handle_invoice_payment_succeeded(event_id: str, event_type: str, data: dict):
    """
    invoice.payment_succeeded
    Fires on new subscriptions AND renewals. Skip 'amount_paid == 0' (free trials).
    """
    customer_id     = data.get("customer", "")
    subscription_id = data.get("subscription", "")
    amount_paid     = data.get("amount_paid", 0)   # cents
    currency        = data.get("currency", "usd")

    if amount_paid == 0:
        logger.debug(f"[Billing] Zero-amount invoice for {customer_id} — skipping notify")
        _get_store().mark_event_processed(event_id, event_type, customer_id, subscription_id)
        return

    existing = _get_store().get_subscription_by_customer(customer_id)
    tier     = getattr(existing.tier, "value", "unknown") if existing else "unknown"
    email    = existing.email if existing else None

    amount_usd = amount_paid / 100.0
    _get_store().mark_event_processed(event_id, event_type, customer_id, subscription_id)

    _get_notifier().payment_succeeded(
        email=email,
        amount_usd=amount_usd,
        tier=tier,
        customer_id=customer_id,
    )
    logger.info(f"[Billing] Payment succeeded: {customer_id} ${amount_usd:.2f}")


def _handle_invoice_payment_failed(event_id: str, event_type: str, data: dict):
    """
    invoice.payment_failed
    Payment retry scheduled by Stripe. Alert immediately — customer may need action.
    """
    customer_id          = data.get("customer", "")
    subscription_id      = data.get("subscription", "")
    amount_due           = data.get("amount_due", 0)   # cents
    next_payment_attempt = _ts_to_dt(data.get("next_payment_attempt"))

    existing = _get_store().get_subscription_by_customer(customer_id)
    tier     = getattr(existing.tier, "value", "unknown") if existing else "unknown"
    email    = existing.email if existing else None

    _get_store().mark_event_processed(event_id, event_type, customer_id, subscription_id)

    _get_notifier().payment_failed(
        email=email,
        amount_usd=amount_due / 100.0,
        tier=tier,
        customer_id=customer_id,
        next_attempt=next_payment_attempt,
    )
    logger.warning(f"[Billing] Payment FAILED: {customer_id} ${amount_due/100:.2f}")


# ── Handler registry ──────────────────────────────────────────────────────────

EVENT_HANDLERS = {
    "checkout.session.completed":     _handle_checkout_completed,
    "customer.subscription.updated":  _handle_subscription_updated,
    "customer.subscription.deleted":  _handle_subscription_deleted,
    "invoice.payment_succeeded":      _handle_invoice_payment_succeeded,
    "invoice.payment_failed":         _handle_invoice_payment_failed,
}

# ── Private helpers ───────────────────────────────────────────────────────────

def _ts_to_dt(ts: Optional[int]) -> Optional[datetime]:
    """Convert Unix timestamp (int) to UTC datetime, or None."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _resolve_tier_from_subscription_id(
    subscription_id: str,
) -> tuple[SubscriptionTier, BillingInterval]:
    """
    Fetch the subscription from Stripe API and extract the price ID.
    Falls back to UNKNOWN if Stripe call fails.
    """
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        return _resolve_tier_from_sub_object(sub)
    except Exception as exc:
        logger.error(f"[Billing] Failed to fetch subscription {subscription_id}: {exc}")
        return (SubscriptionTier.UNKNOWN, BillingInterval.MONTHLY)


def _resolve_tier_from_sub_object(
    sub: dict,
) -> tuple[SubscriptionTier, BillingInterval]:
    """
    Extract price_id from subscription object items and resolve via PRICE_MAP.
    Handles both dict (from webhook payload) and stripe.Subscription object.
    """
    try:
        items = sub.get("items", {})
        # items may be a dict (Stripe object) or plain dict
        item_list = items.get("data", []) if isinstance(items, dict) else []
        if item_list:
            price_id = item_list[0].get("price", {}).get("id", "")
            if price_id:
                return resolve_price(price_id)
    except Exception as exc:
        logger.debug(f"[Billing] Could not extract price_id: {exc}")
    return (SubscriptionTier.UNKNOWN, BillingInterval.MONTHLY)

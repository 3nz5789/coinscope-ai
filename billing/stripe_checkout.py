"""
CoinScopeAI Billing — Stripe Checkout Session API
==================================================
Standalone FastAPI service (port 8002) that handles:

  POST /billing/checkout/session   — create Stripe Checkout Session
  POST /billing/webhook            — handle Stripe webhook events
  GET  /billing/plans              — list pricing tiers
  GET  /billing/health             — health check

Run:
    uvicorn billing.stripe_checkout:app --port 8002 --reload

Environment variables required:
    STRIPE_SECRET_KEY              sk_test_...
    STRIPE_PUBLISHABLE_KEY         pk_test_...
    STRIPE_WEBHOOK_SECRET          whsec_... (from `stripe listen --forward-to ...`)
    STRIPE_PRICE_<TIER>_<INTERVAL> price_... (8 total — see .env.template)

Frontend URLs (set to match your deployed dashboard):
    BILLING_SUCCESS_URL            https://yourdomain.com/billing/success
    BILLING_CANCEL_URL             https://yourdomain.com/pricing
"""

import os
import logging
from typing import Literal

import stripe
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from billing.config import get_price_id, list_plans

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("billing")

# ── Stripe SDK init ───────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
BILLING_SUCCESS_URL = os.getenv(
    "BILLING_SUCCESS_URL",
    "http://localhost:5173/billing/success?session_id={CHECKOUT_SESSION_ID}",
)
BILLING_CANCEL_URL = os.getenv(
    "BILLING_CANCEL_URL",
    "http://localhost:5173/pricing",
)

if not STRIPE_SECRET_KEY:
    log.warning("STRIPE_SECRET_KEY not set — billing endpoints will fail at runtime")

stripe.api_key = STRIPE_SECRET_KEY

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CoinScopeAI Billing API",
    version="1.0.0",
    description="Stripe Checkout Session API — TEST MODE",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://coinscopedash-tltanhwx.manus.space",
        "https://coinscopedash-cv5ce7m8.manus.space",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Request / Response Models ─────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    tier: Literal["starter", "pro", "elite", "team"]
    interval: Literal["monthly", "annual"] = "monthly"
    customer_email: str | None = None   # pre-fills Stripe checkout form
    metadata: dict | None = None        # arbitrary k/v stored on Stripe Session

    @field_validator("tier")
    @classmethod
    def tier_lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("interval")
    @classmethod
    def interval_lower(cls, v: str) -> str:
        return v.lower()


class CheckoutResponse(BaseModel):
    session_id: str
    session_url: str
    tier: str
    interval: str
    amount_usd: float
    publishable_key: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/billing/health")
async def health():
    """Health check — also reports whether Stripe key is loaded."""
    return {
        "status": "ok",
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "webhook_configured": bool(STRIPE_WEBHOOK_SECRET),
        "mode": "test" if STRIPE_SECRET_KEY.startswith("sk_test") else "live",
    }


@app.get("/billing/plans")
async def get_plans():
    """
    Return all pricing tiers with amounts, features, and whether
    their Stripe Price IDs are configured.
    """
    return {"plans": list_plans()}


@app.post("/billing/checkout/session", response_model=CheckoutResponse)
async def create_checkout_session(req: CheckoutRequest):
    """
    Create a Stripe Checkout Session for the requested tier + interval.

    Returns a session_url the frontend should redirect to.
    Stripe handles card collection, 3DS, receipts, and SCA compliance.

    Example request:
        POST /billing/checkout/session
        { "tier": "pro", "interval": "monthly", "customer_email": "user@example.com" }
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured — set STRIPE_SECRET_KEY in .env")

    # Resolve the Stripe Price ID for this tier + interval
    try:
        price_id = get_price_id(req.tier, req.interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Build session metadata
    session_metadata = {
        "tier": req.tier,
        "interval": req.interval,
        "source": "coinscopeai_dashboard",
    }
    if req.metadata:
        session_metadata.update(req.metadata)

    # Build session params
    params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": BILLING_SUCCESS_URL,
        "cancel_url": BILLING_CANCEL_URL,
        "metadata": session_metadata,
        "subscription_data": {
            "metadata": session_metadata,
        },
        # Allow promotion codes (coupon box on checkout page)
        "allow_promotion_codes": True,
        # Collect billing address for tax purposes
        "billing_address_collection": "auto",
    }

    # Pre-fill email if provided
    if req.customer_email:
        params["customer_email"] = req.customer_email

    try:
        session = stripe.checkout.Session.create(**params)
    except stripe.InvalidRequestError as exc:
        log.error("Stripe InvalidRequestError: %s", exc)
        raise HTTPException(status_code=400, detail=f"Stripe error: {exc.user_message}")
    except stripe.AuthenticationError:
        log.error("Stripe AuthenticationError — check STRIPE_SECRET_KEY")
        raise HTTPException(status_code=503, detail="Stripe authentication failed")
    except stripe.StripeError as exc:
        log.error("Stripe error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(exc)}")

    # Look up display amount for response
    from billing.config import PLANS
    plan = PLANS[req.tier]
    amount = plan.annual_usd / 100 if req.interval == "annual" else plan.monthly_usd / 100

    log.info("Checkout session created | tier=%s interval=%s session=%s", req.tier, req.interval, session.id)

    return CheckoutResponse(
        session_id=session.id,
        session_url=session.url,
        tier=req.tier,
        interval=req.interval,
        amount_usd=amount,
        publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
    )


@app.post("/billing/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """
    Stripe webhook endpoint.

    Configure in Stripe Dashboard → Developers → Webhooks:
      URL:    https://<your-domain>/billing/webhook
      Events: checkout.session.completed
              customer.subscription.updated
              customer.subscription.deleted
              invoice.payment_failed

    For local testing use the Stripe CLI:
      stripe listen --forward-to localhost:8002/billing/webhook
    """
    if not STRIPE_WEBHOOK_SECRET:
        log.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        return JSONResponse({"warning": "webhook secret not configured"}, status_code=200)

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature,
            secret=STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        log.warning("Webhook: invalid payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        log.warning("Webhook: invalid signature — possible replay or wrong secret")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    log.info("Webhook received: %s", event_type)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(event["data"]["object"])

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event["data"]["object"])

    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event["data"]["object"])

    else:
        log.debug("Unhandled event type: %s — ignored", event_type)

    return JSONResponse({"received": True}, status_code=200)


# ── Webhook Handlers ──────────────────────────────────────────────────────────

def _handle_checkout_completed(session: dict) -> None:
    """
    Fired when a customer completes payment.
    At this point the subscription is active and the invoice is paid.

    TODO (post-validation): write to users DB / Notion to activate seat.
    """
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    email = session.get("customer_email") or session.get("customer_details", {}).get("email")
    tier = session.get("metadata", {}).get("tier", "unknown")
    interval = session.get("metadata", {}).get("interval", "unknown")

    log.info(
        "✅ Checkout completed | email=%s tier=%s interval=%s customer=%s sub=%s",
        email, tier, interval, customer_id, subscription_id,
    )

    # ── Fulfilment stub ───────────────────────────────────────────────────────
    # Replace this block with your actual user provisioning logic:
    #
    #   1. Look up or create user by email in your DB
    #   2. Set user.plan = tier, user.billing_interval = interval
    #   3. Store stripe_customer_id and stripe_subscription_id
    #   4. Send welcome / activation email
    #   5. Post Telegram alert: "💳 New subscriber: {email} → {tier}"
    #
    # Example Telegram alert (uncomment when bot is connected):
    # from fixed.telegram_alerts import send_telegram_message
    # send_telegram_message(f"💳 New subscriber: {email} → {tier} ({interval})")
    # ─────────────────────────────────────────────────────────────────────────


def _handle_subscription_updated(subscription: dict) -> None:
    """
    Fired on plan change (upgrade / downgrade) or renewal.
    Status can be: active | past_due | canceled | trialing | unpaid
    """
    sub_id = subscription.get("id")
    status = subscription.get("status")
    customer_id = subscription.get("customer")
    tier = subscription.get("metadata", {}).get("tier", "unknown")

    log.info(
        "🔄 Subscription updated | sub=%s status=%s customer=%s tier=%s",
        sub_id, status, customer_id, tier,
    )

    # TODO: sync subscription status to your user DB


def _handle_subscription_deleted(subscription: dict) -> None:
    """Fired when subscription is cancelled (at period end or immediately)."""
    sub_id = subscription.get("id")
    customer_id = subscription.get("customer")
    tier = subscription.get("metadata", {}).get("tier", "unknown")

    log.info(
        "❌ Subscription cancelled | sub=%s customer=%s tier=%s",
        sub_id, customer_id, tier,
    )

    # TODO: revoke access for customer in your DB


def _handle_payment_failed(invoice: dict) -> None:
    """
    Fired when a subscription renewal payment fails.
    Stripe will retry automatically (Smart Retries), but you should notify
    the customer and optionally send a Telegram alert.
    """
    customer_id = invoice.get("customer")
    amount = invoice.get("amount_due", 0) / 100
    attempt_count = invoice.get("attempt_count", 1)

    log.warning(
        "⚠️  Payment failed | customer=%s amount=$%.2f attempt=%d",
        customer_id, amount, attempt_count,
    )

    # TODO: send dunning email, Telegram alert to Mohammed


# ── Dev entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=False)

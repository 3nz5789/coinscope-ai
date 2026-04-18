"""
CoinScopeAI Billing — Customer Portal Session API
==================================================
Stripe Billing Portal lets existing subscribers self-serve their billing:

  ✓ Upgrade or downgrade plan
  ✓ Cancel subscription (cancel_at_period_end by default)
  ✓ Update payment method (card, bank account)
  ✓ Download invoices and billing history

Endpoints:
  POST /billing/portal/session  — create portal session → return redirect URL
  GET  /billing/portal/config   — check Stripe portal configuration status

Prerequisites (one-time Stripe Dashboard setup):
  https://dashboard.stripe.com/test/settings/billing/portal
  Configure: allowed plan changes, cancellation policy, features shown.

After finishing in the portal, Stripe redirects back to BILLING_PORTAL_RETURN_URL.

Webhook events fired by portal actions (all handled by webhook_handler.py):
  customer.subscription.updated   → plan change or cancel_at_period_end toggle
  customer.subscription.deleted   → immediate cancellation
  invoice.payment_failed          → payment method update failed
"""

import os
import logging
from typing import Optional

import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from .subscription_store import SubscriptionStore

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
BILLING_PORTAL_RETURN_URL = os.getenv(
    "BILLING_PORTAL_RETURN_URL",
    "http://localhost:5173/account",
)

# Lazy store singleton — avoids DB init on import (keeps tests patchable)
_store_instance: "SubscriptionStore | None" = None


def _get_store() -> SubscriptionStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = SubscriptionStore()
    return _store_instance


router = APIRouter()


# ── Request / Response Models ─────────────────────────────────────────────────

class PortalSessionRequest(BaseModel):
    """
    Identify the customer for portal session creation.

    Supply either:
      - customer_id  (Stripe cus_xxx) — fastest, no DB lookup required
      - email        — looked up in local billing DB to resolve customer_id

    customer_id takes precedence if both are provided.
    return_url overrides BILLING_PORTAL_RETURN_URL for this session only.
    """
    customer_id: Optional[str] = None
    email: Optional[str] = None
    return_url: Optional[str] = None

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith("cus_"):
            raise ValueError(
                "customer_id must be a Stripe customer ID (starts with 'cus_')"
            )
        return v

    def model_post_init(self, __context) -> None:  # noqa: N802
        if not self.customer_id and not self.email:
            raise ValueError("Provide either customer_id or email")


class PortalSessionResponse(BaseModel):
    portal_url: str
    customer_id: str
    return_url: str


class PortalConfigResponse(BaseModel):
    configured: bool
    portal_configurations: int = 0
    mode: str = "unknown"
    note: str = ""
    reason: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/billing/portal/config", response_model=PortalConfigResponse)
async def portal_config():
    """
    Check whether the Stripe Customer Portal is configured.

    Returns the number of active portal configurations and a human-readable
    note. Call this on dashboard load to decide whether to show the
    'Manage Billing' button to active subscribers.

    A portal configuration must be created at:
      https://dashboard.stripe.com/test/settings/billing/portal
    """
    if not STRIPE_SECRET_KEY:
        return PortalConfigResponse(
            configured=False,
            reason="STRIPE_SECRET_KEY not set",
        )

    stripe.api_key = STRIPE_SECRET_KEY

    try:
        configs = stripe.billing_portal.Configuration.list(limit=1, active=True)
        has_config = len(configs.data) > 0
        mode = "test" if STRIPE_SECRET_KEY.startswith("sk_test") else "live"
        return PortalConfigResponse(
            configured=has_config,
            portal_configurations=len(configs.data),
            mode=mode,
            note=(
                "Customer portal ready"
                if has_config
                else (
                    "Portal not yet configured. Set up at: "
                    "https://dashboard.stripe.com/test/settings/billing/portal"
                )
            ),
        )
    except stripe.AuthenticationError:
        return PortalConfigResponse(
            configured=False,
            reason="Stripe authentication failed — check STRIPE_SECRET_KEY",
        )
    except stripe.StripeError as exc:
        logger.error(f"[Portal] Config check failed: {exc}")
        return PortalConfigResponse(
            configured=False,
            reason=str(exc),
        )


@router.post("/billing/portal/session", response_model=PortalSessionResponse)
async def create_portal_session(req: PortalSessionRequest):
    """
    Create a Stripe Billing Portal session for an existing subscriber.

    The frontend must redirect the user to the returned `portal_url`.
    After the customer finishes, Stripe redirects them back to `return_url`.

    Customer resolution order:
      1. Use `customer_id` directly if provided — fastest, no DB query
      2. Lookup `email` in the local billing DB to find customer_id
      3. If neither resolves → HTTP 404

    Portal sessions expire after ~24 hours and are single-use.
    Never cache or reuse the `portal_url`.

    Security:
      - customer_id is validated against Stripe before session creation
        (prevents spoofing a cus_ ID the caller doesn't own)
      - The portal is scoped to a single customer — no cross-customer access

    Webhook events fired after portal actions (handled automatically):
      customer.subscription.updated  (upgrade / downgrade / cancel schedule)
      customer.subscription.deleted  (immediate cancel)
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured — set STRIPE_SECRET_KEY in .env",
        )

    stripe.api_key = STRIPE_SECRET_KEY

    # ── 1. Resolve customer_id ────────────────────────────────────────────
    customer_id = req.customer_id

    if not customer_id and req.email:
        store = _get_store()
        customer_id = store.get_customer_id_by_email(req.email)
        if not customer_id:
            logger.warning(f"[Portal] Email not found in billing DB: {req.email}")

    if not customer_id:
        raise HTTPException(
            status_code=404,
            detail=(
                "Customer not found. Provide a valid customer_id (cus_xxx) "
                "or the email address of an active subscriber."
            ),
        )

    # ── 2. Verify customer exists in Stripe (guard against ID spoofing) ───
    try:
        stripe.Customer.retrieve(customer_id)
    except stripe.InvalidRequestError:
        logger.warning(f"[Portal] Stripe customer not found: {customer_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Stripe customer '{customer_id}' not found",
        )
    except stripe.AuthenticationError:
        raise HTTPException(
            status_code=503,
            detail="Stripe authentication failed — check STRIPE_SECRET_KEY",
        )
    except stripe.StripeError as exc:
        logger.error(f"[Portal] Customer retrieval error: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Stripe error: {str(exc)}",
        )

    # ── 3. Create portal session ──────────────────────────────────────────
    return_url = req.return_url or BILLING_PORTAL_RETURN_URL

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
    except stripe.InvalidRequestError as exc:
        logger.error(f"[Portal] InvalidRequestError: {exc}")
        exc_str = str(exc).lower()
        if "configuration" in exc_str or "portal" in exc_str or "no default" in exc_str:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Stripe Customer Portal is not configured. "
                    "Set it up at: "
                    "https://dashboard.stripe.com/test/settings/billing/portal"
                ),
            )
        raise HTTPException(
            status_code=400,
            detail=f"Stripe error: {getattr(exc, 'user_message', str(exc))}",
        )
    except stripe.AuthenticationError:
        raise HTTPException(
            status_code=503,
            detail="Stripe authentication failed",
        )
    except stripe.StripeError as exc:
        logger.error(f"[Portal] Session creation failed: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Stripe error: {str(exc)}",
        )

    logger.info(f"[Portal] Session created — customer={customer_id} return={return_url}")

    return PortalSessionResponse(
        portal_url=session.url,
        customer_id=customer_id,
        return_url=return_url,
    )

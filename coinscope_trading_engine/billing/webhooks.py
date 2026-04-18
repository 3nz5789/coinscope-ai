"""
billing/webhooks.py — CoinScopeAI Stripe Webhook Event Handlers
================================================================
Processes inbound Stripe webhook events and keeps the local
subscription state file in sync.

Handled events
--------------
  checkout.session.completed          → subscription created / upgraded
  customer.subscription.updated       → plan change, renewal, pause
  customer.subscription.deleted       → cancellation
  invoice.payment_succeeded           → renewal confirmed
  invoice.payment_failed              → payment failure, notify operator
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# State file shared with stripe_gateway.py
_STATE_FILE = Path(__file__).parent / "subscription_state.json"


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def handle_stripe_event(event: dict) -> None:
    """Route a Stripe event object to the appropriate handler."""
    event_type = event.get("type", "")
    handler    = _HANDLERS.get(event_type)

    if handler:
        try:
            await handler(event["data"]["object"])
        except Exception as exc:
            logger.error("Error handling Stripe event %s: %s", event_type, exc)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def _on_checkout_completed(session: dict) -> None:
    """
    checkout.session.completed
    Fired when a user completes payment. Extract subscription details and
    persist them to the state file.
    """
    sub_id      = session.get("subscription")
    customer_id = session.get("customer")
    tier        = (session.get("metadata") or {}).get("tier", "pro")

    if not sub_id:
        logger.warning("checkout.session.completed has no subscription ID — skipping")
        return

    # Fetch full subscription object for period end
    import stripe
    try:
        sub    = stripe.Subscription.retrieve(sub_id)
        status = sub.status
        period_end            = sub.current_period_end
        cancel_at_period_end  = sub.cancel_at_period_end
    except Exception as exc:
        logger.warning("Could not fetch subscription after checkout: %s", exc)
        status                = "active"
        period_end            = None
        cancel_at_period_end  = False

    state = _load_state()
    state.update({
        "subscription_id":      sub_id,
        "customer_id":          customer_id,
        "tier":                 tier,
        "status":               status,
        "current_period_end":   period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "last_checked":         _now(),
    })
    _save_state(state)
    logger.info(
        "✅ Subscription activated | tier=%s customer=%s sub=%s",
        tier, customer_id, sub_id,
    )

    # Telegram notification (best-effort)
    await _notify(
        f"🎉 <b>New subscription activated!</b>\n"
        f"Plan: <b>{tier.upper()}</b>\n"
        f"Customer: {customer_id}\n"
        f"Subscription: {sub_id}"
    )


async def _on_subscription_updated(sub: dict) -> None:
    """
    customer.subscription.updated
    Handles plan upgrades, downgrades, renewals, and pauses.
    """
    state = _load_state()

    # Determine new tier from price metadata if available
    items     = sub.get("items", {}).get("data", [])
    new_tier  = state.get("tier", "pro")
    if items:
        price_meta = (items[0].get("price") or {}).get("metadata") or {}
        new_tier   = price_meta.get("tier", state.get("tier", "pro"))

    state.update({
        "status":               sub.get("status", state.get("status")),
        "tier":                 new_tier,
        "current_period_end":   sub.get("current_period_end"),
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
        "last_checked":         _now(),
    })
    _save_state(state)
    logger.info(
        "🔄 Subscription updated | status=%s tier=%s cancel_at_end=%s",
        state["status"], new_tier, state["cancel_at_period_end"],
    )


async def _on_subscription_deleted(sub: dict) -> None:
    """
    customer.subscription.deleted
    Fired on cancellation or non-payment termination.
    """
    state = _load_state()
    state.update({
        "status":       "canceled",
        "last_checked": _now(),
    })
    _save_state(state)
    logger.warning(
        "❌ Subscription canceled | sub=%s customer=%s",
        sub.get("id"), sub.get("customer"),
    )
    await _notify(
        f"⚠️ <b>Subscription canceled</b>\n"
        f"Subscription: {sub.get('id')}\n"
        f"Customer: {sub.get('customer')}"
    )


async def _on_payment_succeeded(invoice: dict) -> None:
    """
    invoice.payment_succeeded
    Renewal confirmed — update period end and ensure status is active.
    """
    state = _load_state()
    period_end = invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")

    state.update({
        "status":             "active",
        "current_period_end": period_end or state.get("current_period_end"),
        "last_checked":       _now(),
    })
    _save_state(state)
    amount = invoice.get("amount_paid", 0) / 100
    logger.info("💰 Payment succeeded | amount=$%.2f sub=%s", amount, invoice.get("subscription"))


async def _on_payment_failed(invoice: dict) -> None:
    """
    invoice.payment_failed
    Alert operator — trading should continue until subscription is actually deleted.
    """
    state = _load_state()
    state.update({
        "status":       "past_due",
        "last_checked": _now(),
    })
    _save_state(state)

    attempt = invoice.get("attempt_count", 1)
    amount  = invoice.get("amount_due", 0) / 100
    logger.error(
        "🚨 Payment failed | attempt=%s amount=$%.2f sub=%s",
        attempt, amount, invoice.get("subscription"),
    )
    await _notify(
        f"🚨 <b>Payment failed (attempt {attempt})</b>\n"
        f"Amount: ${amount:.2f}\n"
        f"Subscription: {invoice.get('subscription')}\n"
        f"Please update payment method in the billing portal."
    )


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

_HANDLERS = {
    "checkout.session.completed":    _on_checkout_completed,
    "customer.subscription.updated": _on_subscription_updated,
    "customer.subscription.deleted": _on_subscription_deleted,
    "invoice.payment_succeeded":     _on_payment_succeeded,
    "invoice.payment_failed":        _on_payment_failed,
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now() -> int:
    import time
    return int(time.time())


async def _notify(message: str) -> None:
    """Best-effort Telegram notification for billing events."""
    try:
        from config import settings
        import aiohttp
        token   = settings.telegram_bot_token.get_secret_value()
        chat_id = settings.telegram_chat_id
        url     = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as sess:
            await sess.post(url, json={
                "chat_id":    chat_id,
                "text":       message,
                "parse_mode": "HTML",
            })
    except Exception as exc:
        logger.debug("Billing Telegram notification failed: %s", exc)

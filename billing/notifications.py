"""
Billing Notifications — Telegram alerts for Stripe billing events.

Extends the project's existing TelegramAlerts pattern with billing-specific
messages. Falls back to console logging if bot credentials are absent.
"""

import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class BillingNotifier:
    """
    Sends billing event notifications via Telegram.
    Mirrors the TelegramAlerts interface from fixed/telegram_alerts.py
    but is scoped to billing events only.
    """

    # Tier display names and emojis
    TIER_META = {
        "starter": ("🌱", "Starter"),
        "pro":     ("⚡", "Pro"),
        "elite":   ("🏆", "Elite"),
        "team":    ("🏢", "Team"),
        "unknown": ("❓", "Unknown"),
    }

    def __init__(self):
        self.token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "7296767446")  # Scoopy default
        self.enabled = bool(self.token and self.chat_id)
        if not self.enabled:
            logger.warning("[BillingNotifier] Telegram credentials not set — console fallback")

    # ── Core send ─────────────────────────────────────────────────────────

    def _send(self, text: str):
        """Send a Markdown message via Telegram. Falls back to print."""
        if not self.enabled:
            print(f"[BILLING NOTIFY] {text}")
            return
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=5,
            )
            if not resp.ok:
                logger.error(f"[BillingNotifier] Telegram error {resp.status_code}: {resp.text}")
        except Exception as exc:
            logger.error(f"[BillingNotifier] Send failed: {exc}")

    # ── Billing-specific alerts ───────────────────────────────────────────

    def new_subscription(
        self,
        email: Optional[str],
        tier: str,
        interval: str,
        customer_id: str,
    ):
        """Fired on checkout.session.completed — new paying customer."""
        emoji, name = self.TIER_META.get(tier.lower(), ("❓", tier))
        interval_label = "Annual 📅" if interval == "year" else "Monthly"
        self._send(
            f"💰 *New Subscriber\!*\n"
            f"Plan: {emoji} *{name}* ({interval_label})\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )
        logger.info(f"[BillingNotifier] New subscription — {customer_id} / {tier}")

    def subscription_upgraded(
        self,
        email: Optional[str],
        old_tier: str,
        new_tier: str,
        customer_id: str,
    ):
        """Fired when a customer moves to a higher-value tier."""
        _, old_name = self.TIER_META.get(old_tier.lower(), ("", old_tier))
        new_emoji, new_name = self.TIER_META.get(new_tier.lower(), ("❓", new_tier))
        self._send(
            f"⬆️ *Subscription Upgraded*\n"
            f"{old_name} → {new_emoji} *{new_name}*\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def subscription_downgraded(
        self,
        email: Optional[str],
        old_tier: str,
        new_tier: str,
        customer_id: str,
    ):
        """Fired when a customer moves to a lower-value tier."""
        _, old_name = self.TIER_META.get(old_tier.lower(), ("", old_tier))
        new_emoji, new_name = self.TIER_META.get(new_tier.lower(), ("❓", new_tier))
        self._send(
            f"⬇️ *Subscription Downgraded*\n"
            f"{old_name} → {new_emoji} *{new_name}*\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def subscription_canceled(
        self,
        email: Optional[str],
        tier: str,
        customer_id: str,
        at_period_end: bool = True,
    ):
        """Fired on customer.subscription.deleted."""
        emoji, name = self.TIER_META.get(tier.lower(), ("❓", tier))
        timing = "at period end" if at_period_end else "immediately"
        self._send(
            f"😢 *Subscription Canceled*\n"
            f"Plan: {emoji} {name} — canceled *{timing}*\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def payment_succeeded(
        self,
        email: Optional[str],
        amount_usd: float,
        tier: str,
        customer_id: str,
    ):
        """Fired on invoice.payment_succeeded (renewal)."""
        emoji, name = self.TIER_META.get(tier.lower(), ("❓", tier))
        self._send(
            f"✅ *Payment Received*\n"
            f"Plan: {emoji} {name}\n"
            f"Amount: `${amount_usd:.2f}`\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def payment_failed(
        self,
        email: Optional[str],
        amount_usd: float,
        tier: str,
        customer_id: str,
        next_attempt: Optional[datetime] = None,
    ):
        """Fired on invoice.payment_failed — HIGH PRIORITY."""
        emoji, name = self.TIER_META.get(tier.lower(), ("❓", tier))
        retry_str = (
            f"\nNext retry: `{next_attempt.strftime('%Y-%m-%d %H:%M UTC')}`"
            if next_attempt
            else ""
        )
        self._send(
            f"🚨 *Payment FAILED*\n"
            f"Plan: {emoji} {name}\n"
            f"Amount due: `${amount_usd:.2f}`\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`"
            f"{retry_str}\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def subscription_past_due(self, customer_id: str, email: Optional[str], tier: str):
        """Fired when subscription moves to past_due status."""
        emoji, name = self.TIER_META.get(tier.lower(), ("❓", tier))
        self._send(
            f"⚠️ *Subscription Past Due*\n"
            f"Plan: {emoji} {name}\n"
            f"Email: `{email or 'unknown'}`\n"
            f"Customer: `{customer_id}`\n"
            f"Action required: contact customer or Stripe will retry.\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def webhook_error(self, event_id: str, error: str):
        """Fired when a webhook event cannot be processed."""
        self._send(
            f"⚠️ *Billing Webhook Error*\n"
            f"Event: `{event_id}`\n"
            f"Error: `{error[:200]}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

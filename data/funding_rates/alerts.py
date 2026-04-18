"""
alerts.py — Funding Rate Alert Manager for CoinScopeAI.

Detects extreme funding rates and dispatches Telegram alerts.

Alert tiers:
  WARNING  — |rate| > 0.1%  — notable, worth watching
  CRITICAL — |rate| > 0.3%  — extreme, strong signal (market is very directional)

Cooldown:
  Once a symbol is alerted, it won't trigger again for ALERT_COOLDOWN_SECONDS.
  This prevents spam during sustained extreme rates.

Telegram message format:
  [FUNDING ⚠️ WARNING] BTCUSDT
  Rate: +0.15% (longs pay shorts)
  Mark: $43,250.00 | Next: in 2h 15m
"""

import asyncio
import logging
import time
from typing import Dict, Optional

import aiohttp

from .config import FundingRateConfig, FUNDING_RATE_WARNING, FUNDING_RATE_CRITICAL, ALERT_COOLDOWN_SECONDS
from .storage import FundingRateRecord

log = logging.getLogger(__name__)


class FundingRateAlertManager:
    """
    Stateful alert manager with per-symbol cooldown.

    Usage:
        alerts = FundingRateAlertManager(config)
        alerts.check(record)   # call from the collector's on_extreme callback
    """

    def __init__(self, config: FundingRateConfig):
        self.cfg = config
        self._cooldowns: Dict[str, float] = {}   # symbol → last_alerted epoch seconds
        self._alert_count = 0                    # total alerts sent (for monitoring)

        if not config.telegram_token:
            log.warning("[Alerts] No TELEGRAM_BOT_TOKEN set — alerts will only be logged.")

    # ── Public ────────────────────────────────────────────────────────────────

    def check(self, record: FundingRateRecord) -> None:
        """
        Evaluate a record and dispatch an alert if conditions are met.
        This is synchronous and safe to call from any context.
        Uses fire-and-forget for the Telegram HTTP request.
        """
        rate = record.funding_rate
        abs_rate = abs(rate)

        # Determine alert tier
        if abs_rate >= FUNDING_RATE_CRITICAL:
            tier = "CRITICAL"
        elif abs_rate >= FUNDING_RATE_WARNING:
            tier = "WARNING"
        else:
            return  # Below warning threshold — no alert

        # Respect cooldown
        if self._is_on_cooldown(record.symbol):
            return

        # Mark cooldown and dispatch
        self._cooldowns[record.symbol] = time.time()
        self._alert_count += 1

        message = _format_alert(tier, record)
        log.info("[Alert] %s — %s %.4f%%", tier, record.symbol, rate * 100)

        # Dispatch to Telegram (non-blocking, best-effort)
        if self.cfg.telegram_token and self.cfg.telegram_chat_id:
            asyncio.create_task(self._send_telegram(message))
        else:
            # Still log to stdout so the alert isn't completely invisible
            print(f"\n{'='*50}\n{message}\n{'='*50}")

    @property
    def alert_count(self) -> int:
        return self._alert_count

    def clear_cooldown(self, symbol: str) -> None:
        """Manually clear the cooldown for a symbol (useful for testing)."""
        self._cooldowns.pop(symbol.upper(), None)

    # ── Telegram ──────────────────────────────────────────────────────────────

    async def _send_telegram(self, message: str) -> None:
        """
        POST a message to the Telegram Bot API.
        Non-critical: errors are logged but do not raise.
        """
        url = f"https://api.telegram.org/bot{self.cfg.telegram_token}/sendMessage"
        payload = {
            "chat_id":    self.cfg.telegram_chat_id,
            "text":       message,
            "parse_mode": "HTML",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.warning("[Telegram] Send failed %d: %s", resp.status, body[:200])
                    else:
                        log.debug("[Telegram] Alert sent ✓")

        except asyncio.TimeoutError:
            log.warning("[Telegram] Send timed out (non-fatal)")
        except Exception as e:
            log.warning("[Telegram] Send error: %s (non-fatal)", e)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_on_cooldown(self, symbol: str) -> bool:
        last = self._cooldowns.get(symbol)
        if last is None:
            return False
        return (time.time() - last) < ALERT_COOLDOWN_SECONDS


# ── Message Formatting ────────────────────────────────────────────────────────

def _format_alert(tier: str, rec: FundingRateRecord) -> str:
    """Build the Telegram-ready alert message."""
    rate_pct = rec.funding_rate * 100
    abs_rate = abs(rate_pct)

    # Direction and emoji
    if rec.funding_rate > 0:
        direction = "longs pay shorts 🐂→🐻"
        rate_str  = f"+{rate_pct:.4f}%"
    else:
        direction = "shorts pay longs 🐻→🐂"
        rate_str  = f"{rate_pct:.4f}%"

    # Urgency emoji
    if tier == "CRITICAL":
        prefix = "🚨 <b>[FUNDING CRITICAL]</b>"
    else:
        prefix = "⚠️ <b>[FUNDING WARNING]</b>"

    # Time until next funding
    now_ms = int(time.time() * 1000)
    mins_left = max(0, (rec.next_funding_time - now_ms) // 60000)
    if mins_left >= 60:
        time_str = f"{mins_left // 60}h {mins_left % 60}m"
    else:
        time_str = f"{mins_left}m"

    return (
        f"{prefix} <code>{rec.symbol}</code>\n"
        f"Rate: <b>{rate_str}</b> ({direction})\n"
        f"Mark: ${rec.mark_price:,.2f} | Index: ${rec.index_price:,.2f}\n"
        f"Next funding: in {time_str}\n"
        f"Annual equiv: {abs_rate * 3 * 365:.1f}%"
    )


# ── Diagnostic Helper ─────────────────────────────────────────────────────────

def format_funding_table(records, top_n: int = 15) -> str:
    """
    Return a human-readable table of the top/bottom funding rate symbols.
    Useful for periodic digest messages or debugging.
    """
    if not records:
        return "No funding rate data available."

    sorted_records = sorted(records, key=lambda r: r.funding_rate, reverse=True)

    lines = [
        "📊 <b>Funding Rate Snapshot</b>",
        f"Tracking {len(records)} symbols | {time.strftime('%H:%M UTC')}",
        "",
        "<b>Top Positive (longs pay):</b>",
    ]

    for rec in sorted_records[:top_n]:
        if rec.funding_rate <= 0:
            break
        rate_pct = rec.funding_rate * 100
        lines.append(f"  {rec.symbol:<14} +{rate_pct:.4f}%")

    lines.append("")
    lines.append("<b>Top Negative (shorts pay):</b>")
    for rec in reversed(sorted_records[-top_n:]):
        if rec.funding_rate >= 0:
            break
        rate_pct = rec.funding_rate * 100
        lines.append(f"  {rec.symbol:<14}  {rate_pct:.4f}%")

    return "\n".join(lines)

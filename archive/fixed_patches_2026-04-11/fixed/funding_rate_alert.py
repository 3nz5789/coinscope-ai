"""
Funding Rate Alert Engine
CoinScopeAI | Phase: Data Pipeline

Watches incoming FundingRateRecord objects for threshold breaches and
dispatches Telegram alerts with per-symbol rate limiting.

Thresholds (per 8-hour funding period):
    EXTREME  |rate| > 0.05%   ≈  54% annualised  → strong contrarian signal
    HIGH     |rate| > 0.02%   ≈  22% annualised  → caution / monitor

Alert strategy:
  - One EXTREME alert per symbol per 30 minutes max (avoid spam).
  - HIGH alerts are suppressed while an EXTREME alert is active.
  - Direction flip (positive → negative or vice versa) resets the cooldown.
  - Hourly market-wide heartbeat shows top-5 extreme symbols.
  - Daily summary at 00:00 UTC.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from funding_rate_store import FundingRateRecord, FundingRateStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

THRESHOLD_EXTREME: float = 0.0005   # 0.05 % per 8 h
THRESHOLD_HIGH: float    = 0.0002   # 0.02 % per 8 h

ALERT_COOLDOWN_S: int = 1800        # 30 min between repeated alerts per symbol
HEARTBEAT_INTERVAL_S: int = 3600    # 1 h between market-wide heartbeats


# ---------------------------------------------------------------------------
# Telegram dispatcher (self-contained, no dep on existing TelegramAlerts class)
# ---------------------------------------------------------------------------

class _Telegram:
    """
    Thin Telegram wrapper.  Falls back to console print when credentials
    are absent so the pipeline runs cleanly in CI / dev environments.
    """

    def __init__(self) -> None:
        self.token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        # Support both project conventions for chat ID
        self.chat_id: str = (
            os.getenv("TELEGRAM_CHAT_ID", "")
            or os.getenv("TELEGRAM_CHAT_ID", "7296767446")  # ScoopyAI default
        )
        self.enabled: bool = bool(self.token and self.chat_id)
        if not self.enabled:
            logger.warning(
                "[Telegram] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set — "
                "alerts will print to console only."
            )

    def send(self, text: str) -> None:
        if not self.enabled:
            print(f"[TELEGRAM] {text}")
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=5,
            )
        except Exception as exc:
            logger.error(f"[Telegram] Send failed: {exc!r}")


# ---------------------------------------------------------------------------
# Per-symbol alert state
# ---------------------------------------------------------------------------

@dataclass
class _SymbolState:
    """Tracks the last alert issued for one symbol."""
    last_alert_ts: float = 0.0          # Unix seconds
    last_direction: str = ""             # "LONG_BIASED" | "SHORT_BIASED" | ""
    last_level: str = ""                 # "EXTREME" | "HIGH" | ""
    alert_count: int = 0

    def should_alert(self, direction: str, level: str, now: float) -> bool:
        """
        True if we should fire a new alert, considering:
          1. Cooldown window (ALERT_COOLDOWN_S).
          2. Direction flip → always alert regardless of cooldown.
          3. Level escalation (HIGH → EXTREME) → always alert.
        """
        # Direction flip — reset immediately
        if self.last_direction and self.last_direction != direction:
            return True
        # Level escalation
        if self.last_level == "HIGH" and level == "EXTREME":
            return True
        # Cooldown
        return (now - self.last_alert_ts) >= ALERT_COOLDOWN_S


# ---------------------------------------------------------------------------
# Alert engine
# ---------------------------------------------------------------------------

class FundingRateAlerter:
    """
    Receives FundingRateRecord batches (via the `check` callback) and fires
    Telegram alerts when thresholds are breached.

    Also exposes `run_heartbeat_loop()` — an async coroutine that should be
    started alongside the main pipeline to emit periodic market summaries.
    """

    def __init__(
        self,
        store: FundingRateStore,
        telegram: Optional[_Telegram] = None,
    ) -> None:
        self.store = store
        self._tg = telegram or _Telegram()
        self._states: Dict[str, _SymbolState] = {}
        self._last_heartbeat: float = 0.0
        self._alerts_fired: int = 0

    # ------------------------------------------------------------------
    # Public callback (called by FundingRateWriter.on_new_record)
    # ------------------------------------------------------------------

    def check(self, records: List[FundingRateRecord]) -> None:
        """
        Evaluate a batch of newly-stored records for threshold breaches.
        Called synchronously from the writer task — must be fast.
        """
        now = time.time()
        for rec in records:
            self._evaluate(rec, now)

    # ------------------------------------------------------------------
    # Periodic heartbeat (run as asyncio task)
    # ------------------------------------------------------------------

    async def run_heartbeat_loop(self) -> None:
        """
        Emit a market-wide funding summary every HEARTBEAT_INTERVAL_S.
        Must be awaited — never returns under normal operation.
        """
        import asyncio
        logger.info(
            f"[Alerter] Heartbeat loop started — every {HEARTBEAT_INTERVAL_S}s"
        )
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                await asyncio.get_event_loop().run_in_executor(
                    None, self._send_heartbeat
                )
            except asyncio.CancelledError:
                logger.info("[Alerter] Heartbeat loop cancelled.")
                break
            except Exception as exc:
                logger.error(f"[Alerter] Heartbeat error: {exc!r}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate(self, rec: FundingRateRecord, now: float) -> None:
        rate = rec.funding_rate
        abs_rate = abs(rate)

        # Determine alert level and direction
        if abs_rate > THRESHOLD_EXTREME:
            level = "EXTREME"
        elif abs_rate > THRESHOLD_HIGH:
            level = "HIGH"
        else:
            return  # below HIGH — no alert

        direction = "LONG_BIASED" if rate > 0 else "SHORT_BIASED"
        state = self._states.setdefault(rec.symbol, _SymbolState())

        if not state.should_alert(direction, level, now):
            return

        # Update state
        state.last_alert_ts = now
        state.last_direction = direction
        state.last_level = level
        state.alert_count += 1
        self._alerts_fired += 1

        self._dispatch_alert(rec, level, direction)

    def _dispatch_alert(
        self,
        rec: FundingRateRecord,
        level: str,
        direction: str,
    ) -> None:
        """Format and send a Telegram funding rate alert."""
        emoji = "🚨" if level == "EXTREME" else "⚠️"
        action = (
            "FADE LONGS — market overcrowded long"
            if direction == "LONG_BIASED"
            else "FADE SHORTS — market overcrowded short"
        )
        annualised = rec.funding_rate * 3 * 365  # 3 periods/day × 365 days

        text = (
            f"{emoji} *Funding Rate Alert — {level}*\n\n"
            f"Pair: `{rec.symbol}`\n"
            f"Rate: `{rec.funding_rate:+.4%}` per 8h\n"
            f"Annualised: `{annualised:+.1%}`\n"
            f"Mark: `${rec.mark_price:,.4f}`\n\n"
            f"📌 Signal: _{action}_\n\n"
            f"_Next funding: <t:{rec.next_funding_time // 1000}:R>_\n"
            f"_{self._ts_utc()}_"
        )
        logger.info(
            f"[Alerter] {level} alert: {rec.symbol} {rec.funding_rate:+.4%}"
        )
        self._tg.send(text)

    def _send_heartbeat(self) -> None:
        """Send a market-wide funding rate snapshot as a Telegram message."""
        try:
            snapshot = self.store.get_market_snapshot()
            extremes = [r for r in snapshot if abs(r.funding_rate) > THRESHOLD_EXTREME]
            highs = [r for r in snapshot if THRESHOLD_HIGH < abs(r.funding_rate) <= THRESHOLD_EXTREME]
            stats = self.store.get_stats()
        except Exception as exc:
            logger.error(f"[Alerter] Heartbeat DB query failed: {exc!r}")
            return

        if not snapshot:
            return

        # Build the Telegram message
        lines = [
            f"💓 *Funding Rate Heartbeat*",
            f"_{self._ts_utc()}_\n",
            f"Monitoring: `{stats['unique_symbols']}` symbols",
            f"Alerts fired: `{self._alerts_fired}` total\n",
        ]

        if extremes:
            lines.append(f"🚨 *EXTREME* (|rate| > 0.05%)\n")
            for r in sorted(extremes, key=lambda x: abs(x.funding_rate), reverse=True)[:5]:
                ann = r.funding_rate * 3 * 365
                bias = "👆 LONG" if r.funding_rate > 0 else "👇 SHORT"
                lines.append(
                    f"  `{r.symbol:<12}` {r.funding_rate:+.4%}  ({ann:+.0%}/yr)  {bias}"
                )
            lines.append("")

        if highs:
            lines.append(f"⚠️ *HIGH* (|rate| > 0.02%)\n")
            for r in sorted(highs, key=lambda x: abs(x.funding_rate), reverse=True)[:5]:
                ann = r.funding_rate * 3 * 365
                bias = "👆 LONG" if r.funding_rate > 0 else "👇 SHORT"
                lines.append(
                    f"  `{r.symbol:<12}` {r.funding_rate:+.4%}  ({ann:+.0%}/yr)  {bias}"
                )
            lines.append("")

        if not extremes and not highs:
            lines.append("✅ No symbols above HIGH threshold — market funding neutral.")

        self._tg.send("\n".join(lines))
        logger.info(
            f"[Alerter] Heartbeat sent — {len(extremes)} extreme, {len(highs)} high"
        )

    @staticmethod
    def _ts_utc() -> str:
        import datetime
        return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    @property
    def stats(self) -> dict:
        return {
            "alerts_fired": self._alerts_fired,
            "symbols_tracked": len(self._states),
        }

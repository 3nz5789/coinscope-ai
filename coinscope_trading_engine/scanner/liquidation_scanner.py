"""
liquidation_scanner.py — Liquidation Cascade Tracker
======================================================
Monitors forced liquidation orders from Binance to detect cascade events
that often precede sharp reversals or continuations.

Logic
-----
* Polls GET /fapi/v1/allForceOrders for the last LOOKBACK_MINUTES window
* Aggregates total notional liquidated by side (LONG liq = SELL orders,
  SHORT liq = BUY orders)
* Fires a hit when total notional >= threshold and the cascade is one-sided

Direction heuristic:
  Predominantly SELL liquidations (longs being liquidated) → bearish cascade
    → price may bounce  → signal LONG (counter-trend reversal opportunity)
  Predominantly BUY  liquidations (shorts being liquidated) → bullish cascade
    → price may drop    → signal SHORT (counter-trend reversal opportunity)

Settings (from .env / hardcoded defaults)
------------------------------------------
  LIQUIDATION_NOTIONAL_THRESHOLD_USD — min USD notional to trigger (default 500_000)
  LIQUIDATION_LOOKBACK_MINUTES       — rolling window              (default 15)
  LIQUIDATION_DOMINANCE_RATIO        — one-side dominance required (default 0.70)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import settings
from data.binance_rest import BinanceRESTClient
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer
from scanner.base_scanner import BaseScanner, ScannerHit, ScannerResult, SignalDirection, HitStrength
from utils.helpers import human_number, safe_divide, now_ms
from utils.logger import get_logger

logger = get_logger(__name__)

# Thresholds (can be overridden in subclass / constructor)
DEFAULT_NOTIONAL_THRESHOLD = 500_000    # USD
DEFAULT_LOOKBACK_MINUTES   = 15
DEFAULT_DOMINANCE_RATIO    = 0.70       # 70% one-sided to trigger


class LiquidationScanner(BaseScanner):
    """
    Detects liquidation cascade events and signals counter-trend opportunities.

    Large one-sided liquidations often mark local extremes — the cascade
    exhausts weak-handed positions, creating a potential reversal.
    """

    def __init__(
        self,
        cache: CacheManager,
        rest: BinanceRESTClient,
        notional_threshold: float = DEFAULT_NOTIONAL_THRESHOLD,
        lookback_minutes: int     = DEFAULT_LOOKBACK_MINUTES,
        dominance_ratio: float    = DEFAULT_DOMINANCE_RATIO,
    ) -> None:
        super().__init__(cache, rest, name="LiquidationScanner")
        self._normalizer         = DataNormalizer()
        self._notional_threshold = notional_threshold
        self._lookback_minutes   = lookback_minutes
        self._dominance_ratio    = dominance_ratio

    async def scan(self, symbol: str) -> ScannerResult:
        t0   = time.monotonic()
        hits: list[ScannerHit] = []

        try:
            liq_orders = await self._fetch_liquidations(symbol)
            if not liq_orders:
                return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

            # Separate by side (SELL = long liquidations, BUY = short liquidations)
            sell_notional = sum(o.notional for o in liq_orders if o.side == "SELL")
            buy_notional  = sum(o.notional for o in liq_orders if o.side == "BUY")
            total         = sell_notional + buy_notional

            if total < self._notional_threshold:
                return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

            sell_ratio = safe_divide(sell_notional, total)
            buy_ratio  = safe_divide(buy_notional,  total)

            # Long liquidation cascade → potential reversal LONG signal
            if sell_ratio >= self._dominance_ratio:
                strength, score = self._classify(total, sell_ratio)
                hits.append(self._make_hit(
                    symbol    = symbol,
                    direction = SignalDirection.LONG,
                    strength  = strength,
                    score     = score,
                    reason    = (
                        f"Long liquidation cascade: {human_number(sell_notional)} "
                        f"({sell_ratio:.0%} of {human_number(total)} total liq)"
                    ),
                    metadata  = {
                        "sell_notional": round(sell_notional, 2),
                        "buy_notional":  round(buy_notional, 2),
                        "total_notional": round(total, 2),
                        "sell_ratio":    round(sell_ratio, 3),
                        "order_count":   len(liq_orders),
                        "lookback_min":  self._lookback_minutes,
                    },
                ))

            # Short liquidation cascade → potential reversal SHORT signal
            elif buy_ratio >= self._dominance_ratio:
                strength, score = self._classify(total, buy_ratio)
                hits.append(self._make_hit(
                    symbol    = symbol,
                    direction = SignalDirection.SHORT,
                    strength  = strength,
                    score     = score,
                    reason    = (
                        f"Short liquidation cascade: {human_number(buy_notional)} "
                        f"({buy_ratio:.0%} of {human_number(total)} total liq)"
                    ),
                    metadata  = {
                        "sell_notional": round(sell_notional, 2),
                        "buy_notional":  round(buy_notional, 2),
                        "total_notional": round(total, 2),
                        "buy_ratio":     round(buy_ratio, 3),
                        "order_count":   len(liq_orders),
                        "lookback_min":  self._lookback_minutes,
                    },
                ))

        except Exception as exc:
            logger.error("%s error for %s: %s", self.name, symbol, exc)
            return ScannerResult(scanner=self.name, symbol=symbol, error=str(exc))

        return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _fetch_liquidations(self, symbol: str) -> list:
        """Fetch recent liquidations, using cache to avoid repeated API calls."""
        cache_key = f"liquidations:{symbol}:{self._lookback_minutes}m"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            # Re-normalise from plain dicts
            return [_dict_to_liq(d) for d in cached]

        end_ms   = now_ms()
        start_ms = end_ms - self._lookback_minutes * 60 * 1000
        raw      = await self.rest.get_liquidation_orders(
            symbol=symbol, limit=200,
            start_time=start_ms, end_time=end_ms,
        )
        orders = [
            o for r in raw
            if (o := self._normalizer.liquidation_to_schema(r)) is not None
        ]

        # Cache for 60 s (liquidations are relatively infrequent)
        await self.cache.set(cache_key, [_liq_to_dict(o) for o in orders], ttl=60)
        return orders

    def _classify(self, total_notional: float, dominance: float) -> tuple[HitStrength, float]:
        """Classify the cascade severity into (HitStrength, score)."""
        base_score = min(total_notional / self._notional_threshold * 15, 45.0)
        dominance_bonus = (dominance - self._dominance_ratio) * 20

        if total_notional >= self._notional_threshold * 10:
            return HitStrength.STRONG, min(base_score + dominance_bonus, 60.0)
        if total_notional >= self._notional_threshold * 3:
            return HitStrength.MEDIUM, min(base_score + dominance_bonus, 40.0)
        return HitStrength.WEAK, min(base_score + dominance_bonus, 25.0)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _liq_to_dict(o) -> dict:
    return {
        "side": o.side, "qty": o.qty, "price": o.price,
        "avg_price": o.avg_price, "status": o.status,
        "time": o.time.isoformat(),
    }


def _dict_to_liq(d: dict):
    from datetime import datetime
    from data.data_normalizer import LiquidationOrder
    return LiquidationOrder(
        symbol="", side=d["side"], order_type="LIMIT",
        time_in_force="IOC", qty=d["qty"], price=d["price"],
        avg_price=d["avg_price"], status=d["status"],
        time=datetime.fromisoformat(d["time"]),
    )

"""
funding_rate_scanner.py — Funding Rate Anomaly Detection
==========================================================
Monitors perpetual futures funding rates for extremes and rapid shifts
that often precede mean-reversion moves.

Logic
-----
* Fetches current funding rate via GET /fapi/v1/premiumIndex
* Compares against historical baseline (last N funding periods)
* Triggers on:
    1. Absolute extreme  — rate exceeds EXTREME_THRESHOLD (e.g. ±0.1%)
    2. Relative extreme  — rate is N× the rolling average
    3. Rapid reversal    — rate changed direction sharply vs prior period

Direction heuristic (contrarian — funding predicts over-extension):
  Very positive funding (longs pay shorts) → market over-leveraged long
    → signal SHORT (crowded long trade likely to unwind)
  Very negative funding (shorts pay longs) → market over-leveraged short
    → signal LONG  (short squeeze potential)

Settings (from .env)
--------------------
  FUNDING_RATE_THRESHOLD_PCT — absolute threshold in %  (default 0.1)
"""

from __future__ import annotations

import time
from typing import Optional

from config import settings
from data.binance_rest import BinanceRESTClient
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer
from scanner.base_scanner import BaseScanner, ScannerHit, ScannerResult, SignalDirection, HitStrength
from utils.helpers import safe_divide, pct_change, now_ms
from utils.logger import get_logger

logger = get_logger(__name__)

# Thresholds
EXTREME_MULTIPLIER = 3.0     # rate is 3× rolling avg → extreme
REVERSAL_THRESHOLD = 0.05    # rate changed by 0.05% in one period → rapid reversal
HISTORY_PERIODS    = 8       # number of historical periods to compare


class FundingRateScanner(BaseScanner):
    """
    Detects extreme and rapidly shifting funding rates as contrarian signals.

    High positive funding → crowded longs → SHORT opportunity.
    High negative funding → crowded shorts → LONG opportunity.
    """

    def __init__(
        self,
        cache: CacheManager,
        rest: BinanceRESTClient,
        threshold_pct: Optional[float] = None,
    ) -> None:
        super().__init__(cache, rest, name="FundingRateScanner")
        self._normalizer   = DataNormalizer()
        self._threshold    = (threshold_pct or settings.funding_rate_threshold_pct) / 100.0

    async def scan(self, symbol: str) -> ScannerResult:
        t0   = time.monotonic()
        hits: list[ScannerHit] = []

        try:
            mark    = await self._fetch_mark_price(symbol)
            history = await self._fetch_funding_history(symbol)

            current_rate = mark.last_funding_rate

            # ── 1. Absolute extreme ──────────────────────────────────────
            if abs(current_rate) >= self._threshold:
                direction = SignalDirection.SHORT if current_rate > 0 else SignalDirection.LONG
                strength, score = self._classify_absolute(current_rate)
                hits.append(self._make_hit(
                    symbol    = symbol,
                    direction = direction,
                    strength  = strength,
                    score     = score,
                    reason    = (
                        f"Extreme funding rate: {current_rate * 100:.4f}% "
                        f"({'positive → crowded long' if current_rate > 0 else 'negative → crowded short'})"
                    ),
                    metadata  = {
                        "funding_rate":   current_rate,
                        "threshold":      self._threshold,
                        "mark_price":     mark.mark_price,
                        "next_funding":   mark.next_funding_time.isoformat(),
                    },
                ))

            # ── 2. Relative extreme (vs rolling average) ─────────────────
            if len(history) >= 3:
                avg_abs = sum(abs(h.funding_rate) for h in history[:HISTORY_PERIODS]) / min(len(history), HISTORY_PERIODS)
                if avg_abs > 0:
                    relative = safe_divide(abs(current_rate), avg_abs)
                    if relative >= EXTREME_MULTIPLIER and abs(current_rate) >= self._threshold * 0.5:
                        direction = SignalDirection.SHORT if current_rate > 0 else SignalDirection.LONG
                        hits.append(self._make_hit(
                            symbol    = symbol,
                            direction = direction,
                            strength  = HitStrength.MEDIUM,
                            score     = min(relative * 5, 30.0),
                            reason    = (
                                f"Funding {relative:.1f}× above rolling avg "
                                f"(current={current_rate*100:.4f}%, avg={avg_abs*100:.4f}%)"
                            ),
                            metadata  = {
                                "relative_multiple": round(relative, 2),
                                "rolling_avg":       avg_abs,
                                "current_rate":      current_rate,
                            },
                        ))

            # ── 3. Rapid reversal ────────────────────────────────────────
            if history:
                prior_rate = history[0].funding_rate
                delta      = current_rate - prior_rate
                if abs(delta) >= REVERSAL_THRESHOLD / 100.0:
                    direction = SignalDirection.LONG if delta < 0 else SignalDirection.SHORT
                    hits.append(self._make_hit(
                        symbol    = symbol,
                        direction = direction,
                        strength  = HitStrength.WEAK,
                        score     = min(abs(delta) * 5000, 20.0),
                        reason    = (
                            f"Funding rate rapid shift: "
                            f"{prior_rate*100:.4f}% → {current_rate*100:.4f}% "
                            f"(Δ={delta*100:+.4f}%)"
                        ),
                        metadata  = {
                            "prior_rate":   prior_rate,
                            "current_rate": current_rate,
                            "delta":        delta,
                        },
                    ))

        except Exception as exc:
            logger.error("%s error for %s: %s", self.name, symbol, exc)
            return ScannerResult(scanner=self.name, symbol=symbol, error=str(exc))

        return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _fetch_mark_price(self, symbol: str):
        cache_key = f"mark_price:{symbol}"
        cached = await self.cache.get(cache_key)
        if cached:
            return _dict_to_mark(cached)
        raw  = await self.rest.get_mark_price(symbol)
        mark = self._normalizer.mark_price_to_schema(raw)
        await self.cache.set(cache_key, _mark_to_dict(mark), ttl=10)
        return mark

    async def _fetch_funding_history(self, symbol: str) -> list:
        cache_key = f"funding_history:{symbol}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [_dict_to_fr(d) for d in cached]
        raw     = await self.rest.get_funding_rate_history(symbol, limit=HISTORY_PERIODS + 1)
        history = self._normalizer.funding_rate_history_to_schema(raw)
        history.sort(key=lambda h: h.funding_time, reverse=True)
        await self.cache.set(cache_key, [_fr_to_dict(h) for h in history], ttl=60)
        return history

    def _classify_absolute(self, rate: float) -> tuple[HitStrength, float]:
        abs_rate  = abs(rate)
        threshold = self._threshold
        if abs_rate >= threshold * 3:
            return HitStrength.STRONG, min(50.0 + (abs_rate - threshold * 3) * 1000, 70.0)
        if abs_rate >= threshold * 1.5:
            return HitStrength.MEDIUM, 25.0 + (abs_rate - threshold * 1.5) * 500
        return HitStrength.WEAK, 15.0 + (abs_rate - threshold) * 300


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _mark_to_dict(m) -> dict:
    return {
        "symbol": m.symbol, "mark_price": m.mark_price,
        "index_price": m.index_price, "last_funding_rate": m.last_funding_rate,
        "next_funding_time": m.next_funding_time.isoformat(),
        "interest_rate": m.interest_rate, "time": m.time.isoformat(),
        "estimated_settle_price": m.estimated_settle_price,
    }

def _dict_to_mark(d: dict):
    from datetime import datetime
    from data.data_normalizer import MarkPrice
    return MarkPrice(
        symbol=d["symbol"], mark_price=d["mark_price"],
        index_price=d["index_price"], estimated_settle_price=d["estimated_settle_price"],
        last_funding_rate=d["last_funding_rate"],
        next_funding_time=datetime.fromisoformat(d["next_funding_time"]),
        interest_rate=d["interest_rate"], time=datetime.fromisoformat(d["time"]),
    )

def _fr_to_dict(h) -> dict:
    return {"symbol": h.symbol, "funding_rate": h.funding_rate, "funding_time": h.funding_time.isoformat()}

def _dict_to_fr(d: dict):
    from datetime import datetime
    from data.data_normalizer import FundingRate
    return FundingRate(symbol=d["symbol"], funding_rate=d["funding_rate"],
                       funding_time=datetime.fromisoformat(d["funding_time"]))

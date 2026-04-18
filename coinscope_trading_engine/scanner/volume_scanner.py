"""
volume_scanner.py — Volume Spike Detection
============================================
Detects abnormal volume spikes by comparing the current candle's volume
against a rolling baseline average over the last N candles.

Logic
-----
  spike_ratio = current_volume / rolling_avg_volume

  spike_ratio >= STRONG_MULTIPLIER  → STRONG hit
  spike_ratio >= MEDIUM_MULTIPLIER  → MEDIUM hit
  spike_ratio >= WEAK_MULTIPLIER    → WEAK hit

Direction is inferred from candle colour:
  bullish candle (close >= open) + spike → LONG
  bearish candle (close <  open) + spike → SHORT

Settings (from .env)
--------------------
  VOLUME_SPIKE_MULTIPLIER   — minimum ratio to trigger (default 3.0)
  VOLUME_BASELINE_PERIOD    — rolling window in candles  (default 20)
  DEFAULT_TIMEFRAME         — candle interval             (default "5m")
"""

from __future__ import annotations

import time
from typing import Optional

from config import settings
from data.binance_rest import BinanceRESTClient
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer, Candle
from scanner.base_scanner import BaseScanner, ScannerHit, ScannerResult, SignalDirection, HitStrength
from utils.helpers import pct_change, safe_divide
from utils.logger import get_logger

logger = get_logger(__name__)

# Multiplier thresholds relative to the rolling baseline
WEAK_MULTIPLIER   = 2.0
MEDIUM_MULTIPLIER = 3.0
STRONG_MULTIPLIER = 5.0


class VolumeScanner(BaseScanner):
    """
    Scans for volume spikes that indicate unusual market activity.

    A spike is detected when the current candle's volume exceeds the
    rolling average volume by a configurable multiplier.  Direction
    is inferred from the candle body (bullish / bearish).
    """

    def __init__(
        self,
        cache: CacheManager,
        rest: BinanceRESTClient,
        timeframe: Optional[str] = None,
        baseline_period: Optional[int] = None,
        spike_multiplier: Optional[float] = None,
    ) -> None:
        super().__init__(cache, rest, name="VolumeScanner")
        self._normalizer      = DataNormalizer()
        self._timeframe       = timeframe       or settings.default_timeframe.value
        self._baseline_period = baseline_period or settings.volume_baseline_period
        self._spike_multiplier = spike_multiplier or settings.volume_spike_multiplier

    async def scan(self, symbol: str) -> ScannerResult:
        t0   = time.monotonic()
        hits: list[ScannerHit] = []

        try:
            candles = await self._fetch_candles(symbol)
            if len(candles) < self._baseline_period + 1:
                logger.debug("%s: not enough candles for %s (%d)", self.name, symbol, len(candles))
                return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

            current  = candles[-1]
            baseline = candles[-(self._baseline_period + 1):-1]
            avg_vol  = sum(c.volume for c in baseline) / len(baseline)
            ratio    = safe_divide(current.volume, avg_vol, default=0.0)

            if ratio >= self._spike_multiplier:
                direction = SignalDirection.LONG if current.is_bullish else SignalDirection.SHORT
                strength, score = self._classify(ratio)

                hits.append(self._make_hit(
                    symbol    = symbol,
                    direction = direction,
                    strength  = strength,
                    score     = score,
                    reason    = (
                        f"Volume spike {ratio:.1f}× baseline "
                        f"({'bullish' if current.is_bullish else 'bearish'} candle, "
                        f"vol={current.volume:,.0f})"
                    ),
                    metadata  = {
                        "ratio":        round(ratio, 2),
                        "current_vol":  current.volume,
                        "avg_vol":      round(avg_vol, 2),
                        "candle_close": current.close,
                        "body_pct":     round(current.body_pct, 1),
                        "timeframe":    self._timeframe,
                    },
                ))

            # Secondary: taker buy/sell imbalance on a spike candle
            if hits:
                taker_ratio = safe_divide(
                    current.taker_buy_base_volume,
                    current.volume,
                    default=0.5,
                )
                if taker_ratio > 0.70:
                    hits.append(self._make_hit(
                        symbol    = symbol,
                        direction = SignalDirection.LONG,
                        strength  = HitStrength.WEAK,
                        score     = 10.0,
                        reason    = f"Aggressive buy side on spike: taker_buy={taker_ratio:.0%}",
                        metadata  = {"taker_buy_ratio": round(taker_ratio, 3)},
                    ))
                elif taker_ratio < 0.30:
                    hits.append(self._make_hit(
                        symbol    = symbol,
                        direction = SignalDirection.SHORT,
                        strength  = HitStrength.WEAK,
                        score     = 10.0,
                        reason    = f"Aggressive sell side on spike: taker_buy={taker_ratio:.0%}",
                        metadata  = {"taker_buy_ratio": round(taker_ratio, 3)},
                    ))

        except Exception as exc:
            logger.error("%s error for %s: %s", self.name, symbol, exc)
            return ScannerResult(scanner=self.name, symbol=symbol, error=str(exc))

        return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _fetch_candles(self, symbol: str) -> list[Candle]:
        """Fetch candles from cache first, falling back to REST API."""
        cache_key = f"candles:{symbol}:{self._timeframe}"
        cached = await self.cache.get(cache_key)
        if cached:
            return [_dict_to_candle(c, symbol, self._timeframe) for c in cached]

        limit  = self._baseline_period + 5
        raw    = await self.rest.get_klines(symbol, self._timeframe, limit=limit)
        candles = self._normalizer.klines_to_candles(symbol, self._timeframe, raw)

        # Cache for half the candle duration
        from utils.helpers import timeframe_to_seconds
        ttl = max(5, timeframe_to_seconds(self._timeframe) // 2)
        await self.cache.set(cache_key, [_candle_to_dict(c) for c in candles], ttl=ttl)
        return candles

    def _classify(self, ratio: float) -> tuple[HitStrength, float]:
        """Map spike ratio to (HitStrength, score) pair."""
        if ratio >= STRONG_MULTIPLIER:
            return HitStrength.STRONG, min(40.0 + (ratio - STRONG_MULTIPLIER) * 4, 60.0)
        if ratio >= MEDIUM_MULTIPLIER:
            return HitStrength.MEDIUM, 25.0 + (ratio - MEDIUM_MULTIPLIER) * 5
        return HitStrength.WEAK, 10.0 + (ratio - WEAK_MULTIPLIER) * 7.5


# ---------------------------------------------------------------------------
# Serialisation helpers (candle ↔ plain dict for Redis)
# ---------------------------------------------------------------------------

def _candle_to_dict(c: Candle) -> dict:
    return {
        "open_time":  c.open_time.isoformat(),
        "close_time": c.close_time.isoformat(),
        "open": c.open, "high": c.high, "low": c.low, "close": c.close,
        "volume": c.volume, "quote_volume": c.quote_volume,
        "trades": c.trades,
        "taker_buy_base_volume":  c.taker_buy_base_volume,
        "taker_buy_quote_volume": c.taker_buy_quote_volume,
    }


def _dict_to_candle(d: dict, symbol: str, interval: str) -> Candle:
    from datetime import datetime, timezone
    from data.data_normalizer import Candle as C
    return C(
        symbol=symbol, interval=interval,
        open_time  = datetime.fromisoformat(d["open_time"]),
        close_time = datetime.fromisoformat(d["close_time"]),
        open=d["open"], high=d["high"], low=d["low"], close=d["close"],
        volume=d["volume"], quote_volume=d["quote_volume"],
        trades=d["trades"],
        taker_buy_base_volume  = d["taker_buy_base_volume"],
        taker_buy_quote_volume = d["taker_buy_quote_volume"],
    )

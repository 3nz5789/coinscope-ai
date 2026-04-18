"""
pattern_scanner.py — Candlestick & Chart Pattern Recognition
=============================================================
Detects high-probability candlestick patterns and simple chart structures
from OHLCV candle data.

Patterns detected
-----------------
Single-candle:
  Hammer / Hanging Man, Inverted Hammer / Shooting Star,
  Doji, Marubozu (strong trend candle)

Two-candle:
  Bullish / Bearish Engulfing, Tweezer Top / Bottom

Three-candle:
  Morning Star / Evening Star, Three White Soldiers / Three Black Crows

Chart structure:
  Higher Highs + Higher Lows (uptrend), Lower Highs + Lower Lows (downtrend)
  Pin Bar (long wick rejection)
"""

from __future__ import annotations

import time
from typing import Optional

from config import settings
from data.binance_rest import BinanceRESTClient
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer, Candle
from scanner.base_scanner import BaseScanner, ScannerHit, ScannerResult, SignalDirection, HitStrength
from utils.helpers import safe_divide
from utils.logger import get_logger

logger = get_logger(__name__)

# Pattern thresholds
DOJI_BODY_MAX_PCT    = 5.0    # body is <= 5% of range → doji
MARUBOZU_BODY_MIN_PCT = 90.0  # body is >= 90% of range → marubozu
HAMMER_BODY_MAX_PCT  = 35.0   # small body
HAMMER_WICK_MIN_RATIO = 2.0   # lower wick >= 2× the body
PIN_BAR_WICK_MIN_PCT  = 60.0  # wick >= 60% of full range


class PatternScanner(BaseScanner):
    """
    Detects candlestick and basic chart patterns as trading signals.
    """

    def __init__(
        self,
        cache: CacheManager,
        rest: BinanceRESTClient,
        timeframe: Optional[str] = None,
        candles_needed: int = 10,
    ) -> None:
        super().__init__(cache, rest, name="PatternScanner")
        self._normalizer    = DataNormalizer()
        self._timeframe     = timeframe or settings.default_timeframe.value
        self._candles_needed = candles_needed

    async def scan(self, symbol: str) -> ScannerResult:
        t0   = time.monotonic()
        hits: list[ScannerHit] = []

        try:
            candles = await self._fetch_candles(symbol)
            if len(candles) < self._candles_needed:
                return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

            c  = candles[-1]   # current (most recent closed)
            p1 = candles[-2]   # one candle back
            p2 = candles[-3]   # two candles back

            hits += self._check_single(symbol, c)
            hits += self._check_two(symbol, c, p1)
            hits += self._check_three(symbol, c, p1, p2)
            hits += self._check_structure(symbol, candles[-6:])

        except Exception as exc:
            logger.error("%s error for %s: %s", self.name, symbol, exc)
            return ScannerResult(scanner=self.name, symbol=symbol, error=str(exc))

        return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

    # ── Single-candle patterns ───────────────────────────────────────────

    def _check_single(self, symbol: str, c: Candle) -> list[ScannerHit]:
        hits = []
        rng  = c.high - c.low

        # Hammer / Hanging Man
        body = abs(c.close - c.open)
        lower_wick = min(c.open, c.close) - c.low
        upper_wick = c.high - max(c.open, c.close)
        if (body <= rng * HAMMER_BODY_MAX_PCT / 100 and
                lower_wick >= body * HAMMER_WICK_MIN_RATIO and
                upper_wick <= body * 0.5 and rng > 0):
            direction = SignalDirection.LONG if c.is_bullish else SignalDirection.SHORT
            label     = "Hammer (bullish reversal)" if c.is_bullish else "Hanging Man (bearish)"
            hits.append(self._make_hit(symbol, direction, HitStrength.MEDIUM, 20.0, label,
                                       {"body_pct": round(c.body_pct, 1), "lower_wick_pct": round(c.lower_wick_pct, 1)}))

        # Shooting Star / Inverted Hammer
        if (body <= rng * HAMMER_BODY_MAX_PCT / 100 and
                upper_wick >= body * HAMMER_WICK_MIN_RATIO and
                lower_wick <= body * 0.5 and rng > 0):
            direction = SignalDirection.SHORT if c.is_bearish else SignalDirection.LONG
            label     = "Shooting Star (bearish)" if c.is_bearish else "Inverted Hammer (bullish)"
            hits.append(self._make_hit(symbol, direction, HitStrength.MEDIUM, 18.0, label,
                                       {"body_pct": round(c.body_pct, 1), "upper_wick_pct": round(c.upper_wick_pct, 1)}))

        # Doji
        if c.body_pct <= DOJI_BODY_MAX_PCT and rng > 0:
            hits.append(self._make_hit(symbol, SignalDirection.NEUTRAL, HitStrength.WEAK, 10.0,
                                       f"Doji (indecision, body={c.body_pct:.1f}%)"))

        # Marubozu (strong momentum candle)
        if c.body_pct >= MARUBOZU_BODY_MIN_PCT and rng > 0:
            direction = SignalDirection.LONG if c.is_bullish else SignalDirection.SHORT
            label     = f"{'Bullish' if c.is_bullish else 'Bearish'} Marubozu (strong momentum)"
            hits.append(self._make_hit(symbol, direction, HitStrength.STRONG, 30.0, label,
                                       {"body_pct": round(c.body_pct, 1)}))

        # Pin Bar (long wick rejection)
        max_wick = max(lower_wick, upper_wick)
        if max_wick >= rng * PIN_BAR_WICK_MIN_PCT / 100 and rng > 0:
            direction = SignalDirection.LONG if lower_wick > upper_wick else SignalDirection.SHORT
            hits.append(self._make_hit(symbol, direction, HitStrength.MEDIUM, 22.0,
                                       f"Pin Bar ({'bullish' if direction == SignalDirection.LONG else 'bearish'} rejection)",
                                       {"wick_pct": round(max_wick / rng * 100, 1)}))
        return hits

    # ── Two-candle patterns ──────────────────────────────────────────────

    def _check_two(self, symbol: str, c: Candle, p: Candle) -> list[ScannerHit]:
        hits = []

        # Bullish Engulfing
        if (p.is_bearish and c.is_bullish and
                c.open < p.close and c.close > p.open):
            hits.append(self._make_hit(symbol, SignalDirection.LONG, HitStrength.STRONG, 35.0,
                                       "Bullish Engulfing"))

        # Bearish Engulfing
        if (p.is_bullish and c.is_bearish and
                c.open > p.close and c.close < p.open):
            hits.append(self._make_hit(symbol, SignalDirection.SHORT, HitStrength.STRONG, 35.0,
                                       "Bearish Engulfing"))

        # Tweezer Bottom
        if (p.is_bearish and c.is_bullish and
                abs(p.low - c.low) / max(p.low, 0.001) < 0.001):
            hits.append(self._make_hit(symbol, SignalDirection.LONG, HitStrength.MEDIUM, 20.0,
                                       "Tweezer Bottom (support test)"))

        # Tweezer Top
        if (p.is_bullish and c.is_bearish and
                abs(p.high - c.high) / max(p.high, 0.001) < 0.001):
            hits.append(self._make_hit(symbol, SignalDirection.SHORT, HitStrength.MEDIUM, 20.0,
                                       "Tweezer Top (resistance test)"))
        return hits

    # ── Three-candle patterns ────────────────────────────────────────────

    def _check_three(self, symbol: str, c: Candle, p1: Candle, p2: Candle) -> list[ScannerHit]:
        hits = []

        # Morning Star
        if (p2.is_bearish and p1.body_pct <= 30 and c.is_bullish and
                c.close > (p2.open + p2.close) / 2):
            hits.append(self._make_hit(symbol, SignalDirection.LONG, HitStrength.STRONG, 40.0,
                                       "Morning Star (bullish reversal)"))

        # Evening Star
        if (p2.is_bullish and p1.body_pct <= 30 and c.is_bearish and
                c.close < (p2.open + p2.close) / 2):
            hits.append(self._make_hit(symbol, SignalDirection.SHORT, HitStrength.STRONG, 40.0,
                                       "Evening Star (bearish reversal)"))

        # Three White Soldiers
        if (all(x.is_bullish for x in [p2, p1, c]) and
                p1.close > p2.close and c.close > p1.close and
                all(x.body_pct >= 60 for x in [p2, p1, c])):
            hits.append(self._make_hit(symbol, SignalDirection.LONG, HitStrength.STRONG, 45.0,
                                       "Three White Soldiers (strong uptrend)"))

        # Three Black Crows
        if (all(x.is_bearish for x in [p2, p1, c]) and
                p1.close < p2.close and c.close < p1.close and
                all(x.body_pct >= 60 for x in [p2, p1, c])):
            hits.append(self._make_hit(symbol, SignalDirection.SHORT, HitStrength.STRONG, 45.0,
                                       "Three Black Crows (strong downtrend)"))
        return hits

    # ── Chart structure ──────────────────────────────────────────────────

    def _check_structure(self, symbol: str, candles: list[Candle]) -> list[ScannerHit]:
        if len(candles) < 4:
            return []
        hits = []

        highs = [c.high  for c in candles]
        lows  = [c.low   for c in candles]

        # Higher highs + higher lows → uptrend structure
        hh = all(highs[i] > highs[i - 1] for i in range(1, len(highs)))
        hl = all(lows[i]  > lows[i - 1]  for i in range(1, len(lows)))
        if hh and hl:
            hits.append(self._make_hit(symbol, SignalDirection.LONG, HitStrength.MEDIUM, 20.0,
                                       f"HH+HL structure ({len(candles)}-candle uptrend)",
                                       {"candles": len(candles)}))

        # Lower highs + lower lows → downtrend structure
        lh = all(highs[i] < highs[i - 1] for i in range(1, len(highs)))
        ll = all(lows[i]  < lows[i - 1]  for i in range(1, len(lows)))
        if lh and ll:
            hits.append(self._make_hit(symbol, SignalDirection.SHORT, HitStrength.MEDIUM, 20.0,
                                       f"LH+LL structure ({len(candles)}-candle downtrend)",
                                       {"candles": len(candles)}))
        return hits

    # ── Data fetching ────────────────────────────────────────────────────

    async def _fetch_candles(self, symbol: str) -> list[Candle]:
        from utils.helpers import timeframe_to_seconds
        cache_key = f"candles:{symbol}:{self._timeframe}"
        cached = await self.cache.get(cache_key)
        if cached:
            from scanner.volume_scanner import _dict_to_candle
            return [_dict_to_candle(c, symbol, self._timeframe) for c in cached]
        raw     = await self.rest.get_klines(symbol, self._timeframe, limit=self._candles_needed + 2)
        candles = self._normalizer.klines_to_candles(symbol, self._timeframe, raw)
        ttl     = max(5, timeframe_to_seconds(self._timeframe) // 2)
        from scanner.volume_scanner import _candle_to_dict
        await self.cache.set(cache_key, [_candle_to_dict(c) for c in candles], ttl=ttl)
        return candles

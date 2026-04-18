"""
indicator_engine.py — Technical Indicator Calculations
========================================================
Computes all technical indicators used by the confluence scorer
from a list of Candle objects.

Indicators implemented (pure numpy — no external TA library required)
----------------------------------------------------------------------
Trend:
  EMA(period)          Exponential Moving Average
  SMA(period)          Simple Moving Average
  MACD(12,26,9)        MACD line, signal line, histogram
  ADX(14)              Average Directional Index (trend strength)

Momentum:
  RSI(14)              Relative Strength Index
  Stochastic(14,3,3)   %K and %D lines
  ROC(period)          Rate of Change

Volatility:
  ATR(14)              Average True Range
  Bollinger(20,2)      Upper / middle / lower bands + %B + bandwidth

Volume:
  OBV                  On-Balance Volume
  VWAP                 Volume-Weighted Average Price (session)
  CMF(20)              Chaikin Money Flow

Output schema
-------------
All indicators are returned as an ``Indicators`` dataclass so callers
get dot-notation access and clear field names.

Usage
-----
    from signals.indicator_engine import IndicatorEngine

    engine = IndicatorEngine()
    ind    = engine.compute(candles)

    print(ind.rsi)          # → 67.3
    print(ind.macd_hist)    # → 0.0023
    print(ind.atr)          # → 142.5
    print(ind.bb_pct_b)     # → 0.82  (near upper band)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from data.data_normalizer import Candle
from utils.helpers import safe_divide
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class Indicators:
    """All computed indicator values for the most recent closed candle."""

    symbol:   str = ""
    interval: str = ""

    # ── Trend ────────────────────────────────────────────────────────────
    ema_9:   Optional[float] = None
    ema_21:  Optional[float] = None
    ema_50:  Optional[float] = None
    ema_200: Optional[float] = None
    sma_20:  Optional[float] = None
    sma_50:  Optional[float] = None

    macd:         Optional[float] = None   # MACD line
    macd_signal:  Optional[float] = None   # signal line
    macd_hist:    Optional[float] = None   # histogram (macd - signal)

    adx:    Optional[float] = None         # 0-100; >25 = trending
    di_pos: Optional[float] = None         # +DI
    di_neg: Optional[float] = None         # -DI

    # ── Momentum ─────────────────────────────────────────────────────────
    rsi:       Optional[float] = None      # 0-100
    stoch_k:   Optional[float] = None      # %K 0-100
    stoch_d:   Optional[float] = None      # %D 0-100 (smoothed %K)
    roc:       Optional[float] = None      # Rate of change %

    # ── Volatility ───────────────────────────────────────────────────────
    atr:        Optional[float] = None     # absolute ATR
    atr_pct:    Optional[float] = None     # ATR as % of close price

    bb_upper:   Optional[float] = None
    bb_middle:  Optional[float] = None
    bb_lower:   Optional[float] = None
    bb_pct_b:   Optional[float] = None     # 0=lower band, 1=upper band
    bb_width:   Optional[float] = None     # bandwidth as % of middle band

    # ── Volume ───────────────────────────────────────────────────────────
    obv:        Optional[float] = None     # running On-Balance Volume
    vwap:       Optional[float] = None     # session VWAP
    cmf:        Optional[float] = None     # -1 to +1; >0 = buying pressure

    # ── Derived signals ──────────────────────────────────────────────────
    trend_direction: str = "NEUTRAL"    # "BULLISH" | "BEARISH" | "NEUTRAL"
    momentum_bias:   str = "NEUTRAL"    # "BULLISH" | "BEARISH" | "NEUTRAL"
    volatility_state: str = "NORMAL"    # "LOW" | "NORMAL" | "HIGH" | "EXTREME"

    @property
    def is_trending(self) -> bool:
        return self.adx is not None and self.adx >= 25

    @property
    def rsi_overbought(self) -> bool:
        return self.rsi is not None and self.rsi >= 70

    @property
    def rsi_oversold(self) -> bool:
        return self.rsi is not None and self.rsi <= 30

    @property
    def above_bb_upper(self) -> bool:
        return self.bb_pct_b is not None and self.bb_pct_b >= 1.0

    @property
    def below_bb_lower(self) -> bool:
        return self.bb_pct_b is not None and self.bb_pct_b <= 0.0

    @property
    def macd_bullish_cross(self) -> bool:
        return (self.macd is not None and self.macd_signal is not None
                and self.macd > self.macd_signal and self.macd_hist is not None
                and self.macd_hist > 0)

    @property
    def macd_bearish_cross(self) -> bool:
        return (self.macd is not None and self.macd_signal is not None
                and self.macd < self.macd_signal and self.macd_hist is not None
                and self.macd_hist < 0)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class IndicatorEngine:
    """
    Computes technical indicators from a list of Candle objects.

    All calculations use pure numpy — no external TA library needed.
    Requires at least 50 candles for reliable EMA-50 and ADX values;
    200 candles for EMA-200.
    """

    def compute(self, candles: list[Candle]) -> Indicators:
        """
        Compute all indicators and return an Indicators object.

        Parameters
        ----------
        candles : list[Candle]
            Chronologically ordered closed candles (oldest first).
            Minimum 26 candles for MACD; 50+ recommended.

        Returns
        -------
        Indicators : All computed values for the most recent candle.
        """
        if not candles:
            logger.warning("IndicatorEngine.compute called with empty candle list")
            return Indicators()

        ind = Indicators(
            symbol   = candles[-1].symbol,
            interval = candles[-1].interval,
        )

        closes  = np.array([c.close  for c in candles], dtype=float)
        highs   = np.array([c.high   for c in candles], dtype=float)
        lows    = np.array([c.low    for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)
        opens   = np.array([c.open   for c in candles], dtype=float)
        n       = len(closes)

        # ── EMAs ─────────────────────────────────────────────────────────
        if n >= 9:   ind.ema_9   = float(_ema(closes, 9)[-1])
        if n >= 21:  ind.ema_21  = float(_ema(closes, 21)[-1])
        if n >= 50:  ind.ema_50  = float(_ema(closes, 50)[-1])
        if n >= 200: ind.ema_200 = float(_ema(closes, 200)[-1])

        # ── SMAs ─────────────────────────────────────────────────────────
        if n >= 20:  ind.sma_20  = float(np.mean(closes[-20:]))
        if n >= 50:  ind.sma_50  = float(np.mean(closes[-50:]))

        # ── MACD (12, 26, 9) ─────────────────────────────────────────────
        if n >= 26:
            ema12 = _ema(closes, 12)
            ema26 = _ema(closes, 26)
            macd_line = ema12 - ema26
            if len(macd_line) >= 9:
                signal    = _ema(macd_line, 9)
                ind.macd        = float(macd_line[-1])
                ind.macd_signal = float(signal[-1])
                ind.macd_hist   = float(macd_line[-1] - signal[-1])

        # ── RSI (14) ─────────────────────────────────────────────────────
        if n >= 15:
            ind.rsi = float(_rsi(closes, 14))

        # ── Stochastic (14, 3, 3) ────────────────────────────────────────
        if n >= 17:
            k, d = _stochastic(highs, lows, closes, 14, 3, 3)
            ind.stoch_k = float(k)
            ind.stoch_d = float(d)

        # ── ATR (14) ─────────────────────────────────────────────────────
        if n >= 15:
            atr_val     = float(_atr(highs, lows, closes, 14))
            ind.atr     = atr_val
            ind.atr_pct = safe_divide(atr_val, closes[-1]) * 100

        # ── Bollinger Bands (20, 2) ───────────────────────────────────────
        if n >= 20:
            upper, mid, lower = _bollinger(closes, 20, 2.0)
            ind.bb_upper  = float(upper)
            ind.bb_middle = float(mid)
            ind.bb_lower  = float(lower)
            band_range    = upper - lower
            ind.bb_pct_b  = float(safe_divide(closes[-1] - lower, band_range, 0.5))
            ind.bb_width  = float(safe_divide(band_range, mid) * 100) if mid else None

        # ── ADX (14) ─────────────────────────────────────────────────────
        if n >= 28:
            adx_val, di_pos, di_neg = _adx(highs, lows, closes, 14)
            ind.adx    = float(adx_val)
            ind.di_pos = float(di_pos)
            ind.di_neg = float(di_neg)

        # ── ROC ──────────────────────────────────────────────────────────
        if n >= 14:
            ind.roc = float(safe_divide(closes[-1] - closes[-14], closes[-14]) * 100)

        # ── OBV ──────────────────────────────────────────────────────────
        if n >= 2:
            ind.obv = float(_obv(closes, volumes))

        # ── VWAP (session) ───────────────────────────────────────────────
        typical_prices = (highs + lows + closes) / 3
        ind.vwap = float(
            safe_divide(np.sum(typical_prices * volumes), np.sum(volumes))
        )

        # ── CMF (20) ─────────────────────────────────────────────────────
        if n >= 20:
            ind.cmf = float(_cmf(highs, lows, closes, volumes, 20))

        # ── Derived labels ────────────────────────────────────────────────
        ind.trend_direction  = self._trend_label(ind, closes[-1])
        ind.momentum_bias    = self._momentum_label(ind)
        ind.volatility_state = self._volatility_label(ind)

        return ind

    # ── Derived label helpers ─────────────────────────────────────────────

    @staticmethod
    def _trend_label(ind: Indicators, price: float) -> str:
        signals = 0
        if ind.ema_9  and ind.ema_21  and ind.ema_9  > ind.ema_21:  signals += 1
        if ind.ema_21 and ind.ema_50  and ind.ema_21 > ind.ema_50:  signals += 1
        if ind.ema_50 and ind.ema_200 and ind.ema_50 > ind.ema_200: signals += 1
        if ind.macd_hist and ind.macd_hist > 0: signals += 1
        if ind.di_pos and ind.di_neg and ind.di_pos > ind.di_neg:   signals += 1

        bearish = 0
        if ind.ema_9  and ind.ema_21  and ind.ema_9  < ind.ema_21:  bearish += 1
        if ind.ema_21 and ind.ema_50  and ind.ema_21 < ind.ema_50:  bearish += 1
        if ind.ema_50 and ind.ema_200 and ind.ema_50 < ind.ema_200: bearish += 1
        if ind.macd_hist and ind.macd_hist < 0: bearish += 1
        if ind.di_pos and ind.di_neg and ind.di_pos < ind.di_neg:   bearish += 1

        if signals >= 3: return "BULLISH"
        if bearish >= 3: return "BEARISH"
        return "NEUTRAL"

    @staticmethod
    def _momentum_label(ind: Indicators) -> str:
        bull = sum([
            ind.rsi is not None and ind.rsi > 55,
            ind.stoch_k is not None and ind.stoch_k > 60,
            ind.roc is not None and ind.roc > 0,
            ind.cmf is not None and ind.cmf > 0.1,
        ])
        bear = sum([
            ind.rsi is not None and ind.rsi < 45,
            ind.stoch_k is not None and ind.stoch_k < 40,
            ind.roc is not None and ind.roc < 0,
            ind.cmf is not None and ind.cmf < -0.1,
        ])
        if bull >= 3: return "BULLISH"
        if bear >= 3: return "BEARISH"
        return "NEUTRAL"

    @staticmethod
    def _volatility_label(ind: Indicators) -> str:
        if ind.atr_pct is None:
            return "NORMAL"
        if ind.atr_pct < 0.5:  return "LOW"
        if ind.atr_pct < 1.5:  return "NORMAL"
        if ind.atr_pct < 3.0:  return "HIGH"
        return "EXTREME"


# ---------------------------------------------------------------------------
# Pure numpy indicator implementations
# ---------------------------------------------------------------------------

def _ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    k   = 2.0 / (period + 1)
    out = np.zeros(len(data))
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = data[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(closes: np.ndarray, period: int = 14) -> float:
    """Wilder-smoothed RSI."""
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _stochastic(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    k_period: int = 14, k_smooth: int = 3, d_smooth: int = 3
) -> tuple[float, float]:
    """Stochastic Oscillator (%K, %D)."""
    raw_k = np.zeros(len(closes))
    for i in range(k_period - 1, len(closes)):
        h = np.max(highs[i - k_period + 1: i + 1])
        l = np.min(lows [i - k_period + 1: i + 1])
        raw_k[i] = safe_divide(closes[i] - l, h - l, 0.5) * 100
    smooth_k = _ema(raw_k[k_period - 1:], k_smooth)
    smooth_d = _ema(smooth_k, d_smooth)
    return float(smooth_k[-1]), float(smooth_d[-1])


def _atr(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    period: int = 14
) -> float:
    """Average True Range (Wilder smoothing)."""
    tr = np.zeros(len(closes))
    tr[0] = highs[0] - lows[0]
    for i in range(1, len(closes)):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1]),
        )
    atr = np.mean(tr[:period])
    for i in range(period, len(tr)):
        atr = (atr * (period - 1) + tr[i]) / period
    return float(atr)


def _bollinger(
    closes: np.ndarray, period: int = 20, std_dev: float = 2.0
) -> tuple[float, float, float]:
    """Bollinger Bands — returns (upper, middle, lower)."""
    window = closes[-period:]
    mid    = float(np.mean(window))
    std    = float(np.std(window, ddof=1))
    return mid + std_dev * std, mid, mid - std_dev * std


def _adx(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    period: int = 14
) -> tuple[float, float, float]:
    """Average Directional Index — returns (ADX, +DI, -DI)."""
    n     = len(closes)
    tr    = np.zeros(n)
    dm_p  = np.zeros(n)
    dm_n  = np.zeros(n)

    for i in range(1, n):
        tr[i]   = max(highs[i] - lows[i],
                      abs(highs[i] - closes[i - 1]),
                      abs(lows[i]  - closes[i - 1]))
        up   = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        dm_p[i] = up   if up > down and up > 0 else 0.0
        dm_n[i] = down if down > up and down > 0 else 0.0

    # Wilder smoothing
    def _wilder(arr: np.ndarray, p: int) -> np.ndarray:
        out = np.zeros(len(arr))
        out[p] = np.sum(arr[1: p + 1])
        for i in range(p + 1, len(arr)):
            out[i] = out[i - 1] - out[i - 1] / p + arr[i]
        return out

    atr_w  = _wilder(tr,   period)
    dmp_w  = _wilder(dm_p, period)
    dmn_w  = _wilder(dm_n, period)

    # Avoid divide-by-zero on early candles
    with np.errstate(divide="ignore", invalid="ignore"):
        di_p = np.where(atr_w != 0, dmp_w / atr_w * 100, 0.0)
        di_n = np.where(atr_w != 0, dmn_w / atr_w * 100, 0.0)
        dx   = np.where((di_p + di_n) != 0,
                        np.abs(di_p - di_n) / (di_p + di_n) * 100, 0.0)

    adx_arr = _wilder(dx, period)
    return float(adx_arr[-1]), float(di_p[-1]), float(di_n[-1])


def _obv(closes: np.ndarray, volumes: np.ndarray) -> float:
    """On-Balance Volume."""
    obv = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += volumes[i]
        elif closes[i] < closes[i - 1]:
            obv -= volumes[i]
    return obv


def _cmf(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
    volumes: np.ndarray, period: int = 20
) -> float:
    """Chaikin Money Flow (-1 to +1)."""
    hl_range = highs - lows
    with np.errstate(divide="ignore", invalid="ignore"):
        mfm = np.where(hl_range != 0,
                       ((closes - lows) - (highs - closes)) / hl_range, 0.0)
    mfv    = mfm * volumes
    window = slice(-period, None)
    return float(safe_divide(np.sum(mfv[window]), np.sum(volumes[window])))

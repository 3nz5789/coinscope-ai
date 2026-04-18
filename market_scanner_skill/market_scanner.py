"""
CoinScopeAI — Market Scanner Skill v2.0
========================================
What's new vs v1.0:
  - Standalone Mode: computes RSI, EMA, ATR, Volume, CVD via ccxt when engine is offline
  - Funding rate fetching (current 8h rate from Binance perpetuals)
  - Open interest change (1h Δ%) from Binance futures history
  - Multi-timeframe EMA confirmation (secondary TF alignment check)
  - Chop regime signals demoted in ranking (not filtered, just de-prioritised)
  - CLI: --standalone, --tf, --funding-rate <SYM>, --oi-change <SYM> flags

Usage (standalone):
    python market_scanner.py
    python market_scanner.py --pairs BTC/USDT,ETH/USDT --top 3 --filter LONG --tf 1h
    python market_scanner.py --standalone       # force standalone mode
    python market_scanner.py --funding-rate BTC/USDT
    python market_scanner.py --oi-change ETH/USDT
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ── Optional ccxt import (needed for standalone + supplementary data) ─────────
try:
    import ccxt
    _CCXT_OK = True
except ImportError:
    _CCXT_OK = False

# ── Config ────────────────────────────────────────────────────────────────────

ENGINE_BASE_URL = "http://localhost:8001"

DEFAULT_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "TAO/USDT",
]

# Maps primary timeframe → next-lower timeframe for MTF confirmation
TF_LOWER: dict[str, str] = {
    "1d": "4h",
    "4h": "1h",
    "1h": "15m",
    "15m": "5m",
    "5m":  "1m",
}

SCORE_LABELS = {
    (0.0, 4.9):  ("Weak",        "⚫"),
    (5.0, 5.9):  ("Moderate",    "🟡"),
    (6.0, 7.4):  ("Good",        "🟠"),
    (7.5, 8.9):  ("Strong",      "🟢"),
    (9.0, 12.0): ("Very Strong", "💎"),
}

REGIME_ICONS = {
    "bull":    "🟢 Bull",
    "bear":    "🔴 Bear",
    "chop":    "🟡 Chop",
    "unknown": "⚫ Unknown",
}

# ─────────────────────────────────────────────────────────────────────────────
# Vectorized Indicator Calculations
# ─────────────────────────────────────────────────────────────────────────────

def calc_rsi(close: np.ndarray, period: int = 14) -> float:
    """
    Wilder-smoothed RSI (the standard used by TradingView).
    Returns NaN when insufficient data is available.
    """
    n = len(close)
    if n < period + 1:
        return np.nan

    delta = np.diff(close)
    gain  = np.where(delta > 0, delta, 0.0)
    loss  = np.where(delta < 0, -delta, 0.0)

    # Seed with simple average, then apply Wilder smoothing
    avg_g = np.zeros(len(gain))
    avg_l = np.zeros(len(loss))
    avg_g[period - 1] = gain[:period].mean()
    avg_l[period - 1] = loss[:period].mean()

    for i in range(period, len(gain)):
        avg_g[i] = (avg_g[i - 1] * (period - 1) + gain[i]) / period
        avg_l[i] = (avg_l[i - 1] * (period - 1) + loss[i]) / period

    rs = avg_g[-1] / (avg_l[-1] + 1e-10)
    return float(100.0 - (100.0 / (1.0 + rs)))


def calc_ema(close: np.ndarray, period: int) -> np.ndarray:
    """
    Vectorized EMA. Alpha = 2 / (period + 1).
    Seeded on the first close value (no NaN padding).
    """
    alpha = 2.0 / (period + 1)
    ema = np.empty(len(close), dtype=float)
    ema[0] = close[0]
    for i in range(1, len(close)):
        ema[i] = alpha * close[i] + (1.0 - alpha) * ema[i - 1]
    return ema


def calc_atr(
    high: np.ndarray,
    low:  np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> float:
    """
    Wilder-smoothed Average True Range.
    Returns NaN when insufficient data is available.
    """
    n = len(close)
    if n < period + 1:
        return np.nan

    # True range = max(H-L, |H-Cprev|, |L-Cprev|)
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:]  - close[:-1]),
        ),
    )

    atr = np.zeros(len(tr))
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return float(atr[-1])


def calc_cvd_slope(
    open_:  np.ndarray,
    close:  np.ndarray,
    volume: np.ndarray,
    lookback: int = 10,
) -> float:
    """
    Approximate CVD slope over the last `lookback` bars using linear regression.

    CVD (Cumulative Volume Delta) approximation:
      - Bullish candle (close > open)  → full volume is buying pressure
      - Bearish candle (close < open)  → full volume is selling pressure
      - Doji (close == open)           → volume is neutral (zero delta)

    Positive slope → net buying pressure (supports LONG).
    Negative slope → net selling pressure (supports SHORT).
    """
    if len(close) < lookback:
        return 0.0

    o = open_[-lookback:]
    c = close[-lookback:]
    v = volume[-lookback:]

    delta_vol = np.where(c > o, v, np.where(c < o, -v, 0.0))
    cvd = np.cumsum(delta_vol).astype(float)

    x = np.arange(lookback, dtype=float)
    slope = float(np.polyfit(x, cvd, 1)[0])
    return slope


def calc_linear_slope(arr: np.ndarray, lookback: int = 5) -> float:
    """Slope of the linear regression of the last `lookback` values."""
    if len(arr) < lookback:
        return 0.0
    y = arr[-lookback:].astype(float)
    x = np.arange(lookback, dtype=float)
    return float(np.polyfit(x, y, 1)[0])


# ─────────────────────────────────────────────────────────────────────────────
# Sub-Score Functions (each returns 0, 1, or 2)
# ─────────────────────────────────────────────────────────────────────────────

def score_rsi(rsi: float, direction: str) -> float:
    """RSI momentum sub-score (0–2).
    Rewards RSI in the 'trend continuation' sweet spot — not overbought/oversold."""
    if np.isnan(rsi):
        return 0.0
    if direction == "LONG":
        if 55.0 <= rsi <= 65.0: return 2.0   # sweet spot: trending but not extended
        if 50.0 <= rsi < 55.0 or 65.0 < rsi <= 70.0: return 1.0
        return 0.0
    else:  # SHORT
        if 35.0 <= rsi <= 45.0: return 2.0
        if 30.0 <= rsi < 35.0 or 45.0 < rsi <= 50.0: return 1.0
        return 0.0


def score_ema(
    ema9: float,
    ema21: float,
    ema21_slope: float,
    direction: str,
) -> float:
    """EMA trend sub-score (0–2).
    Rewards both EMA9/21 crossover alignment AND EMA21 slope in same direction."""
    aligned   = (direction == "LONG"  and ema9 > ema21) \
             or (direction == "SHORT" and ema9 < ema21)
    slope_ok  = (direction == "LONG"  and ema21_slope > 0) \
             or (direction == "SHORT" and ema21_slope < 0)

    if aligned and slope_ok: return 2.0
    if aligned or slope_ok:  return 1.0
    return 0.0


def score_atr(atr_pct: float) -> float:
    """Volatility sub-score (0–2).
    Rewards moderate volatility — too low = no movement, too high = unmanageable risk."""
    if np.isnan(atr_pct):
        return 0.0
    if 0.5 <= atr_pct <= 2.0:  return 2.0   # ideal range
    if 0.3 <= atr_pct < 0.5 or 2.0 < atr_pct <= 3.5: return 1.0
    return 0.0                                # too quiet or too wild


def score_volume(vol_ratio: float) -> float:
    """Volume sub-score (0–2). Volume vs 20-bar MA."""
    if np.isnan(vol_ratio):
        return 0.0
    if vol_ratio >= 1.5: return 2.0
    if vol_ratio >= 1.2: return 1.0
    return 0.0


def score_cvd(cvd_slope: float, direction: str) -> float:
    """CVD directional pressure sub-score (0–2)."""
    if direction == "LONG":
        if cvd_slope > 0:  return 2.0
        if cvd_slope == 0: return 1.0
        return 0.0
    else:  # SHORT
        if cvd_slope < 0:  return 2.0
        if cvd_slope == 0: return 1.0
        return 0.0


def score_entry(
    close: float,
    ema21: float,
    atr:   float,
    direction: str,
) -> float:
    """Entry timing sub-score (0–2).
    Rewards price that has pulled back close to EMA21 (within 0.1–1.5 ATR).
    Penalises entries that are too extended from the moving average."""
    if atr <= 0 or np.isnan(atr):
        return 0.0

    dist_atr = (close - ema21) / atr  # signed: positive = above EMA21

    if direction == "LONG":
        if  0.1 <= dist_atr <= 1.5: return 2.0
        if  0.0 <= dist_atr <= 2.5: return 1.0
        return 0.0
    else:  # SHORT
        if -1.5 <= dist_atr <= -0.1: return 2.0
        if -2.5 <= dist_atr <= 0.0:  return 1.0
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Standalone Regime Detector (HMM-free approximation)
# ─────────────────────────────────────────────────────────────────────────────

def detect_regime_simple(rsi: float, ema21_slope: float) -> str:
    """
    Simplified regime proxy when the HMM model is unavailable.
    Uses RSI + EMA21 slope as a directional consensus.
    """
    if np.isnan(rsi):
        return "unknown"
    bull_bias = rsi > 52.0 and ema21_slope > 0
    bear_bias = rsi < 48.0 and ema21_slope < 0
    if bull_bias:  return "bull"
    if bear_bias:  return "bear"
    return "chop"


# ─────────────────────────────────────────────────────────────────────────────
# Standalone Pair Scanner (ccxt-based)
# ─────────────────────────────────────────────────────────────────────────────

def scan_pair_standalone(symbol: str, timeframe: str = "4h") -> Optional[dict]:
    """
    Compute indicators and derive a signal for a single pair without the engine.

    Fetches 120 OHLCV bars from Binance USDT-M futures via ccxt, computes six
    sub-scores (each 0–2), and returns a signal dict in engine-compatible format.

    Returns None if the pair cannot be fetched (network error, invalid symbol, etc.).
    """
    if not _CCXT_OK:
        print("[WARN] ccxt not installed — cannot run standalone mode.", file=sys.stderr)
        return None

    try:
        exchange = ccxt.binanceusdm({"enableRateLimit": True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=120)
        if len(ohlcv) < 30:
            return None

        df = pd.DataFrame(
            ohlcv, columns=["ts", "open", "high", "low", "close", "volume"]
        )
        o  = df["open"].values.astype(float)
        h  = df["high"].values.astype(float)
        lo = df["low"].values.astype(float)
        c  = df["close"].values.astype(float)
        v  = df["volume"].values.astype(float)

    except Exception as exc:
        print(f"[WARN] {symbol}: fetch failed — {exc}", file=sys.stderr)
        return None

    # ── Compute indicators ────────────────────────────────────────────────────
    rsi       = calc_rsi(c, 14)
    ema9_arr  = calc_ema(c, 9)
    ema21_arr = calc_ema(c, 21)
    atr       = calc_atr(h, lo, c, 14)

    ema9  = float(ema9_arr[-1])
    ema21 = float(ema21_arr[-1])
    close = float(c[-1])

    ema21_slope = calc_linear_slope(ema21_arr, 5)
    vol_20_avg  = float(v[-21:-1].mean()) if len(v) >= 21 else float(v.mean())
    vol_ratio   = float(v[-1] / (vol_20_avg + 1e-10))
    atr_pct     = (atr / close * 100.0) if close > 0 and not np.isnan(atr) else np.nan
    cvd_slope   = calc_cvd_slope(o, c, v, 10)

    # ── Determine dominant direction ──────────────────────────────────────────
    direction = "LONG" if ema9 > ema21 else "SHORT"

    # ── Score all six components ──────────────────────────────────────────────
    s_rsi   = score_rsi(rsi, direction)
    s_ema   = score_ema(ema9, ema21, ema21_slope, direction)
    s_atr   = score_atr(atr_pct)
    s_vol   = score_volume(vol_ratio)
    s_cvd   = score_cvd(cvd_slope, direction)
    s_entry = score_entry(close, ema21, atr, direction)

    total_score = s_rsi + s_ema + s_atr + s_vol + s_cvd + s_entry

    # Signal threshold mirrors the FixedScorer thresholds
    signal = direction if total_score >= 5.5 else "NEUTRAL"
    regime = detect_regime_simple(rsi, ema21_slope)

    return {
        "symbol":     symbol,
        "signal":     signal,
        "score":      round(total_score, 2),
        "timeframe":  timeframe,
        "rsi":        round(rsi, 1) if not np.isnan(rsi) else 0.0,
        "regime":     regime,
        "confidence": round(total_score / 12.0, 2),
        "_mode":      "standalone",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Supplementary Data Fetchers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_funding_rate(symbol: str) -> Optional[float]:
    """
    Fetch the current perpetual funding rate from Binance USDT-M futures.

    Returns the rate as a decimal (e.g. 0.0001 = 0.01%).
    Returns None on any error.

    Interpretation:
      >  0.05% → longs paying shorts → bearish crowding → aligns with SHORT
      < -0.05% → shorts paying longs → bullish crowding → aligns with LONG
      Extreme > 0.08% or < -0.08% → mean-reversion risk, flag in output
    """
    if not _CCXT_OK:
        return None
    try:
        exchange = ccxt.binanceusdm({"enableRateLimit": True})
        fr = exchange.fetch_funding_rate(symbol)
        return fr.get("fundingRate", None)
    except Exception:
        return None


def fetch_oi_change(symbol: str) -> Optional[float]:
    """
    Fetch open interest change over the past 1 hour from Binance futures.

    Fetches 2 data points at 1h resolution and computes percentage change.
    Returns the Δ% as a float (e.g. +3.2 = +3.2%, -1.5 = -1.5%).
    Returns None on any error.

    Interpretation:
      Positive Δ + matching signal direction → new positions entering → stronger setup
      Negative Δ + active signal           → positions closing     → weaker setup
    """
    if not _CCXT_OK:
        return None
    try:
        exchange = ccxt.binanceusdm({"enableRateLimit": True})
        history = exchange.fetch_open_interest_history(symbol, "1h", limit=2)
        if len(history) < 2:
            return None
        oi_old = float(history[-2].get("openInterestAmount", 0))
        oi_new = float(history[-1].get("openInterestAmount", 0))
        if oi_old == 0:
            return None
        return round((oi_new - oi_old) / oi_old * 100.0, 2)
    except Exception:
        return None


def check_mtf_confirmation(
    symbol:     str,
    signal:     str,
    primary_tf: str,
) -> str:
    """
    Check EMA9/21 alignment on the secondary (lower) timeframe.

    Returns:
      '✅'  EMA alignment confirms the signal on the lower TF
      '⚠️'  Lower TF is neutral / indeterminate
      '❌'  Lower TF shows the opposite EMA alignment (conflicting setup)
      'N/A' Could not determine (no ccxt, unknown TF, fetch error)
    """
    secondary_tf = TF_LOWER.get(primary_tf)
    if not secondary_tf or not _CCXT_OK:
        return "N/A"

    try:
        exchange = ccxt.binanceusdm({"enableRateLimit": True})
        ohlcv = exchange.fetch_ohlcv(symbol, secondary_tf, limit=30)
        if len(ohlcv) < 25:
            return "N/A"

        c = np.array([bar[4] for bar in ohlcv], dtype=float)
        ema9  = float(calc_ema(c, 9)[-1])
        ema21 = float(calc_ema(c, 21)[-1])

        sec_bullish = ema9 > ema21
        sec_bearish = ema9 < ema21

        if signal == "LONG":
            if sec_bullish: return "✅"
            if sec_bearish: return "❌"
            return "⚠️"
        elif signal == "SHORT":
            if sec_bearish: return "✅"
            if sec_bullish: return "❌"
            return "⚠️"
        return "N/A"
    except Exception:
        return "N/A"


# ─────────────────────────────────────────────────────────────────────────────
# Engine Health Check
# ─────────────────────────────────────────────────────────────────────────────

def check_engine_health() -> bool:
    """Ping the engine health endpoint. Returns True if online."""
    try:
        r = requests.get(f"{ENGINE_BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Core Scan Logic
# ─────────────────────────────────────────────────────────────────────────────

def run_scan(
    pairs:            Optional[list] = None,
    top_n:            int   = 5,
    min_score:        float = 5.5,
    signal_filter:    str   = "ALL",
    primary_tf:       str   = "4h",
    force_standalone: bool  = False,
) -> dict:
    """
    Run a full market scan.

    Automatically selects Engine Mode (localhost:8001) or Standalone Mode (ccxt).
    Enriches every actionable signal with funding rate, OI change, and MTF confirmation.

    Returns a result dict with keys:
        status        'ok' | 'no_signals' | 'error'
        results       Filtered, ranked signal list
        active_count  Number of active signals before top_n filter
        total_scanned Total pairs attempted
        timestamp     UTC timestamp string
        mode          'engine' | 'standalone'
    """
    pairs = pairs or DEFAULT_PAIRS

    # ── Determine mode ────────────────────────────────────────────────────────
    engine_ok = (not force_standalone) and check_engine_health()
    mode      = "engine" if engine_ok else "standalone"

    # ── Fetch raw signals ─────────────────────────────────────────────────────
    if engine_ok:
        try:
            resp = requests.get(
                f"{ENGINE_BASE_URL}/scan",
                params={"pairs": ",".join(pairs), "timeframe": primary_tf},
                timeout=30,
            )
            resp.raise_for_status()
            data       = resp.json()
            signals    = data.get("signals", [])
            active_cnt = data.get("active_count", 0)
            total_sc   = data.get("total_scanned", len(pairs))
        except requests.exceptions.Timeout:
            return _err_result(
                "Engine scan timed out (>30s) — retry with --standalone if issue persists."
            )
        except requests.exceptions.RequestException as exc:
            return _err_result(f"Engine API error: {exc}")
    else:
        # Standalone: scan each pair independently via ccxt
        signals    = []
        failed     = []
        for sym in pairs:
            result = scan_pair_standalone(sym, primary_tf)
            if result:
                signals.append(result)
            else:
                failed.append(sym)
        active_cnt = sum(1 for s in signals if s.get("signal") in ("LONG", "SHORT"))
        total_sc   = len(pairs)

    # ── Enrich actionable signals with supplementary data ─────────────────────
    # This runs in both modes — funding rate and OI come from Binance regardless.
    for sig in signals:
        sym    = sig.get("symbol", "")
        signal = sig.get("signal", "NEUTRAL")

        if signal in ("LONG", "SHORT"):
            sig["funding_rate"] = fetch_funding_rate(sym)
            sig["oi_change"]    = fetch_oi_change(sym)
            sig["mtf_confirm"]  = check_mtf_confirmation(sym, signal, primary_tf)
        else:
            sig["funding_rate"] = None
            sig["oi_change"]    = None
            sig["mtf_confirm"]  = "N/A"

    # ── Filter ────────────────────────────────────────────────────────────────
    filtered = [s for s in signals if s.get("signal") in ("LONG", "SHORT")]

    if signal_filter.upper() in ("LONG", "SHORT"):
        filtered = [s for s in filtered if s.get("signal") == signal_filter.upper()]

    filtered = [s for s in filtered if s.get("score", 0) >= min_score]

    # ── Rank: demote chop regime by 1.0 for ordering ─────────────────────────
    def _rank_score(s: dict) -> float:
        adj = float(s.get("score", 0))
        if s.get("regime") == "chop":
            adj -= 1.0
        return adj

    filtered.sort(key=_rank_score, reverse=True)
    top_results = filtered[:top_n]

    # ── Build return dict ─────────────────────────────────────────────────────
    if not top_results:
        return {
            "status":        "no_signals",
            "message":       (
                f"No setups found above score {min_score}. "
                "Market may be in consolidation — try lowering the threshold "
                "or checking back in 15 min."
            ),
            "results":       [],
            "active_count":  active_cnt,
            "total_scanned": total_sc,
            "timestamp":     _utc_now(),
            "mode":          mode,
        }

    return {
        "status":        "ok",
        "results":       top_results,
        "active_count":  active_cnt,
        "total_scanned": total_sc,
        "timestamp":     _utc_now(),
        "mode":          mode,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _err_result(msg: str) -> dict:
    return {"status": "error", "message": msg, "results": []}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def score_label(score: float) -> str:
    for (lo, hi), (label, icon) in SCORE_LABELS.items():
        if lo <= score <= hi:
            return f"{icon} {label}"
    return "⚫ Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Output Formatter
# ─────────────────────────────────────────────────────────────────────────────

def format_output(scan_result: dict) -> str:
    """Format scan result as a trader-readable string."""
    status = scan_result.get("status")

    if status == "error":
        return f"❌  Error\n{scan_result.get('message', 'Unknown error')}"

    mode = scan_result.get("mode", "?").upper()
    ts   = scan_result.get("timestamp", "N/A")

    if status == "no_signals":
        return (
            f"📡  MARKET SCAN — {ts}  [{mode}]\n"
            f"Scanned: {scan_result.get('total_scanned', 0)} pairs\n\n"
            f"ℹ️  {scan_result.get('message', 'No signals found.')}"
        )

    results = scan_result["results"]
    total   = scan_result["total_scanned"]
    active  = scan_result["active_count"]

    SEP_W = 92
    lines = [
        f"📡  MARKET SCAN — {ts}  [{mode}]",
        f"Scanned: {total} pairs  |  Active Signals: {active}",
        "━" * SEP_W,
        (
            f"{'RANK':<5} {'PAIR':<12} {'SIG':<6} {'SCORE':<7} {'TF':<5} "
            f"{'RSI':<7} {'REGIME':<14} {'STRENGTH':<15} {'MTF':<5} {'FUND%':<10} {'OI Δ%'}"
        ),
        "━" * SEP_W,
    ]

    for i, sig in enumerate(results, 1):
        symbol   = sig.get("symbol",   "???")
        signal   = sig.get("signal",   "N/A")
        score    = float(sig.get("score",    0.0))
        tf       = sig.get("timeframe","4h")
        rsi      = float(sig.get("rsi",      0.0))
        regime   = REGIME_ICONS.get(sig.get("regime", "unknown"), "⚫ Unknown")
        strength = score_label(score)
        mtf      = sig.get("mtf_confirm", "N/A")

        # Funding rate column
        fr = sig.get("funding_rate")
        if fr is not None:
            fr_str = f"{fr * 100:+.3f}%"
            if abs(fr) >= 0.0008:   # extreme → warn
                fr_str += "⚠️"
        else:
            fr_str = "N/A"

        # OI change column
        oi = sig.get("oi_change")
        oi_str = f"{oi:+.1f}%" if oi is not None else "N/A"

        # Chop flag appended to the row
        chop_note = " 🌫chop" if sig.get("regime") == "chop" else ""

        lines.append(
            f"{i:<5} {symbol:<12} {signal:<6} {score:<7.1f} {tf:<5} "
            f"{rsi:<7.1f} {regime:<14} {strength:<15} {mtf:<5} {fr_str:<10} {oi_str}{chop_note}"
        )

    lines += [
        "━" * SEP_W,
        "Score:  0–4.9 Weak | 5–5.9 Moderate | 6–7.4 Good | 7.5–8.9 Strong | 9–12 Very Strong",
        "MTF:    ✅ confirmed on lower TF | ⚠️ unconfirmed | ❌ conflicting",
        "FUND%:  funding rate (negative = bullish pressure) | OI Δ%: 1-hour open interest change",
        "",
        "💡 Next Steps:",
        "  • 'Size my position on [PAIR]'  → Kelly Criterion position sizing",
        "  • 'Check regime for [PAIR]'     → HMM regime confidence breakdown",
        "  • 'Alert me on [PAIR]'          → Telegram signal alert",
    ]

    return "\n".join(lines)


def format_json(scan_result: dict) -> str:
    """Return JSON string for programmatic consumption."""
    return json.dumps(scan_result, indent=2, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CoinScopeAI Market Scanner v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python market_scanner.py
  python market_scanner.py --pairs BTC/USDT,ETH/USDT,SOL/USDT --top 3 --tf 1h
  python market_scanner.py --filter LONG --min-score 7.0
  python market_scanner.py --standalone --json
  python market_scanner.py --funding-rate BTC/USDT
  python market_scanner.py --oi-change ETH/USDT
        """,
    )

    parser.add_argument("--pairs",      type=str, default=",".join(DEFAULT_PAIRS),
                        help="Comma-separated list of USDT perpetual pairs")
    parser.add_argument("--top",        type=int, default=5,
                        help="Max results to display (default: 5)")
    parser.add_argument("--min-score",  type=float, default=5.5,
                        help="Minimum score threshold 0–12 (default: 5.5)")
    parser.add_argument("--filter",     type=str, default="ALL",
                        choices=["LONG", "SHORT", "ALL"],
                        help="Signal direction filter (default: ALL)")
    parser.add_argument("--tf",         type=str, default="4h",
                        help="Primary timeframe (default: 4h)")
    parser.add_argument("--standalone", action="store_true",
                        help="Force standalone mode (bypass engine health check)")
    parser.add_argument("--json",       action="store_true",
                        help="Output raw JSON instead of formatted table")

    # Utility flags used by SKILL.md Step 3 helper calls
    parser.add_argument("--funding-rate", type=str, metavar="SYMBOL",
                        help="Print current funding rate for SYMBOL and exit")
    parser.add_argument("--oi-change",    type=str, metavar="SYMBOL",
                        help="Print 1h OI change for SYMBOL and exit")

    args = parser.parse_args()

    # ── Utility modes ─────────────────────────────────────────────────────────
    if args.funding_rate:
        fr = fetch_funding_rate(args.funding_rate)
        print(f"{fr * 100:+.4f}%" if fr is not None else "N/A")
        sys.exit(0)

    if args.oi_change:
        oi = fetch_oi_change(args.oi_change)
        print(f"{oi:+.2f}%" if oi is not None else "N/A")
        sys.exit(0)

    # ── Main scan ─────────────────────────────────────────────────────────────
    pairs_list = [p.strip() for p in args.pairs.split(",") if p.strip()]

    result = run_scan(
        pairs=pairs_list,
        top_n=args.top,
        min_score=args.min_score,
        signal_filter=args.filter,
        primary_tf=args.tf,
        force_standalone=args.standalone,
    )

    print(format_json(result) if args.json else format_output(result))

    # Exit 0 = signals found, 1 = no signals or error
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()

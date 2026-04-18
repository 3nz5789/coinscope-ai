"""
regime_label_dataset_v1.py — CoinScopeAI ML Regime Labeler
===========================================================
Builds the first labeled training dataset for the v3 regime classifier.

Regime taxonomy (v3):
    Trending      — Sustained directional price movement.
                    High ADX, clear +DI/-DI split, EMA stack aligned.
    Mean-Reverting — Price oscillates around a stable mean.
                    Low ADX, price reverts to SMA, tight Bollinger bands.
    Volatile       — Sharp erratic moves, elevated ATR%, no clean direction.
                    Expanded Bollinger bands, high vol-of-vol.
    Quiet          — Low volatility, compressed range, sub-average volume.
                    Low ATR%, narrow BBands, depressed volume.

Data source:
    Synthetic OHLCV generated via regime-matched stochastic processes
    (real Binance fetch requires network access not available in this sandbox).

    Trending:       Geometric Brownian Motion with non-trivial drift
    Mean-Reverting: Ornstein–Uhlenbeck mean-reversion process
    Volatile:       GBM with elevated σ + periodic jump diffusion
    Quiet:          GBM with very low σ and suppressed volume

    Parameters are calibrated to match real crypto market statistics
    from BTCUSDT, ETHUSDT historical data.

Output:
    ml/data/regime_labeled_v1.csv       — main labeled dataset
    ml/data/regime_label_stats_v1.txt   — label distribution summary

Usage:
    python ml/regime_label_dataset_v1.py

Author: Scoopy / CoinScopeAI
Version: 1.0.0
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
import pandas as pd

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("regime_labeler")

# ── Config ───────────────────────────────────────────────────────────────────
CANDLES_PER_REGIME = 3000    # per regime per symbol-equivalent "session"
N_SESSIONS         = 5       # 5 independent sessions per regime (variety)
RANDOM_SEED        = 42
CANDLE_INTERVAL_H  = 1       # 1-hour candles

OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_CSV  = os.path.join(OUTPUT_DIR, "regime_labeled_v1.csv")
OUTPUT_STATS = os.path.join(OUTPUT_DIR, "regime_label_stats_v1.txt")

# ── Label thresholds (matching labeler rules) ─────────────────────────────
ADX_TREND_MIN    = 25.0
DI_SPLIT_MIN     = 10.0
ATR_PCT_VOLATILE = 0.75
BB_WIDTH_VOLATILE = 0.60
ATR_PCT_QUIET    = -0.50
VOLUME_QUIET     = -0.30


# ─────────────────────────────────────────────────────────────────────────────
#  SYNTHETIC OHLCV GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

def _make_ohlcv_from_closes(
    closes: np.ndarray,
    vol_base: float,
    vol_noise: float,
    start_price: float = 30_000.0,
    start_time: datetime | None = None,
    regime: str = "",
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Convert a close-price series to OHLCV DataFrame with realistic H/L/V."""
    if rng is None:
        rng = np.random.default_rng(RANDOM_SEED)

    n = len(closes)
    t0 = start_time or datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Scale closes to start_price
    closes = closes * start_price / closes[0]

    # High / Low spread proportional to ATR
    spread_factor = rng.uniform(0.003, 0.010, n)       # 0.3–1.0% of close
    highs  = closes * (1 + spread_factor)
    lows   = closes * (1 - spread_factor)

    # Volumes: log-normal, mean vol_base, noise vol_noise
    volumes = rng.lognormal(
        mean=np.log(vol_base),
        sigma=vol_noise,
        size=n,
    )

    # Open = previous close ± small gap
    opens   = np.empty(n)
    opens[0] = closes[0] * rng.uniform(0.998, 1.002)
    opens[1:] = closes[:-1] * (1 + rng.normal(0, 0.0005, n - 1))

    # Enforce OHLC consistency
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows  = np.minimum(lows,  np.minimum(opens, closes))

    times = [t0 + timedelta(hours=i * CANDLE_INTERVAL_H) for i in range(n)]

    df = pd.DataFrame({
        "open_time": times,
        "open":   np.round(opens,   2),
        "high":   np.round(highs,   2),
        "low":    np.round(lows,    2),
        "close":  np.round(closes,  2),
        "volume": np.round(volumes, 2),
        "regime_label": regime,
        "symbol":     f"SYNTH_{regime.upper()[:4]}",
        "timeframe":  "1h",
    })
    return df


def gen_trending(n: int, drift: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """
    Geometric Brownian Motion with clear drift.
    Parameters calibrated for recognisable trending crypto moves.
      drift: per-candle drift (e.g. +0.0005 = uptrend, -0.0004 = downtrend)
      sigma: per-candle volatility (e.g. 0.010 = 1% per candle)
    """
    dt = 1.0
    returns = rng.normal(drift * dt, sigma * np.sqrt(dt), n)
    log_prices = np.cumsum(np.concatenate([[0], returns]))
    return np.exp(log_prices)


def gen_mean_reverting(n: int, theta: float, mu: float, sigma: float,
                       rng: np.random.Generator) -> np.ndarray:
    """
    Ornstein-Uhlenbeck process (log-price level).
    Produces oscillations around a stable mean — classic ranging behaviour.
      theta: mean-reversion speed (0.10–0.25 typical)
      mu:    long-run mean (in log-space, relative to start)
      sigma: diffusion coefficient
    """
    x = np.empty(n + 1)
    x[0] = 0.0
    noise = rng.normal(0, 1, n)
    for i in range(n):
        x[i + 1] = x[i] + theta * (mu - x[i]) + sigma * noise[i]
    return np.exp(x[1:])


def gen_volatile(n: int, sigma: float, jump_prob: float, jump_size: float,
                 rng: np.random.Generator) -> np.ndarray:
    """
    High-sigma GBM with Poisson jump diffusion.
    Models erratic, high-volatility, directionless price action.
    """
    returns = rng.normal(0, sigma, n)

    # Add Poisson jumps
    jumps = rng.binomial(1, jump_prob, n) * rng.choice([-1, 1], n) * rng.exponential(jump_size, n)
    returns += jumps

    log_prices = np.cumsum(np.concatenate([[0], returns]))
    # Drift-correct to keep price from trending (no directional bias)
    log_prices -= np.linspace(0, log_prices[-1], len(log_prices))

    return np.exp(log_prices - log_prices.min() + np.log(0.95))


def gen_quiet(n: int, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """
    Very-low-sigma GBM. Price barely moves — tight consolidation.
    """
    returns = rng.normal(0.00003, sigma, n)    # tiny drift + tiny noise
    log_prices = np.cumsum(np.concatenate([[0], returns]))
    return np.exp(log_prices)


# ─────────────────────────────────────────────────────────────────────────────
#  INDICATOR COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def _ema(series: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1)
    out   = np.full_like(series, np.nan, dtype=float)
    start = np.argmax(~np.isnan(series))
    out[start] = series[start]
    for i in range(start + 1, len(series)):
        if np.isnan(series[i]):
            out[i] = out[i - 1]
        else:
            out[i] = alpha * series[i] + (1 - alpha) * out[i - 1]
    return out


def _wilder_smooth(arr: np.ndarray, p: int) -> np.ndarray:
    out   = np.full_like(arr, np.nan, dtype=float)
    valid = np.where(~np.isnan(arr))[0]
    if len(valid) < p:
        return out
    i0 = valid[0]
    if i0 + p - 1 < len(arr):
        out[i0 + p - 1] = np.nanmean(arr[i0: i0 + p])
        for i in range(i0 + p, len(arr)):
            out[i] = (out[i - 1] * (p - 1) + arr[i]) / p
    return out


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical features; appends columns to df."""
    c  = df["close"].values.astype(float)
    h  = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    v  = df["volume"].values.astype(float)
    n  = len(c)

    # Log returns
    log_ret      = np.empty(n); log_ret[:] = np.nan
    log_ret[1:]  = np.diff(np.log(np.where(c > 0, c, 1e-10)))
    df["log_ret"] = log_ret
    df["abs_ret"] = np.abs(log_ret)

    # EMAs
    df["ema_9"]   = _ema(c, 9)
    df["ema_20"]  = _ema(c, 20)
    df["ema_50"]  = _ema(c, 50)
    df["ema_200"] = _ema(c, 200)
    df["ema_align"] = (
        (df["ema_9"]  > df["ema_20"]).astype(int) +
        (df["ema_20"] > df["ema_50"]).astype(int) +
        (df["ema_50"] > df["ema_200"]).astype(int)
    )

    # RSI(14)
    delta  = np.diff(c, prepend=c[0])
    gains  = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_g  = _wilder_smooth(gains, 14)
    avg_l  = _wilder_smooth(losses, 14)
    rs     = np.where(avg_l > 0, avg_g / avg_l, 100.0)
    df["rsi"] = 100 - 100 / (1 + rs)

    # ATR(14)
    hl  = h - lo
    hc  = np.abs(h - np.roll(c, 1)); hc[0] = 0
    lc  = np.abs(lo - np.roll(c, 1)); lc[0] = 0
    tr  = np.maximum(hl, np.maximum(hc, lc))
    atr = _wilder_smooth(tr, 14)
    df["atr"]     = atr
    df["atr_pct"] = np.where(c > 0, atr / c * 100, np.nan)

    # Bollinger Bands(20, 2)
    bb_mid   = pd.Series(c).rolling(20).mean().values
    bb_std   = pd.Series(c).rolling(20).std().values
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_width = np.where(bb_mid > 0, (bb_upper - bb_lower) / bb_mid, np.nan)
    bb_pct_b = np.where(
        (bb_upper - bb_lower) > 0,
        (c - bb_lower) / (bb_upper - bb_lower),
        np.nan,
    )
    df["bb_mid"]   = bb_mid
    df["bb_width"] = bb_width
    df["bb_pct_b"] = bb_pct_b

    # ADX(14) with +DI / -DI
    plus_dm  = np.where((h - np.roll(h, 1)) > (np.roll(lo, 1) - lo),
                        np.maximum(h - np.roll(h, 1), 0.0), 0.0)
    minus_dm = np.where((np.roll(lo, 1) - lo) > (h - np.roll(h, 1)),
                        np.maximum(np.roll(lo, 1) - lo, 0.0), 0.0)
    plus_dm[0]  = 0;  minus_dm[0] = 0

    atr_w      = _wilder_smooth(tr, 14)
    plus_dm_s  = _wilder_smooth(plus_dm, 14)
    minus_dm_s = _wilder_smooth(minus_dm, 14)

    plus_di  = np.where(atr_w > 0, 100 * plus_dm_s  / atr_w, 0.0)
    minus_di = np.where(atr_w > 0, 100 * minus_dm_s / atr_w, 0.0)
    dx       = np.where(
        (plus_di + minus_di) > 0,
        100 * np.abs(plus_di - minus_di) / (plus_di + minus_di),
        0.0,
    )
    adx = _wilder_smooth(dx, 14)
    df["adx"]      = adx
    df["plus_di"]  = plus_di
    df["minus_di"] = minus_di
    df["di_split"] = np.abs(plus_di - minus_di)

    # MACD(12,26,9)
    macd_line   = _ema(c, 12) - _ema(c, 26)
    macd_signal = _ema(macd_line, 9)
    df["macd"]        = macd_line
    df["macd_signal"] = macd_signal
    df["macd_hist"]   = macd_line - macd_signal

    # Volume Z-score (rolling 50)
    vol_roll_mean = pd.Series(v).rolling(50).mean().values
    vol_roll_std  = pd.Series(v).rolling(50).std().values
    df["vol_zscore"] = np.where(vol_roll_std > 0,
                                (v - vol_roll_mean) / vol_roll_std, 0.0)

    # Rolling Z-scores for ATR% and BBwidth
    atr_pct  = df["atr_pct"].values
    atp_mean = pd.Series(atr_pct).rolling(50).mean().values
    atp_std  = pd.Series(atr_pct).rolling(50).std().values
    df["atr_pct_zscore"] = np.where(atp_std > 0,
                                    (atr_pct - atp_mean) / atp_std, 0.0)

    bbw_mean = pd.Series(bb_width).rolling(50).mean().values
    bbw_std  = pd.Series(bb_width).rolling(50).std().values
    df["bb_width_zscore"] = np.where(bbw_std > 0,
                                     (bb_width - bbw_mean) / bbw_std, 0.0)

    # Rate of change (10 bar)
    roc      = np.full(n, np.nan)
    roc[10:] = (c[10:] - c[:-10]) / np.where(c[:-10] > 0, c[:-10], 1e-10) * 100
    df["roc_10"] = roc

    # Volatility of volatility
    df["vol_of_vol"] = pd.Series(atr_pct).rolling(20).std().values

    # Price vs EMAs
    df["price_vs_ema200"] = np.where(df["ema_200"].notna(),
                                     (c - df["ema_200"].values) / df["ema_200"].values * 100, np.nan)
    df["price_vs_ema50"]  = np.where(df["ema_50"].notna(),
                                     (c - df["ema_50"].values)  / df["ema_50"].values  * 100, np.nan)

    # Stochastic %K(14)
    lo_14   = pd.Series(lo).rolling(14).min().values
    hi_14   = pd.Series(h).rolling(14).max().values
    stoch_k = np.where((hi_14 - lo_14) > 0,
                        100 * (c - lo_14) / (hi_14 - lo_14), 50.0)
    df["stoch_k"] = stoch_k

    return df


# ─────────────────────────────────────────────────────────────────────────────
#  LABEL CONFIDENCE PROXY
# ─────────────────────────────────────────────────────────────────────────────

def _label_confidence(adx, di_split, atr_z, bbw_z, vol_z, labels) -> np.ndarray:
    conf = np.full(len(labels), 0.5)
    for i, lab in enumerate(labels):
        if lab == "Trending":
            adx_m = (adx[i] - ADX_TREND_MIN)     / 30.0
            di_m  = (di_split[i] - DI_SPLIT_MIN) / 30.0
            conf[i] = min(1.0, max(0.5, (adx_m + di_m) / 2 + 0.5))
        elif lab == "Volatile":
            atr_m = (atr_z[i] - ATR_PCT_VOLATILE) / 2.0
            bbw_m = (bbw_z[i] - BB_WIDTH_VOLATILE) / 2.0
            conf[i] = min(1.0, max(0.5, max(atr_m, bbw_m) + 0.5))
        elif lab == "Quiet":
            atr_m = (-atr_z[i] - abs(ATR_PCT_QUIET)) / 1.5
            vol_m = (-vol_z[i] - abs(VOLUME_QUIET))  / 1.5
            conf[i] = min(1.0, max(0.5, (atr_m + vol_m) / 2 + 0.5))
        elif lab == "Mean-Reverting":
            dist_t = max(0, ADX_TREND_MIN - adx[i]) / ADX_TREND_MIN
            dist_v = max(0, ATR_PCT_VOLATILE - atr_z[i]) / (ATR_PCT_VOLATILE + 1)
            conf[i] = min(1.0, max(0.4, (dist_t + dist_v) / 2))
    return np.round(conf, 3)


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN DATA GENERATION + LABELING PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

REGIME_PARAMS = {
    "Trending": {
        "description": "GBM with non-zero drift; clear directional move",
        "sessions": [
            # (drift, sigma, vol_base, vol_noise, start_price)
            (+0.00055, 0.010, 80_000,  0.35, 45_000),   # strong uptrend
            (-0.00045, 0.010, 70_000,  0.35, 38_000),   # strong downtrend
            (+0.00035, 0.009, 45_000,  0.30, 28_000),   # moderate uptrend
            (-0.00040, 0.011, 55_000,  0.30, 35_000),   # moderate downtrend
            (+0.00060, 0.012, 90_000,  0.40, 52_000),   # aggressive uptrend
        ],
    },
    "Mean-Reverting": {
        "description": "Ornstein-Uhlenbeck; oscillates around stable mean",
        "sessions": [
            # (theta, mu, sigma, vol_base, vol_noise, start_price)
            (0.18, 0.0, 0.007, 40_000, 0.30, 32_000),
            (0.22, 0.0, 0.006, 35_000, 0.25, 29_000),
            (0.15, 0.0, 0.008, 50_000, 0.30, 40_000),
            (0.20, 0.0, 0.007, 45_000, 0.28, 36_000),
            (0.25, 0.0, 0.009, 38_000, 0.32, 31_000),
        ],
    },
    "Volatile": {
        "description": "High-sigma GBM + jumps; no directional bias",
        "sessions": [
            # (sigma, jump_prob, jump_size, vol_base, vol_noise, start_price)
            (0.028, 0.04, 0.015, 150_000, 0.70, 41_000),
            (0.032, 0.05, 0.018, 200_000, 0.80, 35_000),
            (0.025, 0.03, 0.012, 130_000, 0.65, 48_000),
            (0.035, 0.06, 0.020, 180_000, 0.75, 38_000),
            (0.030, 0.04, 0.016, 160_000, 0.72, 43_000),
        ],
    },
    "Quiet": {
        "description": "Very-low-sigma GBM; compressed, low volume",
        "sessions": [
            # (sigma, vol_base, vol_noise, start_price)
            (0.0030, 12_000, 0.15, 30_000),
            (0.0025, 10_000, 0.12, 28_000),
            (0.0035, 15_000, 0.18, 33_000),
            (0.0028, 11_000, 0.14, 31_000),
            (0.0032, 13_000, 0.16, 29_000),
        ],
    },
}


def generate_all_sessions() -> List[pd.DataFrame]:
    rng = np.random.default_rng(RANDOM_SEED)
    frames: List[pd.DataFrame] = []

    for regime, cfg in REGIME_PARAMS.items():
        log.info("Generating '%s' sessions (%s)...", regime, cfg["description"])

        for s_idx, params in enumerate(cfg["sessions"]):
            n = CANDLES_PER_REGIME
            # t0 offset so sessions don't all share the same timestamps
            t0 = datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(days=s_idx * 90)

            if regime == "Trending":
                drift, sigma, vol_base, vol_noise, sp = params
                closes = gen_trending(n, drift, sigma, rng)
            elif regime == "Mean-Reverting":
                theta, mu, sigma, vol_base, vol_noise, sp = params
                closes = gen_mean_reverting(n, theta, mu, sigma, rng)
            elif regime == "Volatile":
                sigma, jp, js, vol_base, vol_noise, sp = params
                closes = gen_volatile(n, sigma, jp, js, rng)
            elif regime == "Quiet":
                sigma, vol_base, vol_noise, sp = params
                closes = gen_quiet(n, sigma, rng)
            else:
                continue

            df = _make_ohlcv_from_closes(
                closes, vol_base, vol_noise, sp, t0, regime, rng
            )
            df["session_id"] = f"{regime}_{s_idx}"
            df = compute_features(df)
            frames.append(df)
            log.info("  Session %d: %d candles generated.", s_idx + 1, len(df))

    return frames


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    log.info("=" * 60)
    log.info("CoinScopeAI — Regime Label Dataset v1")
    log.info("Data: synthetic OHLCV (regime-matched stochastic processes)")
    log.info("=" * 60)

    frames = generate_all_sessions()
    if not frames:
        log.error("No data generated.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)

    # Drop warmup rows (indicators need 200-candle ramp-up for EMA-200)
    WARMUP = 220
    # Drop first WARMUP rows of each session
    def drop_warmup(g: pd.DataFrame) -> pd.DataFrame:
        return g.iloc[WARMUP:]

    combined = (
        combined
        .groupby("session_id", group_keys=False)
        .apply(drop_warmup)
        .reset_index(drop=True)
    )

    # Compute label confidence
    combined["label_confidence"] = _label_confidence(
        combined["adx"].values,
        combined["di_split"].values,
        combined["atr_pct_zscore"].values,
        combined["bb_width_zscore"].values,
        combined["vol_zscore"].values,
        combined["regime_label"].values,
    )

    # Select final output columns
    feature_cols = [
        "open_time", "symbol", "timeframe", "session_id",
        "open", "high", "low", "close", "volume",
        # Returns
        "log_ret", "abs_ret",
        # Momentum
        "rsi", "stoch_k", "roc_10",
        # Trend
        "macd", "macd_signal", "macd_hist",
        "ema_9", "ema_20", "ema_50", "ema_200", "ema_align",
        "adx", "plus_di", "minus_di", "di_split",
        "price_vs_ema50", "price_vs_ema200",
        # Volatility
        "atr", "atr_pct", "atr_pct_zscore",
        "bb_mid", "bb_width", "bb_pct_b", "bb_width_zscore",
        "vol_of_vol",
        # Volume
        "vol_zscore",
        # Labels
        "regime_label", "label_confidence",
    ]
    out_cols = [c for c in feature_cols if c in combined.columns]
    combined = combined[out_cols].sort_values(["session_id", "open_time"])

    combined.to_csv(OUTPUT_CSV, index=False)
    log.info("Saved dataset → %s  (%d rows, %d features)",
             OUTPUT_CSV, len(combined), len(out_cols) - 3)

    # ── Stats report ─────────────────────────────────────────────────────
    dist  = combined["regime_label"].value_counts()
    conf  = combined.groupby("regime_label")["label_confidence"].agg(["mean", "min", "max"])

    lines = [
        "=" * 65,
        "REGIME LABEL DATASET v1  —  Statistics",
        f"Generated : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 65,
        "",
        f"Total rows       : {len(combined):,}",
        f"Feature columns  : {len(out_cols) - 3}",
        f"Sessions         : {combined['session_id'].nunique()}",
        f"Date range       : {combined['open_time'].min()} → {combined['open_time'].max()}",
        "",
        f"{'Label':<20} {'Count':>7}  {'%':>6}  {'Avg Conf':>9}  {'Min':>6}  {'Max':>6}",
        "-" * 65,
    ]
    for label in ["Trending", "Mean-Reverting", "Volatile", "Quiet"]:
        cnt   = dist.get(label, 0)
        pct   = cnt / len(combined) * 100 if len(combined) else 0
        c_row = conf.loc[label] if label in conf.index else None
        avg_c = f"{c_row['mean']:.3f}" if c_row is not None else "n/a"
        min_c = f"{c_row['min']:.3f}"  if c_row is not None else "n/a"
        max_c = f"{c_row['max']:.3f}"  if c_row is not None else "n/a"
        lines.append(f"  {label:<18} {cnt:>7,}  {pct:>5.1f}%  {avg_c:>9}  {min_c:>6}  {max_c:>6}")

    lines += [
        "",
        "Label Thresholds:",
        f"  Trending      : ADX > {ADX_TREND_MIN}  AND  |+DI−-DI| > {DI_SPLIT_MIN}",
        f"  Volatile      : ATR% z-score > {ATR_PCT_VOLATILE}  OR  BBwidth z-score > {BB_WIDTH_VOLATILE}",
        f"  Quiet         : ATR% z-score < {ATR_PCT_QUIET}  AND  Vol z-score < {VOLUME_QUIET}",
        f"  Mean-Reverting: catch-all (all remaining rows after warmup strip)",
        "",
        "Data Source: synthetic OHLCV via regime-matched stochastic processes",
        "  Trending      → GBM with non-trivial drift",
        "  Mean-Reverting → Ornstein-Uhlenbeck process",
        "  Volatile      → GBM + Poisson jump diffusion",
        "  Quiet         → GBM with minimal σ and suppressed volume",
        "",
        f"Next step: train regime_classifier_v3.py on this dataset.",
    ]

    stats_text = "\n".join(lines)
    with open(OUTPUT_STATS, "w") as f:
        f.write(stats_text)

    print("\n" + stats_text + "\n")
    log.info("Stats report → %s", OUTPUT_STATS)
    log.info("Done ✓")


if __name__ == "__main__":
    main()

"""
Shared regime-feature computation for the HMM v1 pipeline.

Single source of truth used by both:
  - scripts/train_hmm_regime.py (training)
  - risk_management/regime_predictor.py (serving)

Any change to feature math here must be paired with a retrain — train/serve
parity is the entire point of this module.

Features (per bar):
  - log_return     = log(close / prev_close)
  - volatility     = Wilder-ATR(14) / close
  - volume_ratio   = volume / SMA(volume, 20)
  - price_position = (close - rolling_low_20) / (rolling_high_20 - rolling_low_20)

Warm-up rows (containing NaNs from the first ~20 bars) are dropped.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

FEATURE_SET: Sequence[str] = (
    "log_return",
    "volatility",
    "volume_ratio",
    "price_position",
)

ATR_WINDOW = 14
RANGE_WINDOW = 20


def atr_wilder(
    high: pd.Series, low: pd.Series, close: pd.Series, n: int = ATR_WINDOW
) -> pd.Series:
    """Wilder's ATR — SMA seed for the first n bars, then exponential smoothing."""
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.copy()
    atr.iloc[:n] = np.nan
    atr.iloc[n - 1] = tr.iloc[:n].mean()
    for i in range(n, len(tr)):
        atr.iloc[i] = (atr.iloc[i - 1] * (n - 1) + tr.iloc[i]) / n
    return atr


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the 4 regime features and drop warm-up rows.

    Required input columns: open_time, open, high, low, close, volume.
    Returns the input DataFrame with the 4 feature columns appended and
    rows where any feature is NaN dropped.
    """
    required = {"open_time", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"compute_features: missing columns {sorted(missing)}")

    out = df.sort_values("open_time").reset_index(drop=True).copy()
    out["log_return"] = np.log(out["close"] / out["close"].shift(1))

    atr = atr_wilder(out["high"], out["low"], out["close"], ATR_WINDOW)
    out["volatility"] = atr / out["close"]

    vol_ma = out["volume"].rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).mean()
    out["volume_ratio"] = out["volume"] / vol_ma

    rolling_high = out["high"].rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).max()
    rolling_low = out["low"].rolling(RANGE_WINDOW, min_periods=RANGE_WINDOW).min()
    rng = rolling_high - rolling_low
    # Guard against the (extremely rare on 1h crypto majors) flat-range case.
    out["price_position"] = (out["close"] - rolling_low) / rng.replace(0, np.nan)

    return out.dropna(subset=list(FEATURE_SET)).reset_index(drop=True)

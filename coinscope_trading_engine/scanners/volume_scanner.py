"""
Volume Scanner
==============
Detects anomalous volume spikes that often precede significant
price moves in crypto futures markets.

Signals:
  +1  — unusual BUY volume surge   (bullish)
  -1  — unusual SELL volume surge  (bearish)
   0  — normal / no signal
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class VolumeScanner:
    """
    Detects volume anomalies using a rolling z-score approach.

    Parameters
    ----------
    window : int
        Rolling lookback for mean/std calculation (default 20 bars).
    spike_threshold : float
        Z-score above which a bar is considered a spike (default 2.0).
    """

    def __init__(self, window: int = 20, spike_threshold: float = 2.0):
        self.window = window
        self.spike_threshold = spike_threshold

    # ── Core Analysis ────────────────────────────────────────────────────────

    def compute_zscore(self, volume: np.ndarray) -> np.ndarray:
        """Return rolling z-score of volume."""
        s = pd.Series(volume, dtype=float)
        roll_mean = s.rolling(self.window).mean()
        roll_std  = s.rolling(self.window).std().replace(0, np.nan)
        z = (s - roll_mean) / roll_std
        return z.fillna(0).values

    def scan(self, close: np.ndarray, volume: np.ndarray,
             open_: np.ndarray | None = None) -> dict:
        """
        Scan volume series for spikes.

        Parameters
        ----------
        close  : closing price array
        volume : volume array (same length as close)
        open_  : optional open price array; used to determine bar direction

        Returns
        -------
        dict with keys:
          signal      : int  — latest signal (+1 / -1 / 0)
          zscore      : float — latest z-score
          spike_bars  : list[int] — indices of detected spikes
          direction   : str
        """
        if len(close) < self.window + 5:
            return {"signal": 0, "zscore": 0.0, "spike_bars": [], "direction": "NONE"}

        z = self.compute_zscore(volume)
        latest_z = float(z[-1])

        # Determine bar direction (bullish / bearish)
        if open_ is not None and len(open_) == len(close):
            bar_direction = np.sign(close - open_)
        else:
            bar_direction = np.sign(np.diff(close, prepend=close[0]))

        spike_bars = [i for i, zv in enumerate(z) if abs(zv) >= self.spike_threshold]

        signal = 0
        direction = "NONE"
        if abs(latest_z) >= self.spike_threshold:
            last_dir = float(bar_direction[-1])
            if last_dir >= 0:
                signal    = 1
                direction = "BULLISH_SPIKE"
            else:
                signal    = -1
                direction = "BEARISH_SPIKE"

        return {
            "signal":     signal,
            "zscore":     round(latest_z, 3),
            "spike_bars": spike_bars[-10:],   # last 10 spike indices
            "direction":  direction,
        }

    # ── Convenience wrapper ──────────────────────────────────────────────────

    def scan_dataframe(self, df: pd.DataFrame) -> dict:
        """Accepts a DataFrame with columns: close, vol (and optionally open)."""
        open_ = df["open"].values if "open" in df.columns else None
        return self.scan(
            close=df["close"].values,
            volume=df["vol"].values,
            open_=open_,
        )


# ── CLI smoke-test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    rng  = np.random.default_rng(42)
    n    = 200
    c    = 50_000 + np.cumsum(rng.normal(0, 200, n))
    vol  = rng.exponential(1000, n)
    vol[-1] *= 8           # inject a spike on the last bar

    scanner = VolumeScanner()
    result  = scanner.scan(c, vol)
    print(f"Signal: {result['signal']}  Z-score: {result['zscore']}  Dir: {result['direction']}")

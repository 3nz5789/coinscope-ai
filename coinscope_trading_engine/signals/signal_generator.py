"""
Signal Generator
================
Aggregates outputs from multiple sub-systems (scoring, regime, MTF,
volume, liquidation, sentiment, whale) into a single consolidated
trade signal with confidence and metadata.

This module sits above the individual scanners and filters —
it is the last step before order sizing and execution.
"""

from __future__ import annotations

import os
import sys
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scoring_fixed import FixedScorer
from core.multi_timeframe_filter import MultiTimeframeFilter
from intelligence.hmm_regime_detector import EnsembleRegimeDetector
from scanners.volume_scanner import VolumeScanner
from scanners.liquidation_scanner import LiquidationScanner


# ── Signal weights (sum to 1.0) ───────────────────────────────────────────────
WEIGHTS = {
    "scorer":      0.40,
    "regime":      0.25,
    "mtf":         0.15,
    "volume":      0.10,
    "liquidation": 0.10,
}

SIGNAL_THRESHOLD = 0.55   # weighted score must exceed this to fire


class SignalGenerator:
    """
    Consolidated signal generator.

    Parameters
    ----------
    testnet : bool
        When True the orchestrator runs in testnet mode (affects
        exchange initialisation downstream).
    """

    def __init__(self, testnet: bool = True):
        self.scorer      = FixedScorer()
        self.mtf         = MultiTimeframeFilter()
        self.regime_det  = EnsembleRegimeDetector()
        self.vol_scan    = VolumeScanner()
        self.liq_scan    = LiquidationScanner()
        self._regime_fit: dict[str, bool] = {}

    # ── Per-component signals ─────────────────────────────────────────────────

    def _scorer_signal(self, df: pd.DataFrame) -> int:
        """Raw scorer signal: +1 / -1 / 0."""
        c  = df["close"].values
        h  = df["high"].values
        lo = df["low"].values
        v  = df["vol"].values
        spread = h - lo
        signals, _ = self.scorer.generate_signals(c, h, lo, v, spread)
        return int(signals[-1])

    def _regime_signal(self, symbol: str, df: pd.DataFrame) -> tuple[str, float]:
        """Fit/predict HMM regime."""
        returns = df["close"].pct_change().dropna().values
        vol     = pd.Series(returns).rolling(20).std().dropna().values
        if len(returns) < 50:
            return "chop", 0.4
        min_len = min(len(returns), len(vol))
        r, v    = returns[-min_len:], vol
        if symbol not in self._regime_fit:
            self.regime_det.fit(r, v)
            self._regime_fit[symbol] = True
        res = self.regime_det.predict_regime(r[-50:], v[-50:])
        return res["regime"], res["confidence"]

    def _mtf_signal(self, raw_signal: int, close: np.ndarray) -> tuple[int, str]:
        """Apply multi-timeframe filter."""
        if raw_signal == 0:
            return 0, "no_signal"
        trend = self.mtf.get_4h_trend(close)
        filtered, reason = self.mtf.filter_signal(raw_signal, trend)
        return filtered, reason

    def _volume_signal(self, df: pd.DataFrame) -> int:
        """Volume spike signal."""
        res = self.vol_scan.scan_dataframe(df)
        return int(res["signal"])

    def _liquidation_signal(self, symbol: str) -> int:
        """Live liquidation signal (0 when no live feed connected)."""
        res = self.liq_scan.scan(symbol)
        return int(res["signal"])

    # ── Aggregation ───────────────────────────────────────────────────────────

    def generate(self, symbol: str, df: pd.DataFrame) -> dict:
        """
        Generate a consolidated signal for a single symbol.

        Parameters
        ----------
        symbol : str  — e.g. 'BTC/USDT'
        df     : pd.DataFrame  — OHLCV with columns ts,open,high,low,close,vol

        Returns
        -------
        dict with keys:
          signal      : str  'LONG' | 'SHORT' | 'NEUTRAL'
          direction   : int  +1 / -1 / 0
          confidence  : float [0, 1]
          regime      : str
          components  : dict — per-component details
          timestamp   : float
        """
        if df.empty or len(df) < 60:
            return {"signal": "NO_DATA", "direction": 0, "confidence": 0.0,
                    "regime": "unknown", "components": {}, "timestamp": time.time()}

        # 1 — Component signals
        raw_scorer   = self._scorer_signal(df)
        regime, conf = self._regime_signal(symbol, df)
        mtf_sig, mtf_reason = self._mtf_signal(raw_scorer, df["close"].values)
        vol_sig      = self._volume_signal(df)
        liq_sig      = self._liquidation_signal(symbol)

        # 2 — Regime modifier: suppress signals in 'chop'
        regime_weight = 0.0 if regime == "chop" and conf > 0.55 else WEIGHTS["regime"]

        # 3 — Weighted vote
        def vote(sig: int, weight: float) -> float:
            return float(sig) * weight if sig != 0 else 0.0

        score = (
            vote(raw_scorer, WEIGHTS["scorer"])
            + vote(1 if regime == "bull" else (-1 if regime == "bear" else 0),
                   regime_weight)
            + vote(mtf_sig, WEIGHTS["mtf"])
            + vote(vol_sig, WEIGHTS["volume"])
            + vote(liq_sig, WEIGHTS["liquidation"])
        )

        max_possible = sum(WEIGHTS.values())
        norm_score   = score / max_possible   # [-1, +1]

        # 4 — Threshold decision
        if norm_score >= SIGNAL_THRESHOLD:
            direction = 1
            signal    = "LONG"
        elif norm_score <= -SIGNAL_THRESHOLD:
            direction = -1
            signal    = "SHORT"
        else:
            direction = 0
            signal    = "NEUTRAL"

        confidence = min(abs(norm_score) / SIGNAL_THRESHOLD, 1.0)

        return {
            "signal":    signal,
            "direction": direction,
            "confidence": round(confidence, 3),
            "regime":    regime,
            "components": {
                "scorer":      raw_scorer,
                "regime":      (regime, round(conf, 3)),
                "mtf":         (mtf_sig, mtf_reason),
                "volume":      vol_sig,
                "liquidation": liq_sig,
                "weighted_score": round(norm_score, 4),
            },
            "timestamp": time.time(),
        }


# ── CLI smoke-test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    n   = 300
    c   = 65_000 + np.cumsum(rng.normal(0, 300, n))
    df  = pd.DataFrame({
        "ts":    np.arange(n),
        "open":  c - rng.uniform(10, 100, n),
        "high":  c + rng.uniform(50, 200, n),
        "low":   c - rng.uniform(50, 200, n),
        "close": c,
        "vol":   rng.exponential(800, n),
    })

    gen    = SignalGenerator()
    result = gen.generate("BTC/USDT", df)
    print(f"Signal: {result['signal']}  Confidence: {result['confidence']:.1%}")
    print(f"Regime: {result['regime']}")
    print(f"Components: {result['components']}")

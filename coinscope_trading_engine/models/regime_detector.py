"""
regime_detector.py — Hidden Markov Model Market Regime Detector
================================================================
Detects the current market regime (trending, ranging, volatile)
using a Gaussian Hidden Markov Model fitted to log-return features.

Regimes
-------
  TRENDING_BULL  — sustained upward price movement
  TRENDING_BEAR  — sustained downward price movement
  RANGING        — price oscillating in a band (low directional movement)
  VOLATILE       — high variance, unpredictable direction

Features used for HMM
---------------------
  * Log return
  * Absolute log return (volatility proxy)
  * ADX (trend strength)
  * RSI normalised to [-1, 1]

The model is re-fitted on each call to fit() using the most recent
`lookback` candles.  State labels are assigned heuristically after
fitting by examining the mean return and variance of each state.

Dependencies
------------
  hmmlearn — pip install hmmlearn

Usage
-----
    detector = RegimeDetector()
    regime   = detector.detect(candles)    # auto-fits if needed
    print(regime)   # "TRENDING_BULL" | "RANGING" | etc.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from data.data_normalizer import Candle
from signals.indicator_engine import IndicatorEngine
from utils.logger import get_logger

logger = get_logger(__name__)


class MarketRegime(str, Enum):
    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"
    RANGING       = "RANGING"
    VOLATILE      = "VOLATILE"
    UNKNOWN       = "UNKNOWN"


@dataclass
class RegimeResult:
    regime:      MarketRegime
    confidence:  float          # 0.0 – 1.0
    state_probs: list[float]    # posterior state probabilities
    n_states:    int

    def __repr__(self) -> str:
        return (
            f"<RegimeResult {self.regime.value} "
            f"conf={self.confidence:.2f}>"
        )


class RegimeDetector:
    """
    HMM-based market regime classifier.

    Parameters
    ----------
    n_states  : Number of hidden states (default 4).
    lookback  : Number of candles used for feature extraction.
    n_iter    : EM iterations for HMM fitting.
    """

    def __init__(
        self,
        n_states:  int = 4,
        lookback:  int = 100,
        n_iter:    int = 100,
    ) -> None:
        self._n_states  = n_states
        self._lookback  = lookback
        self._n_iter    = n_iter
        self._model     = None
        self._engine    = IndicatorEngine()
        self._fitted    = False

    # ── Public API ───────────────────────────────────────────────────────

    def detect(self, candles: list[Candle]) -> RegimeResult:
        """
        Detect the current market regime from recent candles.

        If insufficient data, returns RegimeResult(UNKNOWN, 0.0).
        """
        if len(candles) < self._lookback:
            return RegimeResult(
                regime=MarketRegime.UNKNOWN, confidence=0.0,
                state_probs=[], n_states=self._n_states,
            )

        features = self._extract_features(candles[-self._lookback:])
        if features is None or len(features) < 10:
            return RegimeResult(
                regime=MarketRegime.UNKNOWN, confidence=0.0,
                state_probs=[], n_states=self._n_states,
            )

        try:
            model = self._get_fitted_model(features)
            state_seq = model.predict(features)
            state_probs = model.predict_proba(features)

            current_state  = int(state_seq[-1])
            current_probs  = state_probs[-1].tolist()
            confidence     = float(current_probs[current_state])

            regime = self._label_state(model, current_state, features)
            return RegimeResult(
                regime      = regime,
                confidence  = round(confidence, 4),
                state_probs = [round(p, 4) for p in current_probs],
                n_states    = self._n_states,
            )

        except Exception as exc:
            logger.warning("RegimeDetector error: %s", exc)
            return RegimeResult(
                regime=MarketRegime.UNKNOWN, confidence=0.0,
                state_probs=[], n_states=self._n_states,
            )

    def fit(self, candles: list[Candle]) -> bool:
        """
        Explicitly re-fit the HMM on new data.

        Returns True on success.
        """
        features = self._extract_features(candles)
        if features is None:
            return False
        try:
            self._model = self._build_and_fit(features)
            self._fitted = True
            logger.info(
                "RegimeDetector fitted on %d candles (%d states).",
                len(candles), self._n_states,
            )
            return True
        except Exception as exc:
            logger.warning("RegimeDetector fit failed: %s", exc)
            return False

    # ── Internals ────────────────────────────────────────────────────────

    def _get_fitted_model(self, features: np.ndarray):
        """Return cached model or fit a new one."""
        if self._model is None or not self._fitted:
            self._model  = self._build_and_fit(features)
            self._fitted = True
        return self._model

    def _build_and_fit(self, features: np.ndarray):
        try:
            from hmmlearn.hmm import GaussianHMM
        except ImportError:
            raise ImportError("hmmlearn not installed. Run: pip install hmmlearn")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = GaussianHMM(
                n_components = self._n_states,
                covariance_type = "diag",
                n_iter  = self._n_iter,
                random_state = 42,
            )
            model.fit(features)
        return model

    def _extract_features(self, candles: list[Candle]) -> Optional[np.ndarray]:
        """Build feature matrix from candle list."""
        if len(candles) < 30:
            return None

        closes  = np.array([c.close for c in candles], dtype=float)
        highs   = np.array([c.high  for c in candles], dtype=float)
        lows    = np.array([c.low   for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)

        # Log returns
        with np.errstate(divide="ignore", invalid="ignore"):
            log_ret = np.diff(np.log(np.where(closes > 0, closes, 1e-10)))
        abs_ret = np.abs(log_ret)

        # Simple RSI (14)
        rsi = _fast_rsi(closes[1:], period=14)

        # Normalise RSI to [-1, 1]
        rsi_norm = (rsi - 50) / 50

        # ADX proxy: rolling std of log_ret / mean(abs_ret)
        window = 14
        roll_std = np.array([
            np.std(log_ret[max(0, i - window):i + 1])
            for i in range(len(log_ret))
        ])
        avg_abs  = np.convolve(abs_ret, np.ones(window) / window, mode="same")
        adx_proxy = np.where(avg_abs > 0, roll_std / avg_abs, 0.0)

        n = min(len(log_ret), len(rsi_norm), len(adx_proxy))
        features = np.column_stack([
            log_ret[-n:],
            abs_ret[-n:],
            rsi_norm[-n:],
            adx_proxy[-n:],
        ])
        # Replace nan/inf
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        return features

    def _label_state(self, model, state: int, features: np.ndarray) -> MarketRegime:
        """
        Assign a regime label to a state by examining mean return and variance.

        hmmlearn returns `means_` and `covars_` with shapes that depend on
        covariance_type and version. Numpy 2.x refuses `float()` on non-0-D
        arrays, so we coerce via `.item()` after squeezing.
        """
        def _scalar(x) -> float:
            return float(np.asarray(x).ravel()[0])

        # Per-state mean return and variance of the first feature (log-return)
        mean_r = _scalar(model.means_[state, 0])
        # covars_ shape is (n_components, n_features) for diag, but some
        # versions return (n_components, n_features, n_features). Index safely.
        covars = np.asarray(model.covars_)
        if covars.ndim == 3:
            var_r_arr = covars[state, 0, 0]
            all_vars  = covars[:, 0, 0]
        else:
            var_r_arr = covars[state, 0] if covars.ndim == 2 else covars[state]
            all_vars  = covars[:, 0]    if covars.ndim == 2 else covars
        var_r = _scalar(var_r_arr)
        global_var = _scalar(np.mean(all_vars))

        if var_r > global_var * 2:
            return MarketRegime.VOLATILE
        if mean_r >  0.0005:
            return MarketRegime.TRENDING_BULL
        if mean_r < -0.0005:
            return MarketRegime.TRENDING_BEAR
        return MarketRegime.RANGING


# ---------------------------------------------------------------------------
# Fast RSI (numpy only)
# ---------------------------------------------------------------------------

def _fast_rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.convolve(gains,  np.ones(period) / period, mode="same")
    avg_loss = np.convolve(losses, np.ones(period) / period, mode="same")

    rs  = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
    rsi = 100 - (100 / (1 + rs))
    return rsi

"""
anomaly_detector.py — Statistical Market Anomaly Detector
==========================================================
Detects unusual market conditions (anomalous price action, volume spikes,
abnormal volatility) using statistical methods — no ML training required.

Detection methods
-----------------
  1. Z-score on rolling returns      — |z| > threshold = anomaly
  2. IQR fence on rolling volume     — outlier volume = anomaly
  3. Bollinger Band width spike      — BB squeeze release detection
  4. Sudden spread widening          — orderbook spread > 5× normal
  5. Price gap detection             — open != previous close by > 0.5%

Output
------
  AnomalyReport dataclass:
    is_anomaly   : bool
    anomaly_type : list[str]   — which detectors fired
    severity     : "LOW" | "MEDIUM" | "HIGH"
    z_score      : float       — return z-score
    volume_z     : float       — volume z-score

Usage
-----
    detector = AnomalyDetector()
    report   = detector.check(candles, spread_pct=0.001)
    if report.is_anomaly:
        logger.warning("Anomaly: %s", report.anomaly_type)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from data.data_normalizer import Candle
from utils.logger import get_logger

logger = get_logger(__name__)

# Detection thresholds
RETURN_Z_THRESHOLD     = 3.0    # |z| of log-return
VOLUME_Z_THRESHOLD     = 3.5    # |z| of volume
BB_WIDTH_SPIKE         = 3.0    # BB width > N× rolling avg
SPREAD_SPIKE           = 5.0    # spread > N× rolling avg
GAP_THRESHOLD          = 0.005  # 0.5% open vs prev close
LOOKBACK               = 50     # bars for rolling statistics


@dataclass
class AnomalyReport:
    is_anomaly:   bool
    anomaly_types: list[str] = field(default_factory=list)
    severity:     str = "NONE"   # NONE | LOW | MEDIUM | HIGH
    z_score:      float = 0.0
    volume_z:     float = 0.0
    bb_width_z:   float = 0.0
    details:      dict = field(default_factory=dict)

    def __repr__(self) -> str:
        if not self.is_anomaly:
            return "<AnomalyReport clean>"
        return (
            f"<AnomalyReport {self.severity} "
            f"types={self.anomaly_types} z={self.z_score:.2f}>"
        )


class AnomalyDetector:
    """
    Statistical anomaly detector for OHLCV candle data.

    Parameters
    ----------
    return_z_thresh : Z-score threshold for return anomalies.
    volume_z_thresh : Z-score threshold for volume anomalies.
    lookback        : Rolling window for statistics.
    """

    def __init__(
        self,
        return_z_thresh: float = RETURN_Z_THRESHOLD,
        volume_z_thresh: float = VOLUME_Z_THRESHOLD,
        lookback:        int   = LOOKBACK,
    ) -> None:
        self._ret_z    = return_z_thresh
        self._vol_z    = volume_z_thresh
        self._lookback = lookback

    # ── Public API ───────────────────────────────────────────────────────

    def check(
        self,
        candles:    list[Candle],
        spread_pct: Optional[float] = None,
    ) -> AnomalyReport:
        """
        Run all anomaly detectors on the current candle and recent history.

        Parameters
        ----------
        candles    : Recent candles (at least lookback+1 recommended).
        spread_pct : Current bid-ask spread as % of price (optional).

        Returns
        -------
        AnomalyReport with is_anomaly, types, severity, and z-scores.
        """
        if len(candles) < 10:
            return AnomalyReport(is_anomaly=False)

        window  = candles[-self._lookback - 1:]
        current = window[-1]
        history = window[:-1]

        anomaly_types: list[str] = []
        details: dict = {}

        # 1. Return z-score
        ret_z = self._return_z_score(window)
        details["return_z"] = round(ret_z, 3)
        if abs(ret_z) >= self._ret_z:
            anomaly_types.append(f"RETURN_SPIKE(z={ret_z:.2f})")

        # 2. Volume z-score
        vol_z = self._volume_z_score(window)
        details["volume_z"] = round(vol_z, 3)
        if abs(vol_z) >= self._vol_z:
            anomaly_types.append(f"VOLUME_SPIKE(z={vol_z:.2f})")

        # 3. Bollinger width spike
        bb_width_z = self._bb_width_z(window)
        details["bb_width_z"] = round(bb_width_z, 3)
        if bb_width_z >= BB_WIDTH_SPIKE:
            anomaly_types.append(f"BB_WIDTH_SPIKE(z={bb_width_z:.2f})")

        # 4. Price gap
        gap_pct = self._gap_pct(window)
        details["gap_pct"] = round(gap_pct, 5)
        if abs(gap_pct) >= GAP_THRESHOLD:
            anomaly_types.append(f"PRICE_GAP({gap_pct*100:.2f}%)")

        # 5. Spread anomaly (if available)
        if spread_pct is not None:
            spread_z = self._spread_z(spread_pct, window)
            details["spread_z"] = round(spread_z, 3)
            if spread_z >= SPREAD_SPIKE:
                anomaly_types.append(f"SPREAD_SPIKE(z={spread_z:.2f})")

        is_anomaly = len(anomaly_types) > 0
        severity   = self._severity(len(anomaly_types), abs(ret_z), abs(vol_z))

        if is_anomaly:
            logger.info(
                "Anomaly detected for %s: %s (severity=%s)",
                current.symbol, anomaly_types, severity,
            )

        return AnomalyReport(
            is_anomaly    = is_anomaly,
            anomaly_types = anomaly_types,
            severity      = severity,
            z_score       = round(ret_z, 3),
            volume_z      = round(vol_z, 3),
            bb_width_z    = round(bb_width_z, 3),
            details       = details,
        )

    def batch_check(
        self,
        candles_by_symbol: dict[str, list[Candle]],
    ) -> dict[str, AnomalyReport]:
        """Run anomaly checks for all symbols."""
        results: dict[str, AnomalyReport] = {}
        for symbol, candles in candles_by_symbol.items():
            results[symbol] = self.check(candles)
        anomalous = sum(1 for r in results.values() if r.is_anomaly)
        logger.debug(
            "Anomaly batch: %d/%d symbols anomalous.",
            anomalous, len(results),
        )
        return results

    # ── Detectors ────────────────────────────────────────────────────────

    def _return_z_score(self, candles: list[Candle]) -> float:
        """Z-score of the latest bar's log-return vs rolling history."""
        closes = np.array([c.close for c in candles], dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            returns = np.diff(np.log(np.where(closes > 0, closes, 1e-10)))
        if len(returns) < 5:
            return 0.0
        hist_ret = returns[:-1]
        last_ret = returns[-1]
        mu  = np.mean(hist_ret)
        std = np.std(hist_ret)
        if std < 1e-10:
            return 0.0
        return float((last_ret - mu) / std)

    def _volume_z_score(self, candles: list[Candle]) -> float:
        """Z-score of latest bar's volume vs rolling history."""
        volumes = np.array([c.volume for c in candles], dtype=float)
        if len(volumes) < 5:
            return 0.0
        hist_vol = volumes[:-1]
        last_vol = volumes[-1]
        mu  = np.mean(hist_vol)
        std = np.std(hist_vol)
        if std < 1e-10:
            return 0.0
        return float((last_vol - mu) / std)

    def _bb_width_z(self, candles: list[Candle]) -> float:
        """Z-score of latest BB width vs rolling BB widths."""
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < 22:
            return 0.0
        period = min(20, len(closes) - 1)
        widths = []
        for i in range(period, len(closes)):
            window = closes[i - period: i]
            sma    = np.mean(window)
            std    = np.std(window)
            if sma > 0:
                widths.append(4 * std / sma)  # 2×std above + 2×std below, normalised
        if len(widths) < 5:
            return 0.0
        hist_w = np.array(widths[:-1])
        last_w = widths[-1]
        mu  = np.mean(hist_w)
        std = np.std(hist_w)
        if std < 1e-10 or mu < 1e-10:
            return 0.0
        return float((last_w - mu) / std)

    @staticmethod
    def _gap_pct(candles: list[Candle]) -> float:
        """
        Detect open-gap: current open vs previous close.
        Returns signed % gap.
        """
        if len(candles) < 2:
            return 0.0
        prev_close   = candles[-2].close
        current_open = candles[-1].open
        if prev_close <= 0:
            return 0.0
        return (current_open - prev_close) / prev_close

    @staticmethod
    def _spread_z(spread_pct: float, candles: list[Candle]) -> float:
        """
        Compare current spread to a normalised baseline.
        Without historical spreads, use a simple % of close heuristic.
        """
        avg_close = np.mean([c.close for c in candles]) if candles else 1.0
        # Typical spread for crypto futures ~0.01% (0.0001)
        typical   = 0.0001
        if typical <= 0:
            return 0.0
        return float(spread_pct / typical)

    @staticmethod
    def _severity(n_types: int, ret_z: float, vol_z: float) -> str:
        if n_types == 0:
            return "NONE"
        max_z = max(ret_z, vol_z)
        if n_types >= 3 or max_z >= 5.0:
            return "HIGH"
        if n_types == 2 or max_z >= 4.0:
            return "MEDIUM"
        return "LOW"

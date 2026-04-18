"""
sentiment_analyzer.py — Crypto Market Sentiment Analyzer
=========================================================
Derives a market sentiment score from on-chain and derivative market
signals available via the Binance Futures API (no external NLP/LLM).

Sentiment inputs
----------------
  1. Funding rate extremes  — high positive = overheated longs (bearish)
  2. Long/Short ratio       — from Binance top-trader data
  3. Open interest trend    — rising OI confirms trend, falling diverges
  4. Price–volume divergence — price up + volume down = weak momentum
  5. Liquidation imbalance  — large long/short liquidations signal reversals

Output
------
  SentimentScore dataclass:
    score      : -100 (extreme fear) to +100 (extreme greed)
    label      : "EXTREME_FEAR" | "FEAR" | "NEUTRAL" | "GREED" | "EXTREME_GREED"
    components : dict of individual sub-scores for transparency

Usage
-----
    analyzer = SentimentAnalyzer()
    result   = analyzer.analyze(
        funding_rate=0.0005,
        long_short_ratio=1.8,
        oi_change_pct=2.5,
        price_change_pct=1.0,
        volume_change_pct=-10.0,
        liq_long_usdt=500_000,
        liq_short_usdt=50_000,
    )
    print(result.label, result.score)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SentimentLabel(str, Enum):
    EXTREME_FEAR  = "EXTREME_FEAR"
    FEAR          = "FEAR"
    NEUTRAL       = "NEUTRAL"
    GREED         = "GREED"
    EXTREME_GREED = "EXTREME_GREED"


@dataclass
class SentimentScore:
    score:      float                   # -100 to +100
    label:      SentimentLabel
    components: dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0

    def is_bullish(self) -> bool:
        return self.score > 20

    def is_bearish(self) -> bool:
        return self.score < -20

    def __repr__(self) -> str:
        return (
            f"<SentimentScore {self.label.value} "
            f"score={self.score:.1f}>"
        )


class SentimentAnalyzer:
    """
    Calculates a composite market sentiment score from derivatives data.

    All individual component scores are normalised to [-100, +100]
    (positive = bullish/greedy, negative = bearish/fearful) before
    being combined as a weighted average.
    """

    # Component weights (must sum to 1.0)
    WEIGHTS = {
        "funding_rate":      0.30,
        "long_short_ratio":  0.25,
        "oi_trend":          0.20,
        "price_volume_div":  0.15,
        "liquidation_imb":   0.10,
    }

    # Funding rate thresholds
    FUNDING_EXTREME = 0.0010     # ±0.10% per 8h
    FUNDING_HIGH    = 0.0005     # ±0.05%

    def __init__(self) -> None:
        self._history: list[SentimentScore] = []

    # ── Public API ───────────────────────────────────────────────────────

    def analyze(
        self,
        funding_rate:       float = 0.0,
        long_short_ratio:   Optional[float] = None,  # longs / shorts
        oi_change_pct:      float = 0.0,
        price_change_pct:   float = 0.0,
        volume_change_pct:  float = 0.0,
        liq_long_usdt:      float = 0.0,
        liq_short_usdt:     float = 0.0,
    ) -> SentimentScore:
        """
        Compute composite sentiment score from available market data.

        Parameters
        ----------
        funding_rate      : Current 8h funding rate (e.g. 0.0003 = +0.03%).
        long_short_ratio  : Ratio of long to short accounts (e.g. 1.8).
        oi_change_pct     : % change in open interest over last period.
        price_change_pct  : % price change over last period.
        volume_change_pct : % volume change over last period.
        liq_long_usdt     : Value of long liquidations in window (USDT).
        liq_short_usdt    : Value of short liquidations in window (USDT).
        """
        components: dict[str, float] = {}

        # 1. Funding rate component
        components["funding_rate"] = self._score_funding(funding_rate)

        # 2. Long/short ratio component
        if long_short_ratio is not None:
            components["long_short_ratio"] = self._score_ls_ratio(long_short_ratio)
        else:
            components["long_short_ratio"] = 0.0

        # 3. Open interest trend
        components["oi_trend"] = self._score_oi_trend(oi_change_pct, price_change_pct)

        # 4. Price-volume divergence
        components["price_volume_div"] = self._score_price_volume(
            price_change_pct, volume_change_pct
        )

        # 5. Liquidation imbalance
        components["liquidation_imb"] = self._score_liquidations(
            liq_long_usdt, liq_short_usdt
        )

        # Weighted average
        total_weight = sum(self.WEIGHTS.values())
        score = sum(
            components[k] * self.WEIGHTS.get(k, 0.0)
            for k in components
        ) / total_weight

        score = max(-100.0, min(100.0, score))
        label = self._label(score)

        result = SentimentScore(
            score      = round(score, 2),
            label      = label,
            components = {k: round(v, 2) for k, v in components.items()},
        )
        self._history.append(result)
        if len(self._history) > 100:
            self._history.pop(0)

        logger.debug(
            "Sentiment: %s score=%.1f components=%s",
            label.value, score, components,
        )
        return result

    # ── Component scorers ────────────────────────────────────────────────

    def _score_funding(self, rate: float) -> float:
        """
        Funding > 0 = longs pay shorts = crowded longs = bearish signal.
        Returns -100 (extreme greed/crowded longs) to +100 (short squeeze zone).
        """
        if abs(rate) < 0.0001:
            return 0.0
        # High positive funding = bearish sentiment
        magnitude = min(abs(rate) / self.FUNDING_EXTREME, 1.0)
        direction = -1 if rate > 0 else 1
        return direction * magnitude * 100

    def _score_ls_ratio(self, ratio: float) -> float:
        """
        Ratio > 1.5 = crowded longs = bearish contrarian.
        Ratio < 0.7 = crowded shorts = bullish contrarian.
        Returns -100 (extremely crowded longs) to +100 (crowded shorts).
        """
        # Neutral zone 0.9 – 1.1
        if 0.9 <= ratio <= 1.1:
            return 0.0
        if ratio > 1.0:
            # Longs dominate — contrarian bearish
            excess = min((ratio - 1.0) / 1.0, 1.0)
            return -excess * 100
        else:
            # Shorts dominate — contrarian bullish
            deficit = min((1.0 - ratio) / 0.5, 1.0)
            return deficit * 100

    def _score_oi_trend(self, oi_change_pct: float, price_change_pct: float) -> float:
        """
        Rising OI + rising price = bullish confirmation.
        Rising OI + falling price = bearish confirmation.
        Falling OI = trend weakening (slight opposing signal).
        """
        if abs(oi_change_pct) < 0.5:
            return 0.0

        if oi_change_pct > 0 and price_change_pct > 0:
            return min(oi_change_pct * 10, 100.0)     # bullish
        elif oi_change_pct > 0 and price_change_pct < 0:
            return -min(oi_change_pct * 10, 100.0)    # bearish
        elif oi_change_pct < 0:
            # Declining OI = position unwinding
            return price_change_pct * 5                # weak directional
        return 0.0

    def _score_price_volume(self, price_pct: float, volume_pct: float) -> float:
        """
        Price up + volume up = healthy bullish.
        Price up + volume down = weak / divergence.
        """
        if abs(price_pct) < 0.1:
            return 0.0
        if price_pct > 0 and volume_pct > 0:
            return min((price_pct + volume_pct / 10), 50.0)
        if price_pct > 0 and volume_pct < 0:
            return -min(abs(volume_pct) / 20, 30.0)   # divergence = bearish
        if price_pct < 0 and volume_pct > 0:
            return -min(abs(price_pct) * 5, 50.0)     # bearish with volume
        return 0.0

    def _score_liquidations(self, liq_long: float, liq_short: float) -> float:
        """
        Large long liquidations = selling pressure = bearish aftermath.
        Large short liquidations = short squeeze = bullish aftermath.
        """
        total = liq_long + liq_short
        if total < 100_000:
            return 0.0
        ratio = liq_long / total if total > 0 else 0.5
        # Long liqs > 70% = contrarian bullish (selling exhaustion)
        if ratio > 0.7:
            return min((ratio - 0.5) * 200, 100.0)
        # Short liqs > 70% = contrarian bearish (short squeeze exhaustion)
        if ratio < 0.3:
            return -min((0.5 - ratio) * 200, 100.0)
        return 0.0

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _label(score: float) -> SentimentLabel:
        if score >= 60:   return SentimentLabel.EXTREME_GREED
        if score >= 20:   return SentimentLabel.GREED
        if score <= -60:  return SentimentLabel.EXTREME_FEAR
        if score <= -20:  return SentimentLabel.FEAR
        return SentimentLabel.NEUTRAL

    @property
    def recent_history(self) -> list[SentimentScore]:
        return list(self._history[-10:])

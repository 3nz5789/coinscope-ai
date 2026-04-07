"""
CoinScopeAI Phase 2 — Funding Alpha Generator

Produces alpha signals from funding rate data:
  - Cross-exchange funding divergence
  - Predicted funding extremes
  - Funding rate mean-reversion signals
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

from services.market_data.alpha.base import BaseAlphaGenerator
from services.market_data.models import (
    AlphaGeneratorConfig,
    AlphaSignal,
    FundingRate,
    FundingSnapshot,
    PredictedFunding,
    SignalDirection,
)


class FundingAlphaGenerator(BaseAlphaGenerator):
    """
    Stateless generator that analyses funding rate data to produce
    alpha signals.

    Accepts:
      - ``FundingSnapshot`` (cross-exchange current rates)
      - Historical ``FundingRate`` sequences
      - ``PredictedFunding`` lists

    Returns a list of ``AlphaSignal`` objects.
    """

    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        super().__init__(config)

    def generate(
        self,
        symbol: str,
        snapshot: Optional[FundingSnapshot] = None,
        history: Optional[Sequence[FundingRate]] = None,
        predicted: Optional[List[PredictedFunding]] = None,
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        now = time.time()

        if snapshot:
            signals.extend(self._divergence_signals(symbol, snapshot, now))

        if history and len(history) >= self.config.min_data_points:
            signals.extend(self._mean_reversion_signals(symbol, history, now))

        if predicted:
            signals.extend(self._predicted_extreme_signals(symbol, predicted, now))

        return signals

    # -- cross-exchange divergence -------------------------------------------

    def _divergence_signals(
        self, symbol: str, snapshot: FundingSnapshot, ts: float
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        if len(snapshot.rates) < 2:
            return signals

        divergence = snapshot.max_divergence
        rates_list = list(snapshot.rates.values())
        z = self.z_score(divergence, rates_list) if len(rates_list) >= 2 else 0.0

        # Identify which exchange is the outlier
        max_ex = max(snapshot.rates, key=snapshot.rates.get)  # type: ignore
        min_ex = min(snapshot.rates, key=snapshot.rates.get)  # type: ignore

        signals.append(
            AlphaSignal(
                signal_name="funding_cross_exchange_divergence",
                symbol=symbol,
                value=divergence,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=self.direction_from_value(
                    snapshot.mean_rate, threshold=0.0001
                ),
                metadata={
                    "max_exchange": max_ex,
                    "max_rate": snapshot.rates[max_ex],
                    "min_exchange": min_ex,
                    "min_rate": snapshot.rates[min_ex],
                    "mean_rate": snapshot.mean_rate,
                    "num_exchanges": len(snapshot.rates),
                },
            )
        )
        return signals

    # -- mean reversion ------------------------------------------------------

    def _mean_reversion_signals(
        self, symbol: str, history: Sequence[FundingRate], ts: float
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        rates = [fr.rate for fr in history]
        lookback = min(self.config.lookback_periods, len(rates))
        recent = rates[-lookback:]
        current = rates[-1]

        z = self.z_score(current, recent)
        mean_rate = self.mean(recent)

        # Mean reversion: extreme funding tends to revert
        if abs(z) >= self.config.z_score_threshold:
            # If funding is extremely positive, expect bearish reversion
            # If funding is extremely negative, expect bullish reversion
            direction = (
                SignalDirection.BEARISH if z > 0 else SignalDirection.BULLISH
            )
            signals.append(
                AlphaSignal(
                    signal_name="funding_mean_reversion",
                    symbol=symbol,
                    value=current,
                    z_score=z,
                    timestamp=ts,
                    confidence=self.confidence_from_z(z),
                    direction=direction,
                    metadata={
                        "mean_rate": mean_rate,
                        "lookback": lookback,
                        "threshold": self.config.z_score_threshold,
                    },
                )
            )

        # Always emit a funding z-score signal for downstream consumers
        signals.append(
            AlphaSignal(
                signal_name="funding_z_score",
                symbol=symbol,
                value=current,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=self.direction_from_value(current, threshold=0.0001),
                metadata={"mean_rate": mean_rate, "lookback": lookback},
            )
        )
        return signals

    # -- predicted funding extremes ------------------------------------------

    def _predicted_extreme_signals(
        self, symbol: str, predicted: List[PredictedFunding], ts: float
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        if not predicted:
            return signals

        rates = [p.predicted_rate for p in predicted]
        mean_pred = self.mean(rates)
        max_pred = max(predicted, key=lambda p: abs(p.predicted_rate))

        z = self.z_score(max_pred.predicted_rate, rates) if len(rates) >= 2 else 0.0

        signals.append(
            AlphaSignal(
                signal_name="funding_predicted_extreme",
                symbol=symbol,
                value=max_pred.predicted_rate,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=self.direction_from_value(
                    max_pred.predicted_rate, threshold=0.0001
                ),
                metadata={
                    "venue": max_pred.venue,
                    "mean_predicted": mean_pred,
                    "all_venues": {p.venue: p.predicted_rate for p in predicted},
                },
            )
        )
        return signals

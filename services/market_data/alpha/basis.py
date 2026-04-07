"""
CoinScopeAI Phase 2 — Basis Alpha Generator

Produces alpha signals from futures basis / premium data:
  - Futures premium / discount extremes
  - Basis convergence / divergence
  - Term structure analysis (when multiple expiries available)
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Sequence

from services.market_data.alpha.base import BaseAlphaGenerator
from services.market_data.models import (
    AggregatedBasis,
    AlphaGeneratorConfig,
    AlphaSignal,
    BasisData,
    SignalDirection,
)


class BasisAlphaGenerator(BaseAlphaGenerator):
    """
    Stateless generator that analyses futures basis data to produce
    alpha signals.

    Accepts:
      - A sequence of ``AggregatedBasis`` snapshots (time-ordered)
      - Or a sequence of raw ``BasisData`` objects
    """

    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        super().__init__(config)

    def generate(
        self,
        symbol: str,
        basis_snapshots: Optional[Sequence[AggregatedBasis]] = None,
        basis_history: Optional[Sequence[BasisData]] = None,
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        now = time.time()

        if basis_snapshots and len(basis_snapshots) >= self.config.min_data_points:
            signals.extend(self._premium_extreme_signals(symbol, basis_snapshots, now))
            signals.extend(self._convergence_signals(symbol, basis_snapshots, now))

        if basis_history and len(basis_history) >= self.config.min_data_points:
            signals.extend(self._history_signals(symbol, basis_history, now))

        return signals

    # -- premium / discount extremes -----------------------------------------

    def _premium_extreme_signals(
        self,
        symbol: str,
        snapshots: Sequence[AggregatedBasis],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect when basis is at extreme premium or discount."""
        signals: List[AlphaSignal] = []
        basis_pcts = [s.mean_basis_pct for s in snapshots]
        lookback = min(self.config.lookback_periods, len(basis_pcts))
        recent = basis_pcts[-lookback:]
        current = basis_pcts[-1]

        z = self.z_score(current, recent)

        if abs(z) >= self.config.z_score_threshold:
            # Extreme premium → bearish (market overheated)
            # Extreme discount → bullish (market oversold)
            direction = (
                SignalDirection.BEARISH if z > 0 else SignalDirection.BULLISH
            )
            signals.append(
                AlphaSignal(
                    signal_name="basis_premium_extreme",
                    symbol=symbol,
                    value=current,
                    z_score=z,
                    timestamp=ts,
                    confidence=self.confidence_from_z(z),
                    direction=direction,
                    metadata={
                        "mean_basis_pct": self.mean(recent),
                        "lookback": lookback,
                        "annualized_est": current * 365.25 * 3,
                    },
                )
            )

        # Always emit the current basis z-score
        signals.append(
            AlphaSignal(
                signal_name="basis_z_score",
                symbol=symbol,
                value=current,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=self.direction_from_value(current, threshold=0.01),
                metadata={
                    "mean_basis_pct": self.mean(recent),
                    "lookback": lookback,
                },
            )
        )
        return signals

    # -- convergence / divergence --------------------------------------------

    def _convergence_signals(
        self,
        symbol: str,
        snapshots: Sequence[AggregatedBasis],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect basis convergence (narrowing) or divergence (widening)."""
        signals: List[AlphaSignal] = []
        if len(snapshots) < 3:
            return signals

        basis_pcts = [s.mean_basis_pct for s in snapshots]
        lookback = min(self.config.lookback_periods, len(basis_pcts))
        recent = basis_pcts[-lookback:]

        # Rate of change of basis
        roc_values = [
            self.rate_of_change(recent[i], recent[i - 1])
            for i in range(1, len(recent))
            if recent[i - 1] != 0
        ]

        if not roc_values:
            return signals

        current_roc = roc_values[-1]
        z = self.z_score(current_roc, roc_values) if len(roc_values) >= 2 else 0.0

        # Converging basis (narrowing) = positions unwinding
        # Diverging basis (widening) = new positioning
        if current_roc < -0.1:
            direction = SignalDirection.NEUTRAL  # convergence
            label = "converging"
        elif current_roc > 0.1:
            direction = SignalDirection.NEUTRAL  # divergence
            label = "diverging"
        else:
            direction = SignalDirection.NEUTRAL
            label = "stable"

        signals.append(
            AlphaSignal(
                signal_name="basis_convergence",
                symbol=symbol,
                value=current_roc,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=direction,
                metadata={
                    "basis_roc": current_roc,
                    "label": label,
                    "lookback": lookback,
                },
            )
        )
        return signals

    # -- history-based signals -----------------------------------------------

    def _history_signals(
        self,
        symbol: str,
        history: Sequence[BasisData],
        ts: float,
    ) -> List[AlphaSignal]:
        """Produce signals from a raw BasisData time series."""
        signals: List[AlphaSignal] = []
        basis_pcts = [b.basis_pct for b in history]
        lookback = min(self.config.lookback_periods, len(basis_pcts))
        recent = basis_pcts[-lookback:]
        current = basis_pcts[-1]

        z = self.z_score(current, recent)

        signals.append(
            AlphaSignal(
                signal_name="basis_history_z",
                symbol=symbol,
                value=current,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=self.direction_from_value(z, threshold=1.5),
                metadata={
                    "exchange": history[-1].exchange.value,
                    "spot_price": history[-1].spot_price,
                    "futures_price": history[-1].futures_price,
                    "lookback": lookback,
                },
            )
        )
        return signals

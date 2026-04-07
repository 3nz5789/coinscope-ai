"""
CoinScopeAI Phase 2 — Liquidation Alpha Generator

Produces alpha signals from liquidation data:
  - Liquidation cascade detection (sudden spike in liquidation volume)
  - Liquidation cluster analysis (concentration in one direction)
  - Long/short liquidation ratio
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence

from services.market_data.alpha.base import BaseAlphaGenerator
from services.market_data.models import (
    AlphaGeneratorConfig,
    AlphaSignal,
    LiquidationSnapshot,
    SignalDirection,
)


class LiquidationAlphaGenerator(BaseAlphaGenerator):
    """
    Stateless generator that analyses liquidation data to produce
    alpha signals.

    Accepts a sequence of ``LiquidationSnapshot`` objects (time-ordered,
    oldest first) and produces signals based on the latest snapshot
    relative to the historical distribution.
    """

    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        super().__init__(config)

    def generate(
        self,
        symbol: str,
        snapshots: Sequence[LiquidationSnapshot],
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        if not snapshots:
            return signals

        now = time.time()
        latest = snapshots[-1]

        if len(snapshots) >= self.config.min_data_points:
            signals.extend(self._cascade_signals(symbol, snapshots, now))
            signals.extend(self._cluster_signals(symbol, snapshots, now))

        signals.extend(self._ratio_signals(symbol, latest, now))

        return signals

    # -- cascade detection ---------------------------------------------------

    def _cascade_signals(
        self,
        symbol: str,
        snapshots: Sequence[LiquidationSnapshot],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect sudden spikes in total liquidation volume."""
        signals: List[AlphaSignal] = []
        totals = [s.total_usd for s in snapshots]
        lookback = min(self.config.lookback_periods, len(totals))
        recent = totals[-lookback:]
        current = totals[-1]

        z = self.z_score(current, recent)

        if abs(z) >= self.config.z_score_threshold:
            # Large liquidation cascade — market stress event
            signals.append(
                AlphaSignal(
                    signal_name="liquidation_cascade",
                    symbol=symbol,
                    value=current,
                    z_score=z,
                    timestamp=ts,
                    confidence=self.confidence_from_z(z),
                    direction=SignalDirection.NEUTRAL,  # cascades are regime signals
                    metadata={
                        "mean_total": self.mean(recent),
                        "std_total": self.std(recent),
                        "lookback": lookback,
                        "window_seconds": snapshots[-1].window_seconds,
                    },
                )
            )
        return signals

    # -- cluster analysis ----------------------------------------------------

    def _cluster_signals(
        self,
        symbol: str,
        snapshots: Sequence[LiquidationSnapshot],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect concentration of liquidations on one side."""
        signals: List[AlphaSignal] = []
        latest = snapshots[-1]

        if latest.total_usd == 0:
            return signals

        long_pct = latest.long_liquidations_usd / latest.total_usd
        short_pct = latest.short_liquidations_usd / latest.total_usd

        # Compute historical long-percentage for z-score
        long_pcts = []
        for s in snapshots:
            if s.total_usd > 0:
                long_pcts.append(s.long_liquidations_usd / s.total_usd)

        z = self.z_score(long_pct, long_pcts) if len(long_pcts) >= 2 else 0.0

        # If longs are being liquidated disproportionately → bearish
        # If shorts are being liquidated disproportionately → bullish
        if long_pct > 0.7:
            direction = SignalDirection.BEARISH
        elif short_pct > 0.7:
            direction = SignalDirection.BULLISH
        else:
            direction = SignalDirection.NEUTRAL

        signals.append(
            AlphaSignal(
                signal_name="liquidation_cluster",
                symbol=symbol,
                value=long_pct - short_pct,  # positive = more longs liquidated
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=direction,
                metadata={
                    "long_pct": long_pct,
                    "short_pct": short_pct,
                    "total_usd": latest.total_usd,
                },
            )
        )
        return signals

    # -- long/short ratio ----------------------------------------------------

    def _ratio_signals(
        self,
        symbol: str,
        snapshot: LiquidationSnapshot,
        ts: float,
    ) -> List[AlphaSignal]:
        """Emit the long/short liquidation ratio as a signal."""
        signals: List[AlphaSignal] = []
        ratio = snapshot.long_short_ratio

        if ratio is not None:
            # ratio > 1 means more longs liquidated → bearish pressure
            log_ratio = 0.0
            if ratio > 0:
                import math
                log_ratio = math.log(ratio)

            direction = self.direction_from_value(log_ratio, threshold=0.5)

            signals.append(
                AlphaSignal(
                    signal_name="liquidation_long_short_ratio",
                    symbol=symbol,
                    value=ratio,
                    z_score=log_ratio,  # log-ratio as proxy z-score
                    timestamp=ts,
                    confidence=min(abs(log_ratio) / 2.0, 1.0),
                    direction=direction,
                    metadata={
                        "long_usd": snapshot.long_liquidations_usd,
                        "short_usd": snapshot.short_liquidations_usd,
                    },
                )
            )
        return signals

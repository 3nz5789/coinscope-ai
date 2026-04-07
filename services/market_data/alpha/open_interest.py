"""
CoinScopeAI Phase 2 — Open Interest Alpha Generator

Produces alpha signals from open interest data:
  - Cross-exchange OI divergence
  - OI expansion / contraction rate
  - OI vs price divergence
"""

from __future__ import annotations

import time
from typing import List, Optional, Sequence, Tuple

from services.market_data.alpha.base import BaseAlphaGenerator
from services.market_data.models import (
    AggregatedOI,
    AlphaGeneratorConfig,
    AlphaSignal,
    SignalDirection,
)


class OIAlphaGenerator(BaseAlphaGenerator):
    """
    Stateless generator that analyses open interest data to produce
    alpha signals.

    Accepts:
      - A sequence of ``AggregatedOI`` snapshots (time-ordered)
      - Optional price series aligned with the OI snapshots
    """

    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        super().__init__(config)

    def generate(
        self,
        symbol: str,
        oi_snapshots: Sequence[AggregatedOI],
        prices: Optional[Sequence[float]] = None,
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        if not oi_snapshots:
            return signals

        now = time.time()

        if len(oi_snapshots) >= 2:
            signals.extend(self._divergence_signals(symbol, oi_snapshots, now))
            signals.extend(self._expansion_signals(symbol, oi_snapshots, now))

        if prices and len(prices) == len(oi_snapshots) and len(prices) >= self.config.min_data_points:
            signals.extend(
                self._price_divergence_signals(symbol, oi_snapshots, prices, now)
            )

        return signals

    # -- cross-exchange divergence -------------------------------------------

    def _divergence_signals(
        self,
        symbol: str,
        snapshots: Sequence[AggregatedOI],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect when one exchange's OI deviates from the group."""
        signals: List[AlphaSignal] = []
        latest = snapshots[-1]

        if len(latest.by_exchange) < 2:
            return signals

        total = latest.total_oi
        if total == 0:
            return signals

        # Compute share per exchange
        shares = {ex: oi / total for ex, oi in latest.by_exchange.items()}
        share_values = list(shares.values())

        # Find the exchange with the most extreme share
        max_ex = max(shares, key=shares.get)  # type: ignore
        min_ex = min(shares, key=shares.get)  # type: ignore
        divergence = shares[max_ex] - shares[min_ex]

        z = self.z_score(divergence, share_values) if len(share_values) >= 2 else 0.0

        signals.append(
            AlphaSignal(
                signal_name="oi_cross_exchange_divergence",
                symbol=symbol,
                value=divergence,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=SignalDirection.NEUTRAL,
                metadata={
                    "shares": shares,
                    "total_oi": total,
                    "max_exchange": max_ex,
                    "min_exchange": min_ex,
                },
            )
        )
        return signals

    # -- expansion / contraction rate ----------------------------------------

    def _expansion_signals(
        self,
        symbol: str,
        snapshots: Sequence[AggregatedOI],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect rapid OI expansion or contraction."""
        signals: List[AlphaSignal] = []
        totals = [s.total_oi for s in snapshots]
        lookback = min(self.config.lookback_periods, len(totals))
        recent = totals[-lookback:]

        if len(recent) < 2:
            return signals

        # Rate of change: latest vs previous
        roc = self.rate_of_change(recent[-1], recent[-2])
        roc_history = [
            self.rate_of_change(recent[i], recent[i - 1])
            for i in range(1, len(recent))
        ]
        z = self.z_score(roc, roc_history) if len(roc_history) >= 2 else 0.0

        # Expanding OI with price move = trend confirmation
        # Contracting OI = potential reversal or low conviction
        direction = (
            SignalDirection.BULLISH if roc > 0.05
            else SignalDirection.BEARISH if roc < -0.05
            else SignalDirection.NEUTRAL
        )

        signals.append(
            AlphaSignal(
                signal_name="oi_expansion_rate",
                symbol=symbol,
                value=roc,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=direction,
                metadata={
                    "current_oi": recent[-1],
                    "previous_oi": recent[-2],
                    "lookback": lookback,
                    "mean_roc": self.mean(roc_history),
                },
            )
        )
        return signals

    # -- OI vs price divergence ----------------------------------------------

    def _price_divergence_signals(
        self,
        symbol: str,
        snapshots: Sequence[AggregatedOI],
        prices: Sequence[float],
        ts: float,
    ) -> List[AlphaSignal]:
        """
        Detect divergence between OI and price movements.

        Rising price + falling OI = bearish divergence (short squeeze / weak rally)
        Falling price + rising OI = bearish (new shorts entering)
        Rising price + rising OI = bullish (new longs entering)
        Falling price + falling OI = neutral (positions closing)
        """
        signals: List[AlphaSignal] = []
        lookback = min(self.config.lookback_periods, len(prices))

        oi_vals = [s.total_oi for s in snapshots[-lookback:]]
        px_vals = list(prices[-lookback:])

        if len(oi_vals) < 2 or len(px_vals) < 2:
            return signals

        oi_roc = self.rate_of_change(oi_vals[-1], oi_vals[0])
        px_roc = self.rate_of_change(px_vals[-1], px_vals[0])

        # Divergence metric: sign disagreement weighted by magnitude
        divergence = px_roc - oi_roc  # positive = price up more than OI

        # Classify the divergence
        if px_roc > 0 and oi_roc < 0:
            direction = SignalDirection.BEARISH  # weak rally
            div_type = "price_up_oi_down"
        elif px_roc < 0 and oi_roc > 0:
            direction = SignalDirection.BEARISH  # new shorts
            div_type = "price_down_oi_up"
        elif px_roc > 0 and oi_roc > 0:
            direction = SignalDirection.BULLISH  # healthy trend
            div_type = "price_up_oi_up"
        else:
            direction = SignalDirection.NEUTRAL  # unwinding
            div_type = "price_down_oi_down"

        signals.append(
            AlphaSignal(
                signal_name="oi_price_divergence",
                symbol=symbol,
                value=divergence,
                z_score=divergence * 10,  # scaled proxy
                timestamp=ts,
                confidence=min(abs(divergence) * 5, 1.0),
                direction=direction,
                metadata={
                    "oi_roc": oi_roc,
                    "price_roc": px_roc,
                    "divergence_type": div_type,
                    "lookback": lookback,
                },
            )
        )
        return signals

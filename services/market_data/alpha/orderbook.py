"""
CoinScopeAI Phase 2 — Order Book Alpha Generator

Produces alpha signals from L2 order book data:
  - Book imbalance (bid vs ask depth ratio)
  - Depth-weighted mid price (VWAP-style mid)
  - Liquidity cliff detection (sudden drop in depth at a price level)
"""

from __future__ import annotations

import math
import time
from typing import List, Optional, Sequence

from services.market_data.alpha.base import BaseAlphaGenerator
from services.market_data.models import (
    AlphaGeneratorConfig,
    AlphaSignal,
    L2OrderBook,
    SignalDirection,
)


class OrderBookAlphaGenerator(BaseAlphaGenerator):
    """
    Stateless generator that analyses L2 order book snapshots to produce
    alpha signals.

    Accepts:
      - A single ``L2OrderBook`` snapshot (for instantaneous signals)
      - A sequence of snapshots (for temporal signals)
    """

    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        super().__init__(config)

    def generate(
        self,
        symbol: str,
        book: Optional[L2OrderBook] = None,
        book_history: Optional[Sequence[L2OrderBook]] = None,
    ) -> List[AlphaSignal]:
        signals: List[AlphaSignal] = []
        now = time.time()

        target_book = book
        if target_book is None and book_history:
            target_book = book_history[-1]

        if target_book and target_book.bids and target_book.asks:
            signals.extend(self._imbalance_signals(symbol, target_book, now))
            signals.extend(self._depth_weighted_mid_signals(symbol, target_book, now))
            signals.extend(self._liquidity_cliff_signals(symbol, target_book, now))

        if book_history and len(book_history) >= self.config.min_data_points:
            signals.extend(self._temporal_signals(symbol, book_history, now))

        return signals

    # -- book imbalance ------------------------------------------------------

    def _imbalance_signals(
        self, symbol: str, book: L2OrderBook, ts: float
    ) -> List[AlphaSignal]:
        """
        Compute bid/ask depth imbalance.

        Imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)
        Range: [-1, 1].  Positive = more bids (bullish).
        """
        signals: List[AlphaSignal] = []
        bid_depth = sum(lvl.size for lvl in book.bids)
        ask_depth = sum(lvl.size for lvl in book.asks)
        total = bid_depth + ask_depth

        if total == 0:
            return signals

        imbalance = (bid_depth - ask_depth) / total

        signals.append(
            AlphaSignal(
                signal_name="orderbook_imbalance",
                symbol=symbol,
                value=imbalance,
                z_score=imbalance * 3,  # scaled proxy (imbalance is bounded)
                timestamp=ts,
                confidence=min(abs(imbalance) * 2, 1.0),
                direction=self.direction_from_value(imbalance, threshold=0.15),
                metadata={
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "num_bid_levels": len(book.bids),
                    "num_ask_levels": len(book.asks),
                },
            )
        )
        return signals

    # -- depth-weighted mid price --------------------------------------------

    def _depth_weighted_mid_signals(
        self, symbol: str, book: L2OrderBook, ts: float
    ) -> List[AlphaSignal]:
        """
        Compute depth-weighted mid price and its deviation from simple mid.

        The depth-weighted mid is pulled toward the side with more liquidity.
        """
        signals: List[AlphaSignal] = []
        simple_mid = book.mid_price
        if simple_mid is None:
            return signals

        # Weighted mid using top N levels
        n_levels = min(5, len(book.bids), len(book.asks))
        if n_levels == 0:
            return signals

        bid_weight = sum(book.bids[i].size for i in range(n_levels))
        ask_weight = sum(book.asks[i].size for i in range(n_levels))
        total_weight = bid_weight + ask_weight

        if total_weight == 0:
            return signals

        # Depth-weighted mid: weighted average of best bid and best ask
        weighted_mid = (
            book.best_bid * ask_weight + book.best_ask * bid_weight
        ) / total_weight

        deviation_bps = ((weighted_mid - simple_mid) / simple_mid) * 10_000

        signals.append(
            AlphaSignal(
                signal_name="orderbook_depth_weighted_mid",
                symbol=symbol,
                value=weighted_mid,
                z_score=deviation_bps / 5,  # normalise to ~z-score range
                timestamp=ts,
                confidence=min(abs(deviation_bps) / 10, 1.0),
                direction=self.direction_from_value(deviation_bps, threshold=1.0),
                metadata={
                    "simple_mid": simple_mid,
                    "weighted_mid": weighted_mid,
                    "deviation_bps": deviation_bps,
                    "bid_weight": bid_weight,
                    "ask_weight": ask_weight,
                    "n_levels": n_levels,
                },
            )
        )
        return signals

    # -- liquidity cliff detection -------------------------------------------

    def _liquidity_cliff_signals(
        self, symbol: str, book: L2OrderBook, ts: float
    ) -> List[AlphaSignal]:
        """
        Detect liquidity cliffs — sudden drops in depth at a price level.

        A cliff is defined as a level where the size drops by more than
        a configurable threshold relative to the previous level.
        """
        signals: List[AlphaSignal] = []
        cliff_threshold = self.config.extra.get("cliff_threshold", 0.5)

        for side_name, levels in [("bid", book.bids), ("ask", book.asks)]:
            if len(levels) < 3:
                continue

            sizes = [lvl.size for lvl in levels]
            max_drop = 0.0
            cliff_idx = -1

            for i in range(1, len(sizes)):
                if sizes[i - 1] > 0:
                    drop = (sizes[i - 1] - sizes[i]) / sizes[i - 1]
                    if drop > max_drop:
                        max_drop = drop
                        cliff_idx = i

            if max_drop >= cliff_threshold and cliff_idx >= 0:
                cliff_price = levels[cliff_idx].price
                # Bid cliff = support might break → bearish
                # Ask cliff = resistance might break → bullish
                direction = (
                    SignalDirection.BEARISH
                    if side_name == "bid"
                    else SignalDirection.BULLISH
                )

                signals.append(
                    AlphaSignal(
                        signal_name=f"orderbook_liquidity_cliff_{side_name}",
                        symbol=symbol,
                        value=max_drop,
                        z_score=max_drop * 3,
                        timestamp=ts,
                        confidence=min(max_drop, 1.0),
                        direction=direction,
                        metadata={
                            "side": side_name,
                            "cliff_price": cliff_price,
                            "cliff_level_idx": cliff_idx,
                            "drop_pct": max_drop,
                            "pre_cliff_size": sizes[cliff_idx - 1],
                            "post_cliff_size": sizes[cliff_idx],
                        },
                    )
                )
        return signals

    # -- temporal signals (spread dynamics) ----------------------------------

    def _temporal_signals(
        self,
        symbol: str,
        history: Sequence[L2OrderBook],
        ts: float,
    ) -> List[AlphaSignal]:
        """Detect spread widening / narrowing over time."""
        signals: List[AlphaSignal] = []
        spreads = [b.spread_bps for b in history if b.spread_bps is not None]

        if len(spreads) < self.config.min_data_points:
            return signals

        lookback = min(self.config.lookback_periods, len(spreads))
        recent = spreads[-lookback:]
        current = recent[-1]
        z = self.z_score(current, recent)

        # Widening spread = lower liquidity, potential stress
        signals.append(
            AlphaSignal(
                signal_name="orderbook_spread_z",
                symbol=symbol,
                value=current,
                z_score=z,
                timestamp=ts,
                confidence=self.confidence_from_z(z),
                direction=SignalDirection.NEUTRAL,
                metadata={
                    "spread_bps": current,
                    "mean_spread_bps": self.mean(recent),
                    "lookback": lookback,
                },
            )
        )
        return signals

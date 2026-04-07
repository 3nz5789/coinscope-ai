"""
CoinScopeAI — Spread / Mark-Price Divergence Scanner

Detects:
  1. Intra-exchange divergence: mark price vs. order-book mid price
  2. Cross-exchange divergence: mark price on exchange A vs. exchange B

These divergences can signal:
  - Arbitrage opportunities
  - Liquidation cascades about to trigger
  - Market microstructure stress
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from ..models import (
    EventType,
    Exchange,
    MarkPrice,
    OrderBook,
    ScanSignal,
)
from .base_scanner import BaseScanner, ScannerConfig

logger = logging.getLogger("coinscopeai.scanner.spread_divergence")

DEFAULT_THRESHOLDS = {
    "mark_mid_divergence_bps": 10.0,     # basis points
    "cross_exchange_divergence_bps": 15.0,
}


class SpreadDivergenceScanner(BaseScanner):
    NAME = "spread_divergence"

    def __init__(self, config: ScannerConfig, event_bus) -> None:
        merged = {**DEFAULT_THRESHOLDS, **config.thresholds}
        config.thresholds = merged
        super().__init__(config, event_bus)

    def _subscribed_event_types(self) -> List[EventType]:
        return [EventType.MARK_PRICE, EventType.ORDER_BOOK]

    async def evaluate(self) -> List[ScanSignal]:
        signals: List[ScanSignal] = []
        t = self.config.thresholds

        for symbol in self.config.symbols:
            mark_prices: Dict[Exchange, float] = {}
            mid_prices: Dict[Exchange, float] = {}

            for exchange in self.config.exchanges:
                # Latest mark price
                mp_event = self._get_latest(exchange, symbol, EventType.MARK_PRICE)
                if mp_event and isinstance(mp_event.data, MarkPrice):
                    mark_prices[exchange] = mp_event.data.mark_price

                # Latest order book mid
                ob_event = self._get_latest(exchange, symbol, EventType.ORDER_BOOK)
                if ob_event and isinstance(ob_event.data, OrderBook):
                    mid = ob_event.data.mid_price
                    if mid:
                        mid_prices[exchange] = mid

            # --- Intra-exchange: mark vs mid ---
            for exchange in self.config.exchanges:
                mp = mark_prices.get(exchange)
                mid = mid_prices.get(exchange)
                if mp and mid and mid > 0:
                    div_bps = abs(mp - mid) / mid * 10_000
                    if div_bps >= t["mark_mid_divergence_bps"]:
                        strength = min(1.0, div_bps / (t["mark_mid_divergence_bps"] * 5))
                        signals.append(ScanSignal(
                            scanner_name=self.NAME,
                            exchange=exchange,
                            symbol=symbol,
                            signal_type="mark_mid_divergence",
                            strength=strength,
                            details={
                                "mark_price": mp,
                                "mid_price": mid,
                                "divergence_bps": round(div_bps, 2),
                                "direction": "mark_above" if mp > mid else "mark_below",
                            },
                        ))

            # --- Cross-exchange mark price divergence ---
            if len(mark_prices) >= 2:
                exchanges_list = list(mark_prices.keys())
                for i in range(len(exchanges_list)):
                    for j in range(i + 1, len(exchanges_list)):
                        ex_a, ex_b = exchanges_list[i], exchanges_list[j]
                        pa, pb = mark_prices[ex_a], mark_prices[ex_b]
                        ref = (pa + pb) / 2.0
                        if ref > 0:
                            div_bps = abs(pa - pb) / ref * 10_000
                            if div_bps >= t["cross_exchange_divergence_bps"]:
                                higher_ex = ex_a if pa > pb else ex_b
                                strength = min(1.0, div_bps / (t["cross_exchange_divergence_bps"] * 5))
                                signals.append(ScanSignal(
                                    scanner_name=self.NAME,
                                    exchange=higher_ex,
                                    symbol=symbol,
                                    signal_type="cross_exchange_mark_divergence",
                                    strength=strength,
                                    details={
                                        "exchange_a": ex_a.value,
                                        "price_a": pa,
                                        "exchange_b": ex_b.value,
                                        "price_b": pb,
                                        "divergence_bps": round(div_bps, 2),
                                    },
                                ))

        await self.emit_signals(signals)
        return signals

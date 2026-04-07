"""
CoinScopeAI — Liquidity Deterioration Scanner

Detects real-time thinning of order book liquidity that precedes
large price moves or flash crashes.

Metrics monitored:
  1. Spread widening: bid-ask spread exceeding N× its rolling average
  2. Depth thinning: top-of-book quantity dropping below threshold
  3. Trade imbalance: heavy one-sided aggression (buy vs sell volume ratio)
"""

from __future__ import annotations

import logging
import time
from typing import List

from ..models import (
    EventType,
    Exchange,
    OrderBook,
    ScanSignal,
    Trade,
    Side,
)
from .base_scanner import BaseScanner, ScannerConfig

logger = logging.getLogger("coinscopeai.scanner.liquidity_deterioration")

DEFAULT_THRESHOLDS = {
    "spread_multiplier": 3.0,         # current spread > N× rolling avg
    "min_spread_samples": 10,
    "depth_thin_pct": 50.0,           # top-of-book qty dropped by this %
    "trade_imbalance_ratio": 3.0,     # buy_vol / sell_vol (or inverse) threshold
    "min_trade_samples": 20,
}


class LiquidityDeteriorationScanner(BaseScanner):
    NAME = "liquidity_deterioration"

    def __init__(self, config: ScannerConfig, event_bus) -> None:
        merged = {**DEFAULT_THRESHOLDS, **config.thresholds}
        config.thresholds = merged
        super().__init__(config, event_bus)

    def _subscribed_event_types(self) -> List[EventType]:
        return [EventType.ORDER_BOOK, EventType.TRADE]

    async def evaluate(self) -> List[ScanSignal]:
        signals: List[ScanSignal] = []
        t = self.config.thresholds

        for exchange in self.config.exchanges:
            for symbol in self.config.symbols:
                # ---- Spread analysis ----
                ob_window = self._get_window(exchange, symbol, EventType.ORDER_BOOK)
                spreads = []
                for ev in ob_window:
                    if isinstance(ev.data, OrderBook) and ev.data.spread is not None:
                        spreads.append(ev.data.spread)

                if len(spreads) >= t["min_spread_samples"]:
                    avg_spread = sum(spreads[:-1]) / len(spreads[:-1])
                    current_spread = spreads[-1]
                    if avg_spread > 0 and current_spread > avg_spread * t["spread_multiplier"]:
                        strength = min(1.0, (current_spread / avg_spread) / (t["spread_multiplier"] * 3))
                        signals.append(ScanSignal(
                            scanner_name=self.NAME,
                            exchange=exchange,
                            symbol=symbol,
                            signal_type="spread_widening",
                            strength=strength,
                            details={
                                "current_spread": current_spread,
                                "avg_spread": round(avg_spread, 8),
                                "multiplier": round(current_spread / avg_spread, 2),
                                "threshold_multiplier": t["spread_multiplier"],
                            },
                        ))

                # ---- Depth thinning ----
                if len(ob_window) >= 2:
                    first_ob = ob_window[0].data
                    last_ob = ob_window[-1].data
                    if isinstance(first_ob, OrderBook) and isinstance(last_ob, OrderBook):
                        first_bid_qty = first_ob.best_bid.quantity if first_ob.best_bid else 0
                        last_bid_qty = last_ob.best_bid.quantity if last_ob.best_bid else 0
                        first_ask_qty = first_ob.best_ask.quantity if first_ob.best_ask else 0
                        last_ask_qty = last_ob.best_ask.quantity if last_ob.best_ask else 0

                        for side_label, first_q, last_q in [("bid", first_bid_qty, last_bid_qty), ("ask", first_ask_qty, last_ask_qty)]:
                            if first_q > 0:
                                drop_pct = (first_q - last_q) / first_q * 100
                                if drop_pct >= t["depth_thin_pct"]:
                                    strength = min(1.0, drop_pct / 100.0)
                                    signals.append(ScanSignal(
                                        scanner_name=self.NAME,
                                        exchange=exchange,
                                        symbol=symbol,
                                        signal_type=f"depth_thinning_{side_label}",
                                        strength=strength,
                                        details={
                                            "side": side_label,
                                            "initial_qty": first_q,
                                            "current_qty": last_q,
                                            "drop_pct": round(drop_pct, 2),
                                        },
                                    ))

                # ---- Trade imbalance ----
                trade_window = self._get_window(exchange, symbol, EventType.TRADE)
                if len(trade_window) >= t["min_trade_samples"]:
                    buy_vol = sum(
                        ev.data.quantity for ev in trade_window
                        if isinstance(ev.data, Trade) and ev.data.side == Side.BUY
                    )
                    sell_vol = sum(
                        ev.data.quantity for ev in trade_window
                        if isinstance(ev.data, Trade) and ev.data.side == Side.SELL
                    )
                    if sell_vol > 0 and buy_vol / sell_vol >= t["trade_imbalance_ratio"]:
                        strength = min(1.0, (buy_vol / sell_vol) / (t["trade_imbalance_ratio"] * 3))
                        signals.append(ScanSignal(
                            scanner_name=self.NAME,
                            exchange=exchange,
                            symbol=symbol,
                            signal_type="trade_imbalance_buy",
                            strength=strength,
                            details={
                                "buy_volume": buy_vol,
                                "sell_volume": sell_vol,
                                "ratio": round(buy_vol / sell_vol, 2),
                            },
                        ))
                    elif buy_vol > 0 and sell_vol / buy_vol >= t["trade_imbalance_ratio"]:
                        strength = min(1.0, (sell_vol / buy_vol) / (t["trade_imbalance_ratio"] * 3))
                        signals.append(ScanSignal(
                            scanner_name=self.NAME,
                            exchange=exchange,
                            symbol=symbol,
                            signal_type="trade_imbalance_sell",
                            strength=strength,
                            details={
                                "buy_volume": buy_vol,
                                "sell_volume": sell_vol,
                                "ratio": round(sell_vol / buy_vol, 2),
                            },
                        ))

        await self.emit_signals(signals)
        return signals

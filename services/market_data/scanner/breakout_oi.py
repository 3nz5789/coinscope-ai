"""
CoinScopeAI — Breakout + OI Expansion Scanner

Detects price breakouts accompanied by rising open interest, which
signals genuine directional conviction rather than a stop-hunt.

Logic:
  1. Track rolling high/low of mark price over the window.
  2. Detect breakout when price exceeds the rolling high (or breaks below low).
  3. Confirm with OI expansion: latest OI > OI at window start by threshold %.
  4. Strength = normalized combination of price move % and OI change %.
"""

from __future__ import annotations

import logging
import time
from typing import List

from ..models import (
    EventType,
    Exchange,
    MarkPrice,
    OpenInterest,
    ScanSignal,
)
from .base_scanner import BaseScanner, ScannerConfig

logger = logging.getLogger("coinscopeai.scanner.breakout_oi")

DEFAULT_THRESHOLDS = {
    "price_breakout_pct": 0.5,      # % move above rolling high
    "oi_expansion_pct": 2.0,        # % OI increase over window
    "min_data_points": 5,           # minimum data points needed
}


class BreakoutOIScanner(BaseScanner):
    NAME = "breakout_oi"

    def __init__(self, config: ScannerConfig, event_bus) -> None:
        merged = {**DEFAULT_THRESHOLDS, **config.thresholds}
        config.thresholds = merged
        super().__init__(config, event_bus)

    def _subscribed_event_types(self) -> List[EventType]:
        return [EventType.MARK_PRICE, EventType.OPEN_INTEREST]

    async def evaluate(self) -> List[ScanSignal]:
        signals: List[ScanSignal] = []
        t = self.config.thresholds

        for exchange in self.config.exchanges:
            for symbol in self.config.symbols:
                mp_window = self._get_window(exchange, symbol, EventType.MARK_PRICE)
                oi_window = self._get_window(exchange, symbol, EventType.OPEN_INTEREST)

                if len(mp_window) < t["min_data_points"] or len(oi_window) < 2:
                    continue

                prices = [e.data.mark_price for e in mp_window if isinstance(e.data, MarkPrice)]
                if not prices:
                    continue

                rolling_high = max(prices[:-1]) if len(prices) > 1 else prices[0]
                rolling_low = min(prices[:-1]) if len(prices) > 1 else prices[0]
                current_price = prices[-1]

                # OI change
                oi_values = [e.data.open_interest for e in oi_window if isinstance(e.data, OpenInterest)]
                if len(oi_values) < 2:
                    continue
                oi_start = oi_values[0]
                oi_end = oi_values[-1]
                oi_change_pct = ((oi_end - oi_start) / oi_start * 100) if oi_start > 0 else 0

                # Breakout detection
                breakout_up = rolling_high > 0 and ((current_price - rolling_high) / rolling_high * 100) >= t["price_breakout_pct"]
                breakout_down = rolling_low > 0 and ((rolling_low - current_price) / rolling_low * 100) >= t["price_breakout_pct"]

                oi_expanding = oi_change_pct >= t["oi_expansion_pct"]

                if (breakout_up or breakout_down) and oi_expanding:
                    direction = "long" if breakout_up else "short"
                    price_move_pct = abs(current_price - (rolling_high if breakout_up else rolling_low)) / (rolling_high if breakout_up else rolling_low) * 100 if (rolling_high if breakout_up else rolling_low) > 0 else 0
                    strength = min(1.0, (price_move_pct / 5.0 + oi_change_pct / 20.0) / 2.0)

                    signals.append(ScanSignal(
                        scanner_name=self.NAME,
                        exchange=exchange,
                        symbol=symbol,
                        signal_type=f"breakout_oi_{direction}",
                        strength=strength,
                        details={
                            "direction": direction,
                            "current_price": current_price,
                            "rolling_high": rolling_high,
                            "rolling_low": rolling_low,
                            "price_move_pct": round(price_move_pct, 4),
                            "oi_change_pct": round(oi_change_pct, 4),
                            "oi_start": oi_start,
                            "oi_end": oi_end,
                        },
                    ))

        await self.emit_signals(signals)
        return signals

"""
CoinScopeAI — Funding-Extreme Scanner

Detects abnormally high or low funding rates that may signal:
  - Overcrowded positioning (mean-reversion opportunity)
  - Extreme sentiment divergence across exchanges

Logic:
  1. Collect latest funding rates across exchanges for each symbol.
  2. Flag when |funding_rate| exceeds the high/low thresholds.
  3. Optionally flag cross-exchange divergence (spread between max and min funding).
"""

from __future__ import annotations

import logging
from typing import List

from ..models import (
    EventType,
    Exchange,
    FundingRate,
    ScanSignal,
)
from .base_scanner import BaseScanner, ScannerConfig

logger = logging.getLogger("coinscopeai.scanner.funding_extreme")

DEFAULT_THRESHOLDS = {
    "high_funding_pct": 0.05,        # 0.05% per 8h → ~55% annualized
    "low_funding_pct": -0.05,
    "cross_exchange_spread_pct": 0.03,  # divergence between exchanges
    "min_exchanges": 1,
}


class FundingExtremeScanner(BaseScanner):
    NAME = "funding_extreme"

    def __init__(self, config: ScannerConfig, event_bus) -> None:
        merged = {**DEFAULT_THRESHOLDS, **config.thresholds}
        config.thresholds = merged
        super().__init__(config, event_bus)

    def _subscribed_event_types(self) -> List[EventType]:
        return [EventType.FUNDING_RATE]

    async def evaluate(self) -> List[ScanSignal]:
        signals: List[ScanSignal] = []
        t = self.config.thresholds

        for symbol in self.config.symbols:
            rates_by_exchange = {}

            for exchange in self.config.exchanges:
                latest = self._get_latest(exchange, symbol, EventType.FUNDING_RATE)
                if latest and isinstance(latest.data, FundingRate):
                    rates_by_exchange[exchange] = latest.data.funding_rate

            if not rates_by_exchange:
                continue

            # Per-exchange extreme detection
            for exchange, rate in rates_by_exchange.items():
                rate_pct = rate * 100  # convert to percentage
                if rate_pct >= t["high_funding_pct"]:
                    strength = min(1.0, rate_pct / (t["high_funding_pct"] * 5))
                    signals.append(ScanSignal(
                        scanner_name=self.NAME,
                        exchange=exchange,
                        symbol=symbol,
                        signal_type="funding_extreme_high",
                        strength=strength,
                        details={
                            "funding_rate": rate,
                            "funding_rate_pct": round(rate_pct, 6),
                            "annualized_pct": round(rate * 3 * 365 * 100, 2),
                            "threshold_pct": t["high_funding_pct"],
                        },
                    ))
                elif rate_pct <= t["low_funding_pct"]:
                    strength = min(1.0, abs(rate_pct) / abs(t["low_funding_pct"] * 5))
                    signals.append(ScanSignal(
                        scanner_name=self.NAME,
                        exchange=exchange,
                        symbol=symbol,
                        signal_type="funding_extreme_low",
                        strength=strength,
                        details={
                            "funding_rate": rate,
                            "funding_rate_pct": round(rate_pct, 6),
                            "annualized_pct": round(rate * 3 * 365 * 100, 2),
                            "threshold_pct": t["low_funding_pct"],
                        },
                    ))

            # Cross-exchange divergence
            if len(rates_by_exchange) >= max(2, t["min_exchanges"]):
                max_rate = max(rates_by_exchange.values())
                min_rate = min(rates_by_exchange.values())
                spread = (max_rate - min_rate) * 100
                if spread >= t["cross_exchange_spread_pct"]:
                    max_ex = max(rates_by_exchange, key=rates_by_exchange.get)  # type: ignore
                    min_ex = min(rates_by_exchange, key=rates_by_exchange.get)  # type: ignore
                    strength = min(1.0, spread / (t["cross_exchange_spread_pct"] * 5))
                    signals.append(ScanSignal(
                        scanner_name=self.NAME,
                        exchange=max_ex,
                        symbol=symbol,
                        signal_type="funding_cross_exchange_divergence",
                        strength=strength,
                        details={
                            "max_exchange": max_ex.value,
                            "max_rate": max_rate,
                            "min_exchange": min_ex.value,
                            "min_rate": min_rate,
                            "spread_pct": round(spread, 6),
                            "all_rates": {e.value: r for e, r in rates_by_exchange.items()},
                        },
                    ))

        await self.emit_signals(signals)
        return signals

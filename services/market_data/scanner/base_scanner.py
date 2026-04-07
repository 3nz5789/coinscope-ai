"""
CoinScopeAI — Base Scanner

All scan engines inherit from this base. Provides:
- Configurable thresholds, symbols, and timeframes
- Rolling data window management
- Signal emission through the event bus
"""

from __future__ import annotations

import abc
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from ..base import EventBus
from ..models import EventType, Exchange, MarketEvent, ScanSignal

logger = logging.getLogger("coinscopeai.scanner")


@dataclass
class ScannerConfig:
    """Configuration for a scanner instance."""
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    exchanges: List[Exchange] = field(default_factory=lambda: list(Exchange))
    window_seconds: float = 300.0       # rolling window size
    scan_interval: float = 5.0          # how often the scanner evaluates
    thresholds: Dict[str, float] = field(default_factory=dict)
    enabled: bool = True


class BaseScanner(abc.ABC):
    """Abstract base scanner that subscribes to market events and emits signals."""

    NAME: str = "base"

    def __init__(self, config: ScannerConfig, event_bus: EventBus) -> None:
        self.config = config
        self.event_bus = event_bus
        # Rolling data stores keyed by (exchange, symbol)
        self._data: Dict[str, Deque] = defaultdict(lambda: deque(maxlen=10_000))

    def subscribe(self) -> None:
        """Register event subscriptions on the event bus."""
        for et in self._subscribed_event_types():
            self.event_bus.subscribe(et, self._on_event)

    @abc.abstractmethod
    def _subscribed_event_types(self) -> List[EventType]:
        """Which event types this scanner needs."""
        ...

    async def _on_event(self, event: MarketEvent) -> None:
        """Receive an event, store it, and optionally trigger evaluation."""
        if event.symbol not in self.config.symbols:
            return
        if event.exchange not in self.config.exchanges:
            return
        key = f"{event.exchange.value}:{event.symbol}:{event.event_type.value}"
        self._data[key].append(event)
        # Prune old data outside window
        cutoff = time.time() - self.config.window_seconds
        while self._data[key] and self._data[key][0].timestamp < cutoff:
            self._data[key].popleft()

    def _get_window(self, exchange: Exchange, symbol: str, event_type: EventType) -> List[MarketEvent]:
        key = f"{exchange.value}:{symbol}:{event_type.value}"
        return list(self._data[key])

    def _get_latest(self, exchange: Exchange, symbol: str, event_type: EventType) -> Optional[MarketEvent]:
        key = f"{exchange.value}:{symbol}:{event_type.value}"
        if self._data[key]:
            return self._data[key][-1]
        return None

    @abc.abstractmethod
    async def evaluate(self) -> List[ScanSignal]:
        """Run the scan logic and return any signals."""
        ...

    async def emit_signals(self, signals: List[ScanSignal]) -> None:
        for sig in signals:
            event = MarketEvent(
                event_type=EventType.SCAN_SIGNAL,
                data=sig,
                exchange=sig.exchange,
                symbol=sig.symbol,
                timestamp=sig.timestamp,
            )
            await self.event_bus.publish(event)
            logger.info(
                "[%s] SIGNAL %s %s:%s strength=%.2f %s",
                self.NAME, sig.signal_type, sig.exchange.value, sig.symbol,
                sig.strength, sig.details,
            )

"""
CoinScopeAI — Multi-Exchange Data Aggregator

Orchestrates all exchange clients and scanners:
  - Starts / stops exchange feed clients
  - Shares a single EventBus across all components
  - Runs scanner evaluation loops
  - Exposes consolidated metrics
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from .base import BaseExchangeClient, EventBus, EventCallback
from .models import (
    ConnectionMetrics,
    EventType,
    Exchange,
    MarketEvent,
    ScanSignal,
)
from .scanner.base_scanner import BaseScanner, ScannerConfig

logger = logging.getLogger("coinscopeai.aggregator")


class Aggregator:
    """Central orchestrator for multi-exchange market data and scanners."""

    def __init__(self) -> None:
        self.event_bus = EventBus()
        self._clients: Dict[Exchange, BaseExchangeClient] = {}
        self._scanners: List[BaseScanner] = []
        self._scanner_tasks: List[asyncio.Task] = []
        self._running = False
        self._signal_callbacks: List[Callable[[ScanSignal], Coroutine[Any, Any, None]]] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_client(self, client: BaseExchangeClient) -> None:
        """Register an exchange client. Its event_bus is replaced with the shared bus."""
        client.event_bus = self.event_bus
        self._clients[client.EXCHANGE] = client
        logger.info("Registered client: %s", client.EXCHANGE.value)

    def add_scanner(self, scanner: BaseScanner) -> None:
        """Register a scanner. Its event_bus is replaced with the shared bus."""
        scanner.event_bus = self.event_bus
        scanner.subscribe()
        self._scanners.append(scanner)
        logger.info("Registered scanner: %s", scanner.NAME)

    def on_signal(self, callback: Callable[[ScanSignal], Coroutine[Any, Any, None]]) -> None:
        """Register a callback for scan signals."""
        self._signal_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start all clients and scanner evaluation loops."""
        logger.info("Aggregator starting with %d clients, %d scanners",
                     len(self._clients), len(self._scanners))
        self._running = True

        # Wire signal callbacks
        if self._signal_callbacks:
            async def _dispatch_signal(event: MarketEvent) -> None:
                if isinstance(event.data, ScanSignal):
                    for cb in self._signal_callbacks:
                        try:
                            await cb(event.data)
                        except Exception:
                            logger.exception("Signal callback error")
            self.event_bus.subscribe(EventType.SCAN_SIGNAL, _dispatch_signal)

        # Start exchange clients
        for client in self._clients.values():
            await client.start()

        # Start scanner evaluation loops
        for scanner in self._scanners:
            task = asyncio.create_task(
                self._scanner_loop(scanner),
                name=f"scanner-{scanner.NAME}",
            )
            self._scanner_tasks.append(task)

    async def stop(self) -> None:
        """Gracefully stop everything."""
        logger.info("Aggregator stopping")
        self._running = False
        for task in self._scanner_tasks:
            task.cancel()
        await asyncio.gather(*self._scanner_tasks, return_exceptions=True)
        for client in self._clients.values():
            await client.stop()
        logger.info("Aggregator stopped")

    async def _scanner_loop(self, scanner: BaseScanner) -> None:
        """Periodically evaluate a scanner."""
        while self._running:
            try:
                await scanner.evaluate()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Scanner %s evaluation error", scanner.NAME)
            await asyncio.sleep(scanner.config.scan_interval)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Return consolidated metrics for all clients."""
        result = {}
        for exchange, client in self._clients.items():
            m = client.metrics
            result[exchange.value] = {
                "state": m.state.value,
                "uptime_seconds": m.uptime_seconds,
                "messages_received": m.messages_received,
                "messages_per_second": round(m.messages_per_second, 2) if m.messages_per_second else 0,
                "reconnect_count": m.reconnect_count,
                "errors": m.errors,
                "last_message_at": m.last_message_at,
            }
        return result

    def get_scanner_names(self) -> List[str]:
        return [s.NAME for s in self._scanners]

    # ------------------------------------------------------------------
    # Convenience: subscribe to raw events
    # ------------------------------------------------------------------

    def subscribe(self, event_type: EventType, callback: EventCallback) -> None:
        self.event_bus.subscribe(event_type, callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        self.event_bus.subscribe_all(callback)

"""
Tests for the multi-exchange aggregator.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.market_data.aggregator import Aggregator
from services.market_data.base import EventBus
from services.market_data.models import (
    ConnectionMetrics, ConnectionState, EventType, Exchange,
    MarkPrice, MarketEvent, ScanSignal,
)
from services.market_data.scanner.base_scanner import ScannerConfig
from services.market_data.scanner.breakout_oi import BreakoutOIScanner


class FakeClient:
    """Minimal fake exchange client for testing aggregator wiring."""
    EXCHANGE = Exchange.BINANCE

    def __init__(self):
        self.event_bus = EventBus()
        self.metrics = ConnectionMetrics(exchange=Exchange.BINANCE, state=ConnectionState.CONNECTED)
        self.metrics.messages_received = 100
        self.metrics.connected_at = 1700000000.0
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class TestAggregator:
    def test_add_client(self):
        agg = Aggregator()
        fake = FakeClient()
        agg.add_client(fake)
        assert Exchange.BINANCE in agg._clients
        # Event bus should be replaced with aggregator's shared bus
        assert fake.event_bus is agg.event_bus

    def test_add_scanner(self):
        agg = Aggregator()
        config = ScannerConfig(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE])
        scanner = BreakoutOIScanner(config, agg.event_bus)
        agg.add_scanner(scanner)
        assert len(agg._scanners) == 1

    @pytest.mark.asyncio
    async def test_start_stop(self):
        agg = Aggregator()
        fake = FakeClient()
        agg.add_client(fake)

        await agg.start()
        assert fake.started

        # Let scanner loop tick once
        await asyncio.sleep(0.1)

        await agg.stop()
        assert fake.stopped

    def test_get_metrics(self):
        agg = Aggregator()
        fake = FakeClient()
        agg.add_client(fake)

        metrics = agg.get_metrics()
        assert "binance" in metrics
        assert metrics["binance"]["state"] == "connected"
        assert metrics["binance"]["messages_received"] == 100

    @pytest.mark.asyncio
    async def test_signal_callback(self):
        agg = Aggregator()
        received_signals = []

        async def on_sig(sig):
            received_signals.append(sig)

        agg.on_signal(on_sig)

        fake = FakeClient()
        agg.add_client(fake)
        await agg.start()

        # Manually publish a scan signal through the event bus
        sig = ScanSignal(
            scanner_name="test",
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
            signal_type="test_signal",
            strength=0.5,
        )
        event = MarketEvent(
            event_type=EventType.SCAN_SIGNAL,
            data=sig,
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
        )
        await agg.event_bus.publish(event)

        assert len(received_signals) == 1
        assert received_signals[0].signal_type == "test_signal"

        await agg.stop()

    def test_get_scanner_names(self):
        agg = Aggregator()
        config = ScannerConfig(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE])
        scanner = BreakoutOIScanner(config, agg.event_bus)
        agg.add_scanner(scanner)
        assert agg.get_scanner_names() == ["breakout_oi"]

    @pytest.mark.asyncio
    async def test_subscribe_events(self):
        agg = Aggregator()
        received = []

        async def handler(event):
            received.append(event)

        agg.subscribe(EventType.MARK_PRICE, handler)

        mp = MarkPrice(exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000)
        event = MarketEvent(
            event_type=EventType.MARK_PRICE,
            data=mp,
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
        )
        await agg.event_bus.publish(event)

        assert len(received) == 1

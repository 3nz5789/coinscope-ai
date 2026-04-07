"""
Tests for base exchange client infrastructure: EventBus, RateLimiter.
"""

import asyncio
import time
import pytest
from services.market_data.base import EventBus, RateLimiter
from services.market_data.models import (
    EventType, Exchange, MarketEvent, MarkPrice,
)


@pytest.fixture
def event_bus():
    return EventBus()


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        event_bus.subscribe(EventType.MARK_PRICE, handler)

        mp = MarkPrice(exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000.0)
        event = MarketEvent(
            event_type=EventType.MARK_PRICE,
            data=mp,
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
        )
        await event_bus.publish(event)

        assert len(received) == 1
        assert received[0].data.mark_price == 50000.0

    @pytest.mark.asyncio
    async def test_subscribe_all(self, event_bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        event_bus.subscribe_all(handler)

        mp = MarkPrice(exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000.0)
        event1 = MarketEvent(event_type=EventType.MARK_PRICE, data=mp, exchange=Exchange.BINANCE, symbol="BTCUSDT")
        event2 = MarketEvent(event_type=EventType.TRADE, data=mp, exchange=Exchange.BINANCE, symbol="BTCUSDT")

        await event_bus.publish(event1)
        await event_bus.publish(event2)

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_no_cross_contamination(self, event_bus):
        mark_received = []
        trade_received = []

        async def mark_handler(event):
            mark_received.append(event)

        async def trade_handler(event):
            trade_received.append(event)

        event_bus.subscribe(EventType.MARK_PRICE, mark_handler)
        event_bus.subscribe(EventType.TRADE, trade_handler)

        mp = MarkPrice(exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000.0)
        event = MarketEvent(event_type=EventType.MARK_PRICE, data=mp, exchange=Exchange.BINANCE, symbol="BTCUSDT")
        await event_bus.publish(event)

        assert len(mark_received) == 1
        assert len(trade_received) == 0

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_break_bus(self, event_bus):
        received = []

        async def bad_handler(event):
            raise ValueError("boom")

        async def good_handler(event):
            received.append(event)

        event_bus.subscribe(EventType.MARK_PRICE, bad_handler)
        event_bus.subscribe(EventType.MARK_PRICE, good_handler)

        mp = MarkPrice(exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000.0)
        event = MarketEvent(event_type=EventType.MARK_PRICE, data=mp, exchange=Exchange.BINANCE, symbol="BTCUSDT")
        await event_bus.publish(event)

        # good_handler should still receive the event
        assert len(received) == 1


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_basic_acquire(self):
        rl = RateLimiter(max_calls=10, period=1.0)
        start = time.monotonic()
        for _ in range(5):
            await rl.acquire()
        elapsed = time.monotonic() - start
        # Should be nearly instant for 5 calls with 10 tokens
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_rate_limit_throttle(self):
        rl = RateLimiter(max_calls=2, period=1.0)
        start = time.monotonic()
        for _ in range(4):
            await rl.acquire()
        elapsed = time.monotonic() - start
        # After 2 immediate calls, the 3rd and 4th should be delayed
        assert elapsed >= 0.3  # at least some delay

"""
Tests for Bybit client — message parsing and normalization.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch

from services.market_data.base import EventBus
from services.market_data.bybit.client import BybitClient
from services.market_data.models import (
    EventType, Exchange, OrderBook, Trade, Side,
    FundingRate, OpenInterest, MarketEvent,
)


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def client(bus):
    return BybitClient(symbols=["BTCUSDT", "ETHUSDT"], event_bus=bus)


class TestBybitOrderBook:
    @pytest.mark.asyncio
    async def test_parse_orderbook(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.ORDER_BOOK, handler)

        raw = json.dumps({
            "topic": "orderbook.1.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "data": {
                "s": "BTCUSDT",
                "b": [["50000.00", "1.500"]],
                "a": [["50001.00", "2.000"]],
                "u": 12345,
            }
        })
        await client._handle_message(raw)

        assert len(received) == 1
        ob = received[0].data
        assert isinstance(ob, OrderBook)
        assert ob.exchange == Exchange.BYBIT
        assert ob.symbol == "BTCUSDT"
        assert ob.best_bid.price == 50000.0
        assert ob.best_ask.price == 50001.0
        assert ob.sequence == 12345

    @pytest.mark.asyncio
    async def test_parse_orderbook_50(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.ORDER_BOOK, handler)

        bids = [[str(50000 - i), str(1.0 + i * 0.1)] for i in range(50)]
        asks = [[str(50001 + i), str(0.5 + i * 0.1)] for i in range(50)]

        raw = json.dumps({
            "topic": "orderbook.50.ETHUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "data": {"s": "ETHUSDT", "b": bids, "a": asks, "u": 99999},
        })
        await client._handle_message(raw)

        ob = received[0].data
        assert len(ob.bids) == 50
        assert len(ob.asks) == 50


class TestBybitTrades:
    @pytest.mark.asyncio
    async def test_parse_public_trade(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TRADE, handler)

        raw = json.dumps({
            "topic": "publicTrade.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "data": [
                {
                    "i": "trade123",
                    "T": 1700000000000,
                    "p": "50000.00",
                    "v": "0.100",
                    "S": "Buy",
                    "s": "BTCUSDT",
                }
            ]
        })
        await client._handle_message(raw)

        assert len(received) == 1
        trade = received[0].data
        assert isinstance(trade, Trade)
        assert trade.side == Side.BUY
        assert trade.price == 50000.0

    @pytest.mark.asyncio
    async def test_parse_sell_trade(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TRADE, handler)

        raw = json.dumps({
            "topic": "publicTrade.ETHUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "data": [
                {"i": "t1", "T": 1700000000000, "p": "3000", "v": "5.0", "S": "Sell", "s": "ETHUSDT"},
            ]
        })
        await client._handle_message(raw)

        trade = received[0].data
        assert trade.side == Side.SELL


class TestBybitControlMessages:
    @pytest.mark.asyncio
    async def test_subscription_ack_ignored(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe_all(handler)

        raw = json.dumps({"success": True, "ret_msg": "subscribe", "op": "subscribe"})
        await client._handle_message(raw)

        assert len(received) == 0


class TestBybitREST:
    @pytest.mark.asyncio
    async def test_poll_open_interest(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.OPEN_INTEREST, handler)

        mock_resp = {
            "retCode": 0,
            "result": {
                "list": [
                    {"openInterest": "12000.5", "timestamp": "1700000000000"}
                ]
            }
        }

        with patch.object(client, '_rest_get', new_callable=AsyncMock, return_value=mock_resp):
            await client._poll_open_interest()

        btc_events = [e for e in received if e.symbol == "BTCUSDT"]
        assert len(btc_events) >= 1
        assert btc_events[0].data.open_interest == 12000.5

    @pytest.mark.asyncio
    async def test_poll_funding_rate(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.FUNDING_RATE, handler)

        mock_resp = {
            "retCode": 0,
            "result": {
                "list": [
                    {"fundingRate": "0.00015", "fundingRateTimestamp": "1700000000000"}
                ]
            }
        }

        with patch.object(client, '_rest_get', new_callable=AsyncMock, return_value=mock_resp):
            await client._poll_funding_rate()

        btc_events = [e for e in received if e.symbol == "BTCUSDT"]
        assert len(btc_events) >= 1
        assert btc_events[0].data.funding_rate == 0.00015


class TestBybitConfig:
    def test_default_depth(self):
        c = BybitClient(symbols=["BTCUSDT"])
        assert c.orderbook_depth == 1

    def test_custom_depth(self):
        c = BybitClient(symbols=["BTCUSDT"], orderbook_depth=50)
        assert c.orderbook_depth == 50

    def test_testnet(self):
        c = BybitClient(symbols=["BTCUSDT"], use_testnet=True)
        assert "testnet" in c.WS_BASE_URL

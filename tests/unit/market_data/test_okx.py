"""
Tests for OKX client — message parsing and normalization.
"""

import json
import pytest
from services.market_data.base import EventBus
from services.market_data.okx.client import OKXClient, _inst_id, _symbol_from_inst
from services.market_data.models import (
    EventType, Exchange, MarkPrice, OrderBook, FundingRate,
    OpenInterest, Ticker, MarketEvent,
)


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def client(bus):
    return OKXClient(symbols=["BTCUSDT", "ETHUSDT"], event_bus=bus)


class TestOKXHelpers:
    def test_inst_id(self):
        assert _inst_id("BTCUSDT") == "BTC-USDT-SWAP"
        assert _inst_id("ETHUSDT") == "ETH-USDT-SWAP"

    def test_symbol_from_inst(self):
        assert _symbol_from_inst("BTC-USDT-SWAP") == "BTCUSDT"
        assert _symbol_from_inst("ETH-USDT-SWAP") == "ETHUSDT"


class TestOKXOrderBook:
    @pytest.mark.asyncio
    async def test_parse_books5(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.ORDER_BOOK, handler)

        raw = json.dumps({
            "arg": {"channel": "books5", "instId": "BTC-USDT-SWAP"},
            "data": [{
                "bids": [["50000", "1.5", "0", "3"], ["49999", "2.0", "0", "5"]],
                "asks": [["50001", "0.5", "0", "2"], ["50002", "1.0", "0", "4"]],
                "ts": "1700000000000",
            }]
        })
        await client._handle_message(raw)

        assert len(received) == 1
        ob = received[0].data
        assert isinstance(ob, OrderBook)
        assert ob.exchange == Exchange.OKX
        assert ob.symbol == "BTCUSDT"
        assert len(ob.bids) == 2
        assert ob.best_bid.price == 50000.0


class TestOKXTicker:
    @pytest.mark.asyncio
    async def test_parse_ticker(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TICKER, handler)

        raw = json.dumps({
            "arg": {"channel": "tickers", "instId": "BTC-USDT-SWAP"},
            "data": [{
                "instId": "BTC-USDT-SWAP",
                "last": "50000.5",
                "bidPx": "50000",
                "askPx": "50001",
                "high24h": "51000",
                "low24h": "49000",
                "vol24h": "10000",
                "volCcy24h": "500000000",
                "ts": "1700000000000",
            }]
        })
        await client._handle_message(raw)

        assert len(received) == 1
        t = received[0].data
        assert isinstance(t, Ticker)
        assert t.last_price == 50000.5
        assert t.high_24h == 51000.0


class TestOKXMarkPrice:
    @pytest.mark.asyncio
    async def test_parse_mark_price(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.MARK_PRICE, handler)

        raw = json.dumps({
            "arg": {"channel": "mark-price", "instId": "ETH-USDT-SWAP"},
            "data": [{
                "instId": "ETH-USDT-SWAP",
                "markPx": "3000.50",
                "ts": "1700000000000",
            }]
        })
        await client._handle_message(raw)

        assert len(received) == 1
        mp = received[0].data
        assert isinstance(mp, MarkPrice)
        assert mp.mark_price == 3000.50
        assert mp.symbol == "ETHUSDT"


class TestOKXFundingRate:
    @pytest.mark.asyncio
    async def test_parse_funding_rate(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.FUNDING_RATE, handler)

        raw = json.dumps({
            "arg": {"channel": "funding-rate", "instId": "BTC-USDT-SWAP"},
            "data": [{
                "instId": "BTC-USDT-SWAP",
                "fundingRate": "0.00015",
                "nextFundingRate": "0.00012",
                "nextFundingTime": "1700003600000",
                "ts": "1700000000000",
            }]
        })
        await client._handle_message(raw)

        assert len(received) == 1
        fr = received[0].data
        assert isinstance(fr, FundingRate)
        assert fr.funding_rate == 0.00015
        assert fr.predicted_rate == 0.00012


class TestOKXOpenInterest:
    @pytest.mark.asyncio
    async def test_parse_open_interest(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.OPEN_INTEREST, handler)

        raw = json.dumps({
            "arg": {"channel": "open-interest", "instId": "BTC-USDT-SWAP"},
            "data": [{
                "instId": "BTC-USDT-SWAP",
                "oi": "15000",
                "oiCcy": "750000000",
                "ts": "1700000000000",
            }]
        })
        await client._handle_message(raw)

        assert len(received) == 1
        oi = received[0].data
        assert isinstance(oi, OpenInterest)
        assert oi.open_interest == 15000.0
        assert oi.open_interest_value == 750000000.0


class TestOKXControlMessages:
    @pytest.mark.asyncio
    async def test_subscription_ack_ignored(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe_all(handler)

        raw = json.dumps({"event": "subscribe", "arg": {"channel": "books5", "instId": "BTC-USDT-SWAP"}})
        await client._handle_message(raw)

        assert len(received) == 0

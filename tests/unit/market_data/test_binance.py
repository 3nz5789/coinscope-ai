"""
Tests for Binance Futures client — message parsing and normalization.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.market_data.base import EventBus
from services.market_data.binance.client import BinanceFuturesClient
from services.market_data.models import (
    EventType, Exchange, MarkPrice, OrderBook, Trade, Side,
    FundingRate, OpenInterest, MarketEvent,
)


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def client(bus):
    return BinanceFuturesClient(symbols=["BTCUSDT", "ETHUSDT"], event_bus=bus)


class TestBinanceMarkPrice:
    @pytest.mark.asyncio
    async def test_parse_mark_price(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.MARK_PRICE, handler)

        raw = json.dumps({
            "stream": "btcusdt@markPrice@1s",
            "data": {
                "e": "markPriceUpdate",
                "E": 1700000000000,
                "s": "BTCUSDT",
                "p": "50000.50",
                "i": "49999.00",
                "P": "50001.00",
                "r": "0.00010000",
                "T": 1700000000000,
            }
        })
        await client._handle_combined_message(raw)

        assert len(received) == 1
        mp = received[0].data
        assert isinstance(mp, MarkPrice)
        assert mp.exchange == Exchange.BINANCE
        assert mp.symbol == "BTCUSDT"
        assert mp.mark_price == 50000.50
        assert mp.index_price == 49999.0
        assert mp.raw["e"] == "markPriceUpdate"


class TestBinanceBookTicker:
    @pytest.mark.asyncio
    async def test_parse_book_ticker(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.ORDER_BOOK, handler)

        raw = json.dumps({
            "stream": "btcusdt@bookTicker",
            "data": {
                "e": "bookTicker",
                "u": 1234567890,
                "s": "BTCUSDT",
                "b": "50000.00",
                "B": "1.500",
                "a": "50001.00",
                "A": "2.000",
                "T": 1700000000000,
                "E": 1700000000000,
            }
        })
        await client._handle_combined_message(raw)

        assert len(received) == 1
        ob = received[0].data
        assert isinstance(ob, OrderBook)
        assert ob.best_bid.price == 50000.0
        assert ob.best_bid.quantity == 1.5
        assert ob.best_ask.price == 50001.0
        assert ob.best_ask.quantity == 2.0
        assert ob.spread == 1.0


class TestBinanceAggTrade:
    @pytest.mark.asyncio
    async def test_parse_agg_trade_buy(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TRADE, handler)

        raw = json.dumps({
            "stream": "btcusdt@aggTrade",
            "data": {
                "e": "aggTrade",
                "E": 1700000000000,
                "a": 987654321,
                "s": "BTCUSDT",
                "p": "50000.00",
                "q": "0.100",
                "f": 100,
                "l": 100,
                "T": 1700000000000,
                "m": False,  # buyer is maker = False → taker is buyer
            }
        })
        await client._handle_combined_message(raw)

        assert len(received) == 1
        trade = received[0].data
        assert isinstance(trade, Trade)
        assert trade.side == Side.BUY
        assert trade.price == 50000.0
        assert trade.quantity == 0.1

    @pytest.mark.asyncio
    async def test_parse_agg_trade_sell(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TRADE, handler)

        raw = json.dumps({
            "stream": "ethusdt@aggTrade",
            "data": {
                "e": "aggTrade",
                "E": 1700000000000,
                "a": 123,
                "s": "ETHUSDT",
                "p": "3000.00",
                "q": "1.000",
                "f": 100,
                "l": 100,
                "T": 1700000000000,
                "m": True,  # seller is maker → taker sold
            }
        })
        await client._handle_combined_message(raw)

        trade = received[0].data
        assert trade.side == Side.SELL


class TestBinanceREST:
    @pytest.mark.asyncio
    async def test_poll_open_interest(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.OPEN_INTEREST, handler)

        mock_response = {
            "symbol": "BTCUSDT",
            "openInterest": "15000.000",
            "time": 1700000000000,
        }

        with patch.object(client, '_rest_get', new_callable=AsyncMock, return_value=mock_response):
            await client._poll_open_interest()

        # Should receive one per symbol
        btc_events = [e for e in received if e.symbol == "BTCUSDT"]
        assert len(btc_events) >= 1
        oi = btc_events[0].data
        assert isinstance(oi, OpenInterest)
        assert oi.open_interest == 15000.0

    @pytest.mark.asyncio
    async def test_poll_funding_rate(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.FUNDING_RATE, handler)

        mock_response = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.00",
            "indexPrice": "49999.00",
            "lastFundingRate": "0.00010000",
            "nextFundingTime": 1700003600000,
            "time": 1700000000000,
        }

        with patch.object(client, '_rest_get', new_callable=AsyncMock, return_value=mock_response):
            await client._poll_funding_rate()

        btc_events = [e for e in received if e.symbol == "BTCUSDT"]
        assert len(btc_events) >= 1
        fr = btc_events[0].data
        assert isinstance(fr, FundingRate)
        assert fr.funding_rate == 0.0001


class TestBinanceClientConfig:
    def test_default_urls(self):
        c = BinanceFuturesClient(symbols=["BTCUSDT"])
        assert "fstream.binance.com" in c.WS_BASE_URL
        assert "fapi.binance.com" in c.REST_BASE_URL

    def test_testnet_urls(self):
        c = BinanceFuturesClient(symbols=["BTCUSDT"], use_testnet=True)
        assert "testnet" in c.REST_BASE_URL or "binancefuture" in c.WS_BASE_URL

    def test_symbols_uppercased(self):
        c = BinanceFuturesClient(symbols=["btcusdt", "ethusdt"])
        assert c.symbols == ["BTCUSDT", "ETHUSDT"]

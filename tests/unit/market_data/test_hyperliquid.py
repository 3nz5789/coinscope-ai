"""
Tests for Hyperliquid client — message parsing and normalization.
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.market_data.base import EventBus
from services.market_data.hyperliquid.client import HyperliquidClient, _hl_coin
from services.market_data.models import (
    EventType, Exchange, MarkPrice, OrderBook, Trade, Side,
    FundingRate, OpenInterest, MarketEvent,
)


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def client(bus):
    return HyperliquidClient(symbols=["BTCUSDT", "ETHUSDT"], event_bus=bus)


class TestHLHelpers:
    def test_hl_coin(self):
        assert _hl_coin("BTCUSDT") == "BTC"
        assert _hl_coin("ETHUSDT") == "ETH"
        assert _hl_coin("SOLUSDT") == "SOL"


class TestHLAllMids:
    @pytest.mark.asyncio
    async def test_parse_all_mids(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.MARK_PRICE, handler)

        raw = json.dumps({
            "channel": "allMids",
            "data": {
                "mids": {
                    "BTC": "50000.5",
                    "ETH": "3000.25",
                    "SOL": "100.0",  # not in our symbol list
                }
            }
        })
        await client._handle_all_mids(raw)

        # Should only get BTC and ETH (SOL not in symbols)
        assert len(received) == 2
        symbols = {e.data.symbol for e in received}
        assert "BTCUSDT" in symbols
        assert "ETHUSDT" in symbols

        btc = [e for e in received if e.data.symbol == "BTCUSDT"][0].data
        assert btc.mark_price == 50000.5


class TestHLL2Book:
    @pytest.mark.asyncio
    async def test_parse_l2book(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.ORDER_BOOK, handler)

        raw = json.dumps({
            "channel": "l2Book",
            "data": {
                "coin": "BTC",
                "time": 1700000000000,
                "levels": [
                    [{"px": "50000", "sz": "1.5", "n": 3}, {"px": "49999", "sz": "2.0", "n": 5}],
                    [{"px": "50001", "sz": "0.5", "n": 2}, {"px": "50002", "sz": "1.0", "n": 4}],
                ]
            }
        })
        await client._handle_l2book(raw)

        assert len(received) == 1
        ob = received[0].data
        assert isinstance(ob, OrderBook)
        assert ob.exchange == Exchange.HYPERLIQUID
        assert ob.symbol == "BTCUSDT"
        assert len(ob.bids) == 2
        assert len(ob.asks) == 2
        assert ob.best_bid.price == 50000.0


class TestHLTrades:
    @pytest.mark.asyncio
    async def test_parse_trades(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TRADE, handler)

        raw = json.dumps({
            "channel": "trades",
            "data": [
                {"coin": "BTC", "side": "B", "px": "50000", "sz": "0.1", "time": 1700000000000, "tid": "t1"},
                {"coin": "BTC", "side": "A", "px": "49999", "sz": "0.2", "time": 1700000000001, "tid": "t2"},
            ]
        })
        await client._handle_trades(raw)

        assert len(received) == 2
        assert received[0].data.side == Side.BUY
        assert received[1].data.side == Side.SELL

    @pytest.mark.asyncio
    async def test_unknown_coin_ignored(self, client, bus):
        received = []

        async def handler(event: MarketEvent):
            received.append(event)

        bus.subscribe(EventType.TRADE, handler)

        raw = json.dumps({
            "channel": "trades",
            "data": [
                {"coin": "DOGE", "side": "B", "px": "0.1", "sz": "1000", "time": 1700000000000, "tid": "t1"},
            ]
        })
        await client._handle_trades(raw)

        assert len(received) == 0


class TestHLREST:
    @pytest.mark.asyncio
    async def test_poll_meta_and_ctx(self, client, bus):
        fr_received = []
        oi_received = []

        async def fr_handler(event: MarketEvent):
            fr_received.append(event)

        async def oi_handler(event: MarketEvent):
            oi_received.append(event)

        bus.subscribe(EventType.FUNDING_RATE, fr_handler)
        bus.subscribe(EventType.OPEN_INTEREST, oi_handler)

        mock_result = [
            {
                "universe": [
                    {"name": "BTC", "szDecimals": 5},
                    {"name": "ETH", "szDecimals": 4},
                    {"name": "SOL", "szDecimals": 2},
                ]
            },
            [
                {"funding": "0.00012", "openInterest": "15000", "markPx": "50000"},
                {"funding": "-0.00005", "openInterest": "200000", "markPx": "3000"},
                {"funding": "0.00001", "openInterest": "500000", "markPx": "100"},
            ]
        ]

        # Mock the aiohttp session post
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = AsyncMock(return_value=mock_result)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.post = MagicMock(return_value=mock_resp)

        with patch.object(client, '_get_session', new_callable=AsyncMock, return_value=mock_session):
            await client._poll_meta_and_ctx()

        # BTC and ETH should have funding + OI; SOL should not (not in symbols)
        assert len(fr_received) == 2
        assert len(oi_received) == 2

        btc_fr = [e for e in fr_received if e.symbol == "BTCUSDT"]
        assert len(btc_fr) == 1
        assert btc_fr[0].data.funding_rate == 0.00012

        eth_oi = [e for e in oi_received if e.symbol == "ETHUSDT"]
        assert len(eth_oi) == 1
        assert eth_oi[0].data.open_interest == 200000.0

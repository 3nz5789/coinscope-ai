"""
Tests for CoinScopeAI Phase 2 — Hyperliquid Deep Client

Uses mock HTTP responses to test parsing and normalisation logic
without hitting the live API.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.market_data.hyperliquid.deep_client import (
    HyperliquidDeepClient,
    HyperliquidDeepWs,
)
from services.market_data.models import (
    AssetContext,
    Exchange,
    FundingRate,
    L2OrderBook,
    OrderBookLevel,
    PredictedFunding,
)


# ---------------------------------------------------------------------------
# Fixtures: mock API responses
# ---------------------------------------------------------------------------

META_AND_ASSET_CTXS_RESPONSE = [
    {
        "universe": [
            {"name": "BTC", "szDecimals": 5, "maxLeverage": 50},
            {"name": "ETH", "szDecimals": 4, "maxLeverage": 50},
        ],
        "marginTables": [],
    },
    [
        {
            "dayNtlVlm": "500000000.0",
            "funding": "0.0001",
            "impactPxs": ["83000.0", "83100.0"],
            "markPx": "83050.0",
            "midPx": "83045.0",
            "openInterest": "12000.5",
            "oraclePx": "83060.0",
            "premium": "0.00015",
            "prevDayPx": "82000.0",
        },
        {
            "dayNtlVlm": "200000000.0",
            "funding": "0.00005",
            "impactPxs": ["3200.0", "3210.0"],
            "markPx": "3205.0",
            "midPx": "3204.5",
            "openInterest": "50000.0",
            "oraclePx": "3206.0",
            "premium": "0.0001",
            "prevDayPx": "3150.0",
        },
    ],
]

PREDICTED_FUNDINGS_RESPONSE = [
    [
        "BTC",
        [
            ["BinPerp", {"fundingRate": "0.0001", "nextFundingTime": 1700000000000}],
            ["HlPerp", {"fundingRate": "0.00005", "nextFundingTime": 1700000000000}],
            ["BybitPerp", {"fundingRate": "0.00012", "nextFundingTime": 1700000000000}],
        ],
    ],
    [
        "ETH",
        [
            ["BinPerp", {"fundingRate": "0.00008", "nextFundingTime": 1700000000000}],
            ["HlPerp", {"fundingRate": "0.00003", "nextFundingTime": 1700000000000}],
        ],
    ],
]

FUNDING_HISTORY_RESPONSE = [
    {"coin": "BTC", "fundingRate": "0.0001", "premium": "0.00015", "time": 1700000000000},
    {"coin": "BTC", "fundingRate": "0.00008", "premium": "0.00012", "time": 1700003600000},
    {"coin": "BTC", "fundingRate": "-0.00005", "premium": "-0.0001", "time": 1700007200000},
]

L2_BOOK_RESPONSE = {
    "coin": "BTC",
    "time": 1700000000000,
    "levels": [
        [
            {"px": "83000.0", "sz": "5.5", "n": 10},
            {"px": "82999.0", "sz": "3.2", "n": 5},
            {"px": "82998.0", "sz": "1.0", "n": 2},
        ],
        [
            {"px": "83001.0", "sz": "4.0", "n": 8},
            {"px": "83002.0", "sz": "2.5", "n": 4},
            {"px": "83003.0", "sz": "0.5", "n": 1},
        ],
    ],
}

ALL_MIDS_RESPONSE = {"BTC": "83050.0", "ETH": "3205.0", "SOL": "145.0"}


# ---------------------------------------------------------------------------
# Helper to mock aiohttp
# ---------------------------------------------------------------------------

class MockResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status = status

    async def json(self):
        return self._data

    def raise_for_status(self):
        if self.status >= 400:
            raise Exception(f"HTTP {self.status}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSession:
    def __init__(self, response_data):
        self._response_data = response_data
        self.closed = False

    def post(self, url, json=None):
        return MockResponse(self._response_data)

    async def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# Tests: REST Client
# ---------------------------------------------------------------------------

class TestHyperliquidDeepClient:
    @pytest.fixture
    def client(self):
        c = HyperliquidDeepClient()
        return c

    @pytest.mark.asyncio
    async def test_get_meta_and_asset_contexts(self, client):
        client._session = MockSession(META_AND_ASSET_CTXS_RESPONSE)
        client._external_session = True

        meta, contexts = await client.get_meta_and_asset_contexts()

        assert "universe" in meta
        assert len(contexts) == 2

        btc = contexts[0]
        assert btc.symbol == "BTC"
        assert btc.funding_rate == 0.0001
        assert btc.mark_price == 83050.0
        assert btc.mid_price == 83045.0
        assert btc.oracle_price == 83060.0
        assert btc.open_interest == 12000.5
        assert btc.day_notional_volume == 500000000.0
        assert btc.premium == 0.00015
        assert btc.prev_day_price == 82000.0
        assert btc.impact_prices == [83000.0, 83100.0]

        eth = contexts[1]
        assert eth.symbol == "ETH"
        assert eth.funding_rate == 0.00005

    @pytest.mark.asyncio
    async def test_get_predicted_fundings(self, client):
        client._session = MockSession(PREDICTED_FUNDINGS_RESPONSE)
        client._external_session = True

        result = await client.get_predicted_fundings()

        assert "BTC" in result
        assert len(result["BTC"]) == 3
        assert result["BTC"][0].venue == "BinPerp"
        assert result["BTC"][0].predicted_rate == 0.0001

        assert "ETH" in result
        assert len(result["ETH"]) == 2

    @pytest.mark.asyncio
    async def test_get_funding_history(self, client):
        client._session = MockSession(FUNDING_HISTORY_RESPONSE)
        client._external_session = True

        rates = await client.get_funding_history("BTC", 1700000000000)

        assert len(rates) == 3
        assert rates[0].symbol == "BTC"
        assert rates[0].exchange == Exchange.HYPERLIQUID
        assert rates[0].rate == 0.0001
        assert rates[0].premium == 0.00015
        assert rates[2].rate == -0.00005

    @pytest.mark.asyncio
    async def test_get_l2_book(self, client):
        client._session = MockSession(L2_BOOK_RESPONSE)
        client._external_session = True

        book = await client.get_l2_book("BTC")

        assert book.symbol == "BTC"
        assert book.exchange == Exchange.HYPERLIQUID
        assert len(book.bids) == 3
        assert len(book.asks) == 3
        assert book.best_bid == 83000.0
        assert book.best_ask == 83001.0
        assert book.bids[0].num_orders == 10
        assert book.asks[0].size == 4.0

    @pytest.mark.asyncio
    async def test_get_all_mids(self, client):
        client._session = MockSession(ALL_MIDS_RESPONSE)
        client._external_session = True

        mids = await client.get_all_mids()

        assert mids["BTC"] == 83050.0
        assert mids["ETH"] == 3205.0
        assert mids["SOL"] == 145.0


# ---------------------------------------------------------------------------
# Tests: WebSocket Parser Helpers
# ---------------------------------------------------------------------------

class TestHyperliquidDeepWsParsers:
    def test_parse_l2_book(self):
        book = HyperliquidDeepWs.parse_l2_book(L2_BOOK_RESPONSE)
        assert book.symbol == "BTC"
        assert book.exchange == Exchange.HYPERLIQUID
        assert len(book.bids) == 3
        assert len(book.asks) == 3
        assert book.best_bid == 83000.0
        assert book.best_ask == 83001.0

    def test_parse_asset_context(self):
        data = {
            "coin": "BTC",
            "ctx": {
                "funding": "0.0001",
                "markPx": "83050.0",
                "midPx": "83045.0",
                "oraclePx": "83060.0",
                "openInterest": "12000.5",
                "dayNtlVlm": "500000000.0",
                "premium": "0.00015",
                "prevDayPx": "82000.0",
                "impactPxs": ["83000.0", "83100.0"],
            },
        }
        ctx = HyperliquidDeepWs.parse_asset_context(data)
        assert ctx.symbol == "BTC"
        assert ctx.funding_rate == 0.0001
        assert ctx.mark_price == 83050.0
        assert ctx.open_interest == 12000.5

    def test_parse_asset_context_missing_fields(self):
        data = {
            "coin": "SOL",
            "ctx": {
                "funding": "0.0",
                "markPx": "145.0",
                "midPx": None,
                "oraclePx": "145.5",
                "openInterest": "0.0",
                "dayNtlVlm": "0.0",
                "premium": None,
                "prevDayPx": "140.0",
                "impactPxs": None,
            },
        }
        ctx = HyperliquidDeepWs.parse_asset_context(data)
        assert ctx.symbol == "SOL"
        assert ctx.mid_price is None
        assert ctx.premium == 0.0
        assert ctx.impact_prices is None


# ---------------------------------------------------------------------------
# Tests: WebSocket Subscription Management
# ---------------------------------------------------------------------------

class TestHyperliquidDeepWsSubscriptions:
    def test_subscribe_l2_book(self):
        ws = HyperliquidDeepWs()
        ws.subscribe_l2_book("BTC")
        assert len(ws._subscriptions) == 1
        assert ws._subscriptions[0] == {"type": "l2Book", "coin": "BTC"}

    def test_subscribe_active_asset_ctx(self):
        ws = HyperliquidDeepWs()
        ws.subscribe_active_asset_ctx("ETH")
        assert ws._subscriptions[0] == {"type": "activeAssetCtx", "coin": "ETH"}

    def test_subscribe_trades(self):
        ws = HyperliquidDeepWs()
        ws.subscribe_trades("SOL")
        assert ws._subscriptions[0] == {"type": "trades", "coin": "SOL"}

    def test_subscribe_all_mids(self):
        ws = HyperliquidDeepWs()
        ws.subscribe_all_mids()
        assert ws._subscriptions[0] == {"type": "allMids"}

    def test_multiple_subscriptions(self):
        ws = HyperliquidDeepWs()
        ws.subscribe_l2_book("BTC")
        ws.subscribe_l2_book("ETH")
        ws.subscribe_active_asset_ctx("BTC")
        assert len(ws._subscriptions) == 3

"""
Tests for CoinScopeAI Phase 2 — CoinGlass Client

Tests both the CoinGlass API client and the free exchange fallback client
using mocked HTTP responses.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.market_data.coinglass.client import (
    CoinGlassClient,
    ExchangeFallbackClient,
)
from services.market_data.models import (
    AggregatedOI,
    FundingSnapshot,
    LiquidationSnapshot,
)


# ---------------------------------------------------------------------------
# Mock helpers
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
    def __init__(self, responses=None):
        self._responses = responses or {}
        self._default_response = {"code": "0", "msg": "", "data": []}
        self.closed = False

    def get(self, url, params=None):
        for key, resp in self._responses.items():
            if key in url:
                return MockResponse(resp)
        return MockResponse(self._default_response)

    async def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# Tests: CoinGlass Client (with API key)
# ---------------------------------------------------------------------------

class TestCoinGlassClientWithKey:
    @pytest.fixture
    def client(self):
        c = CoinGlassClient(api_key="test_key_123")
        return c

    def test_has_api_key(self, client):
        assert client.has_api_key is True

    @pytest.mark.asyncio
    async def test_get_liquidation_history(self, client):
        mock_data = {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "longLiquidationUsd": 5000000,
                    "shortLiquidationUsd": 3000000,
                    "count": 150,
                }
            ],
        }
        client._session = MockSession({
            "liquidation/aggregated-history": mock_data,
        })
        client._external_session = True

        result = await client.get_liquidation_history("BTC", "1h")

        assert isinstance(result, LiquidationSnapshot)
        assert result.symbol == "BTC"
        assert result.long_liquidations_usd == 5000000
        assert result.short_liquidations_usd == 3000000
        assert result.total_count == 150
        assert result.window_seconds == 3600

    @pytest.mark.asyncio
    async def test_get_oi_exchange_list(self, client):
        mock_data = {
            "code": "0",
            "msg": "",
            "data": [
                {"exchangeName": "Binance", "openInterest": 50000},
                {"exchangeName": "Bybit", "openInterest": 30000},
                {"exchangeName": "OKX", "openInterest": 20000},
            ],
        }
        client._session = MockSession({
            "open-interest/exchange-list": mock_data,
        })
        client._external_session = True

        result = await client.get_oi_exchange_list("BTC")

        assert isinstance(result, AggregatedOI)
        assert result.symbol == "BTC"
        assert result.total_oi == 100000
        assert result.by_exchange["Binance"] == 50000

    @pytest.mark.asyncio
    async def test_get_funding_exchange_list(self, client):
        mock_data = {
            "code": "0",
            "msg": "",
            "data": [
                {"exchangeName": "Binance", "rate": 0.0001},
                {"exchangeName": "Bybit", "rate": 0.0002},
            ],
        }
        client._session = MockSession({
            "funding-rate/exchange-list": mock_data,
        })
        client._external_session = True

        result = await client.get_funding_exchange_list("BTC")

        assert isinstance(result, FundingSnapshot)
        assert result.symbol == "BTC"
        assert len(result.rates) == 2
        assert abs(result.mean_rate - 0.00015) < 1e-10


# ---------------------------------------------------------------------------
# Tests: CoinGlass Client (no API key — fallback)
# ---------------------------------------------------------------------------

class TestCoinGlassClientNoKey:
    @pytest.fixture
    def client(self):
        c = CoinGlassClient(api_key="")
        return c

    def test_no_api_key(self, client):
        assert client.has_api_key is False


# ---------------------------------------------------------------------------
# Tests: Exchange Fallback Client
# ---------------------------------------------------------------------------

class TestExchangeFallbackClient:
    @pytest.fixture
    def fallback(self):
        return ExchangeFallbackClient()

    @pytest.mark.asyncio
    async def test_get_funding_snapshot_empty(self, fallback):
        """Test that fallback returns a valid snapshot even with no data."""
        # Mock all requests to return None
        fallback._session = MockSession()
        fallback._session.closed = False

        result = await fallback.get_funding_snapshot("BTC")
        assert isinstance(result, FundingSnapshot)
        assert result.symbol == "BTC"

    @pytest.mark.asyncio
    async def test_get_aggregated_oi_empty(self, fallback):
        fallback._session = MockSession()
        fallback._session.closed = False

        result = await fallback.get_aggregated_oi("BTC")
        assert isinstance(result, AggregatedOI)
        assert result.symbol == "BTC"

    @pytest.mark.asyncio
    async def test_get_liquidation_snapshot_empty(self, fallback):
        fallback._session = MockSession()
        fallback._session.closed = False

        result = await fallback.get_liquidation_snapshot("BTC")
        assert isinstance(result, LiquidationSnapshot)
        assert result.symbol == "BTC"
        assert result.window_seconds == 3600


# ---------------------------------------------------------------------------
# Tests: Parsing helpers
# ---------------------------------------------------------------------------

class TestCoinGlassParsers:
    def test_parse_liquidation_history_dict(self):
        raw = {
            "longLiquidationUsd": 1000000,
            "shortLiquidationUsd": 500000,
            "count": 50,
        }
        result = CoinGlassClient._parse_liquidation_history("BTC", raw, "1h")
        assert result.long_liquidations_usd == 1000000
        assert result.short_liquidations_usd == 500000
        assert result.total_count == 50

    def test_parse_liquidation_history_list(self):
        raw = [
            {"longLiquidationUsd": 500000, "shortLiquidationUsd": 200000, "count": 20},
            {"longLiquidationUsd": 800000, "shortLiquidationUsd": 400000, "count": 40},
        ]
        result = CoinGlassClient._parse_liquidation_history("ETH", raw, "4h")
        assert result.long_liquidations_usd == 800000  # takes latest
        assert result.window_seconds == 14400

    def test_parse_liquidation_history_empty(self):
        result = CoinGlassClient._parse_liquidation_history("BTC", [], "1h")
        assert result.total_usd == 0

    def test_parse_oi_exchange_list(self):
        raw = [
            {"exchangeName": "Binance", "openInterest": 100},
            {"exchangeName": "OKX", "openInterest": 50},
        ]
        result = CoinGlassClient._parse_oi_exchange_list("BTC", raw)
        assert result.total_oi == 150

    def test_parse_funding_exchange_list(self):
        raw = [
            {"exchangeName": "Binance", "rate": 0.0001},
            {"exchangeName": "Bybit", "rate": 0.0003},
        ]
        result = CoinGlassClient._parse_funding_exchange_list("BTC", raw)
        assert len(result.rates) == 2
        assert abs(result.max_divergence - 0.0002) < 1e-10

"""
test_api.py — REST Client & WebSocket Manager Tests
=====================================================
Tests Binance REST client response parsing, signing, error handling,
and WebSocket message routing.  Uses httpx mock transports to avoid
live API calls.
"""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from data.binance_rest import BinanceRESTClient
from data.data_normalizer import DataNormalizer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_response():
    """Factory: build a fake httpx.Response with JSON body."""
    def _make(status_code: int = 200, body: dict | list = None):
        body = body or {}
        return httpx.Response(
            status_code = status_code,
            content     = json.dumps(body).encode(),
            headers     = {
                "Content-Type": "application/json",
                "X-MBX-USED-WEIGHT-1M": "10",
            },
        )
    return _make


@pytest.fixture
def rest_client():
    """BinanceRESTClient with testnet=True and fake credentials."""
    return BinanceRESTClient(
        api_key    = "test_key",
        api_secret = "test_secret",
        testnet    = True,
    )


@pytest.fixture
def normalizer():
    return DataNormalizer()


# ---------------------------------------------------------------------------
# REST client tests
# ---------------------------------------------------------------------------

class TestBinanceRESTClient:

    @pytest.mark.asyncio
    async def test_ping_success(self, rest_client, mock_response):
        """ping() returns True on HTTP 200 with empty body."""
        with patch.object(
            rest_client._client, "get",
            new_callable=AsyncMock,
            return_value=mock_response(200, {}),
        ):
            result = await rest_client.ping()
        assert result is True

    @pytest.mark.asyncio
    async def test_ping_failure(self, rest_client, mock_response):
        """ping() returns False on HTTP 500."""
        with patch.object(
            rest_client._client, "get",
            new_callable=AsyncMock,
            return_value=mock_response(500, {"msg": "Internal error"}),
        ):
            result = await rest_client.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_klines_returns_candle_list(self, rest_client, mock_response, normalizer):
        """get_klines() returns a list of Candle dataclasses."""
        raw_kline = [
            1_700_000_000_000,  # open_time
            "65000.00",         # open
            "65500.00",         # high
            "64800.00",         # low
            "65200.00",         # close
            "100.5",            # volume
            1_700_000_059_999,  # close_time
            "6541000.00",       # quote_volume
            250,                # trades
            "60.3",             # taker_buy_volume
            "3927810.00",       # taker_buy_quote
            "0",
        ]
        with patch.object(
            rest_client._client, "get",
            new_callable=AsyncMock,
            return_value=mock_response(200, [raw_kline]),
        ):
            candles = await rest_client.get_klines("BTCUSDT", "1m", limit=1)

        assert len(candles) == 1
        c = candles[0]
        assert c["open"]  == pytest.approx(65000.0)
        assert c["high"]  == pytest.approx(65500.0)
        assert c["close"] == pytest.approx(65200.0)

    @pytest.mark.asyncio
    async def test_get_symbol_price_returns_float(self, rest_client, mock_response):
        """get_symbol_price() parses the price field and returns a float."""
        with patch.object(
            rest_client._client, "get",
            new_callable=AsyncMock,
            return_value=mock_response(200, {"symbol": "BTCUSDT", "price": "65432.10"}),
        ):
            price = await rest_client.get_symbol_price("BTCUSDT")
        assert isinstance(price, float)
        assert price == pytest.approx(65432.10)

    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self, rest_client, mock_response):
        """is_throttled returns True when weight usage > 85% of 2400."""
        resp = mock_response(200, {"symbol": "BTCUSDT", "price": "1.0"})
        resp.headers["X-MBX-USED-WEIGHT-1M"] = "2100"   # 87.5% of 2400
        with patch.object(
            rest_client._client, "get",
            new_callable=AsyncMock,
            return_value=resp,
        ):
            await rest_client.get_symbol_price("BTCUSDT")
        assert rest_client.is_throttled

    def test_signature_includes_timestamp(self, rest_client):
        """_sign() appends a timestamp and returns a non-empty hex digest."""
        params = {"symbol": "BTCUSDT", "limit": 10}
        signed = rest_client._sign(params)
        assert "timestamp" in signed
        assert "signature" in signed
        assert len(signed["signature"]) == 64   # SHA256 hex = 64 chars


# ---------------------------------------------------------------------------
# DataNormalizer tests
# ---------------------------------------------------------------------------

class TestDataNormalizer:

    def test_klines_to_candles_basic(self, normalizer):
        raw = [
            [
                1_700_000_000_000, "65000", "65500", "64800", "65200",
                "100", 1_700_000_059_999, "6541000", 250, "60", "3900000", "0",
            ]
        ]
        candles = normalizer.klines_to_candles("BTCUSDT", "1m", raw)
        assert len(candles) == 1
        c = candles[0]
        assert c.symbol   == "BTCUSDT"
        assert c.interval == "1m"
        assert c.open     == pytest.approx(65000.0)
        assert c.close    == pytest.approx(65200.0)
        assert c.volume   == pytest.approx(100.0)

    def test_candle_properties(self, normalizer):
        raw = [[
            1_700_000_000_000, "100", "120", "90", "115",
            "50", 1_700_000_059_999, "5000", 100, "30", "3000", "0",
        ]]
        candles = normalizer.klines_to_candles("ETHUSDT", "5m", raw)
        c = candles[0]
        assert c.is_bullish is True          # close > open
        assert c.body_pct   > 0              # positive body
        assert c.upper_wick_pct >= 0
        assert c.lower_wick_pct >= 0

    def test_empty_klines_returns_empty_list(self, normalizer):
        result = normalizer.klines_to_candles("BTCUSDT", "1h", [])
        assert result == []

    def test_depth_to_orderbook(self, normalizer):
        raw = {
            "lastUpdateId": 123456,
            "bids": [["65000", "1.0"], ["64990", "2.5"]],
            "asks": [["65010", "0.8"], ["65020", "1.2"]],
        }
        ob = normalizer.depth_to_orderbook("BTCUSDT", raw)
        assert ob.symbol        == "BTCUSDT"
        assert len(ob.bids)     == 2
        assert len(ob.asks)     == 2
        assert ob.best_bid      == pytest.approx(65000.0)
        assert ob.best_ask      == pytest.approx(65010.0)
        assert ob.spread_pct    > 0

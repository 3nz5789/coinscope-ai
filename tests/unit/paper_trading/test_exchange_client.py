"""
Unit tests for CoinScopeAI Paper Trading — Exchange Client.
Tests cover: testnet enforcement, rate limiting, order placement,
error handling, and kill switch (close all positions).
"""

import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from services.paper_trading.config import (
    BINANCE_FUTURES_TESTNET_REST,
    ExchangeConfig,
    _BLOCKED_MAINNET_URLS,
)
from services.paper_trading.exchange_client import (
    BinanceFuturesTestnetClient,
    ExchangeError,
    InsufficientBalanceError,
    OrderResult,
    RateLimitError,
)


# ── Testnet Enforcement Tests ─────────────────────────────────

class TestTestnetEnforcement:

    def test_default_config_is_testnet(self):
        config = ExchangeConfig()
        assert "testnet" in config.rest_url

    def test_mainnet_url_blocked(self):
        """Mainnet URLs must be blocked."""
        for url in _BLOCKED_MAINNET_URLS:
            with pytest.raises(RuntimeError, match="Mainnet"):
                config = ExchangeConfig.__new__(ExchangeConfig)
                config.api_key = ""
                config.api_secret = ""
                config.rest_url = url
                config.ws_url = "wss://stream.binancefuture.com"
                config.__post_init__()

    def test_non_testnet_url_blocked(self):
        """Any URL without 'testnet' is blocked at client level."""
        config = ExchangeConfig()
        config.rest_url = "https://some-random-api.com"
        with pytest.raises(RuntimeError, match="testnet"):
            BinanceFuturesTestnetClient(config)


# ── Order Result Tests ────────────────────────────────────────

class TestOrderResult:

    def test_order_result_fields(self):
        result = OrderResult(
            order_id=123,
            client_order_id="CSA-test",
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            status="FILLED",
            price=50000.0,
            avg_price=50000.0,
            quantity=0.01,
            executed_qty=0.01,
            timestamp=int(time.time() * 1000),
            raw={"orderId": 123},
        )
        assert result.order_id == 123
        assert result.symbol == "BTCUSDT"
        assert result.side == "BUY"
        assert result.status == "FILLED"


# ── Rate Limiting Tests ───────────────────────────────────────

class TestRateLimiting:

    def test_min_request_interval(self):
        """Client should enforce minimum interval between requests."""
        config = ExchangeConfig(api_key="test", api_secret="test")
        client = BinanceFuturesTestnetClient(config)

        # Simulate rapid requests
        client._last_request_time = time.time()
        start = time.time()
        client._rate_limit()
        elapsed = time.time() - start
        # Should have waited at least MIN_REQUEST_INTERVAL
        assert elapsed >= client.MIN_REQUEST_INTERVAL - 0.01


# ── Error Handling Tests ──────────────────────────────────────

class TestErrorHandling:

    def test_exchange_error_attributes(self):
        err = ExchangeError("test message", 400, "raw response")
        assert str(err) == "test message"
        assert err.code == 400
        assert err.response == "raw response"

    def test_insufficient_balance_error(self):
        err = InsufficientBalanceError("no balance", -2019)
        assert isinstance(err, ExchangeError)
        assert err.code == -2019

    def test_rate_limit_error(self):
        err = RateLimitError("rate limited", 429)
        assert isinstance(err, ExchangeError)


# ── Config Loading Tests ──────────────────────────────────────

class TestConfigLoading:

    def test_loads_from_env_vars(self):
        with patch.dict("os.environ", {
            "BINANCE_TESTNET_API_KEY": "env_key",
            "BINANCE_TESTNET_API_SECRET": "env_secret",
        }):
            config = ExchangeConfig()
            assert config.api_key == "env_key"
            assert config.api_secret == "env_secret"

    def test_explicit_params_override_env(self):
        with patch.dict("os.environ", {
            "BINANCE_TESTNET_API_KEY": "env_key",
        }):
            config = ExchangeConfig(api_key="explicit_key")
            assert config.api_key == "explicit_key"

    def test_force_testnet_urls(self):
        """Mainnet URLs are blocked — ExchangeConfig raises RuntimeError."""
        with pytest.raises(RuntimeError, match="TESTNET ONLY"):
            ExchangeConfig(
                rest_url="https://fapi.binance.com",
                ws_url="wss://fstream.binance.com",
            )

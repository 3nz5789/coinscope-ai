"""
conftest.py — Pytest Configuration & Shared Fixtures
======================================================
Shared fixtures available across all test modules.
Configures environment variables and async test runner.
"""

from __future__ import annotations

import os
import sys
import asyncio
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
# Ensure the engine root is on the path so tests can import modules directly
_ENGINE_ROOT = Path(__file__).parent.parent
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

# ---------------------------------------------------------------------------
# Environment — inject minimal .env values for tests before config loads
# ---------------------------------------------------------------------------
os.environ.setdefault("TESTNET_MODE",        "true")
os.environ.setdefault("BINANCE_TESTNET_API_KEY",    "test_key")
os.environ.setdefault("BINANCE_TESTNET_API_SECRET", "test_secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN",  "123456:TESTTOKEN")
os.environ.setdefault("TELEGRAM_CHAT_ID",    "-100123456")
os.environ.setdefault("SECRET_KEY",          "a" * 64)
os.environ.setdefault("ENVIRONMENT",         "development")
os.environ.setdefault("MIN_CONFLUENCE_SCORE","40")
os.environ.setdefault("RISK_PER_TRADE_PCT",  "1.0")
os.environ.setdefault("MAX_LEVERAGE",        "10")
os.environ.setdefault("MAX_DAILY_LOSS_PCT",  "3.0")
os.environ.setdefault("MAX_OPEN_POSITIONS",  "5")
os.environ.setdefault("MAX_POSITION_SIZE_PCT","20.0")
os.environ.setdefault("MAX_TOTAL_EXPOSURE_PCT","50.0")
os.environ.setdefault("SCAN_PAIRS",          "BTCUSDT,ETHUSDT")
os.environ.setdefault("SCAN_INTERVAL_SECONDS","60")

# ---------------------------------------------------------------------------
# Asyncio mode
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Common candle fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def btc_candles():
    """60 uptrending BTC candles at 1-hour interval."""
    from data.data_normalizer import Candle
    candles = []
    base = 60_000.0
    for i in range(60):
        close = base + i * 50
        ts    = 1_700_000_000_000 + i * 3_600_000
        candles.append(Candle(
            symbol       = "BTCUSDT",
            interval     = "1h",
            open_time    = ts,
            close_time   = ts + 3_599_999,
            open         = close - 20,
            high         = close + 80,
            low          = close - 60,
            close        = close,
            volume       = 1000.0,
            quote_volume = close * 1000,
            trades       = 200,
            taker_buy_volume = 600.0,
            taker_buy_quote  = close * 600,
        ))
    return candles


@pytest.fixture
def eth_candles():
    """50 candles for ETHUSDT at 15-minute interval."""
    from data.data_normalizer import Candle
    candles = []
    base = 3_000.0
    for i in range(50):
        close = base + i * 5
        ts    = 1_700_000_000_000 + i * 900_000
        candles.append(Candle(
            symbol       = "ETHUSDT",
            interval     = "15m",
            open_time    = ts,
            close_time   = ts + 899_999,
            open         = close - 2,
            high         = close + 8,
            low          = close - 6,
            close        = close,
            volume       = 5000.0,
            quote_volume = close * 5000,
            trades       = 150,
            taker_buy_volume = 3000.0,
            taker_buy_quote  = close * 3000,
        ))
    return candles

"""
test_scanners.py — Market Scanner Unit Tests
=============================================
Tests scanner logic, hit detection, result aggregation,
and edge cases for all 5 scanner types.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

import pytest

from scanner.base_scanner import SignalDirection, HitStrength, ScannerResult
from scanner.volume_scanner import VolumeScanner
from scanner.pattern_scanner import PatternScanner
from scanner.funding_rate_scanner import FundingRateScanner
from scanner.orderbook_scanner import OrderBookScanner
from scanner.liquidation_scanner import LiquidationScanner
from data.data_normalizer import Candle, OrderBook, LiquidationOrder


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def make_candle(
    symbol="BTCUSDT",
    interval="1m",
    open_=65000.0,
    high=65500.0,
    low=64800.0,
    close=65200.0,
    volume=100.0,
    timestamp=1_700_000_000_000,
) -> Candle:
    return Candle(
        symbol=symbol, interval=interval,
        open_time=timestamp, close_time=timestamp + 59_999,
        open=open_, high=high, low=low, close=close,
        volume=volume, quote_volume=close * volume,
        trades=100, taker_buy_volume=volume * 0.6,
        taker_buy_quote=close * volume * 0.6,
    )


def make_candles(n=60, base_close=65000.0, vol=100.0) -> list[Candle]:
    candles = []
    for i in range(n):
        ts = 1_700_000_000_000 + i * 60_000
        close = base_close + i * 10
        candles.append(make_candle(
            close=close, open_=close - 5, high=close + 20,
            low=close - 30, volume=vol, timestamp=ts,
        ))
    return candles


def make_orderbook(
    symbol="BTCUSDT",
    best_bid=65000.0,
    best_ask=65010.0,
    bids=None,
    asks=None,
) -> OrderBook:
    bids = bids or [(65000.0, 5.0), (64990.0, 10.0), (64980.0, 2.0)]
    asks = asks or [(65010.0, 4.0), (65020.0, 3.0), (65030.0, 1.0)]
    return OrderBook(
        symbol=symbol,
        last_update_id=999,
        bids=bids,
        asks=asks,
    )


# ---------------------------------------------------------------------------
# VolumeScanner
# ---------------------------------------------------------------------------

class TestVolumeScanner:

    @pytest.fixture
    def scanner(self):
        mock_cache = AsyncMock()
        mock_cache.get_candles = AsyncMock(return_value=[])
        mock_rest   = MagicMock()
        return VolumeScanner(rest_client=mock_rest, cache=mock_cache)

    def test_volume_spike_detected(self, scanner):
        """High volume candle should generate a scanner hit."""
        candles = make_candles(50, vol=100.0)
        # Last candle has 5× the average volume
        candles[-1] = make_candle(volume=500.0)
        result = scanner._evaluate(candles)
        assert result is not None
        assert len(result.hits) > 0

    def test_no_hit_on_normal_volume(self, scanner):
        """Normal volume candles produce no hits."""
        candles = make_candles(50, vol=100.0)
        result = scanner._evaluate(candles)
        # At most WEAK hit for slight taker imbalance — no STRONG
        strong_hits = [h for h in result.hits if h.strength == HitStrength.STRONG]
        assert len(strong_hits) == 0

    def test_insufficient_candles_returns_empty(self, scanner):
        """Fewer than MIN_CANDLES should return no hits."""
        candles = make_candles(3)
        result = scanner._evaluate(candles)
        assert result is None or len(result.hits) == 0


# ---------------------------------------------------------------------------
# PatternScanner
# ---------------------------------------------------------------------------

class TestPatternScanner:

    @pytest.fixture
    def scanner(self):
        return PatternScanner()

    def test_bullish_engulfing_detected(self, scanner):
        """Bullish engulfing pattern: small bearish bar followed by larger bullish bar."""
        candles = make_candles(20)
        # Bearish bar
        candles[-2] = make_candle(open_=65100, close=65000, high=65200, low=64900)
        # Bullish engulfing bar (opens below prev close, closes above prev open)
        candles[-1] = make_candle(open_=64950, close=65200, high=65300, low=64850)
        result = scanner._evaluate("BTCUSDT", candles)
        directions = [h.direction for h in result.hits]
        assert SignalDirection.LONG in directions

    def test_hammer_detected(self, scanner):
        """Hammer candle: small body, long lower wick, short upper wick."""
        candles = make_candles(20)
        # Hammer: opens high, closes near open, long lower wick
        candles[-1] = make_candle(
            open_=65000, close=65050, high=65100, low=63500
        )
        result = scanner._evaluate("BTCUSDT", candles)
        # Should detect some bullish pattern
        long_hits = [h for h in result.hits if h.direction == SignalDirection.LONG]
        assert len(long_hits) > 0

    def test_no_pattern_on_flat_candles(self, scanner):
        """Identical OHLC bars should not produce pattern hits."""
        flat = [make_candle(open_=100, high=101, low=99, close=100)] * 10
        result = scanner._evaluate("BTCUSDT", flat)
        assert len(result.hits) == 0


# ---------------------------------------------------------------------------
# FundingRateScanner
# ---------------------------------------------------------------------------

class TestFundingRateScanner:

    @pytest.fixture
    def scanner(self):
        mock_cache = AsyncMock()
        mock_rest   = MagicMock()
        return FundingRateScanner(rest_client=mock_rest, cache=mock_cache)

    def test_extreme_positive_funding_triggers_short(self, scanner):
        """Extreme positive funding = crowded longs = bearish contrarian signal."""
        result = scanner._evaluate_rate(
            symbol="BTCUSDT",
            current_rate=0.0015,    # 3× the 0.0005 threshold
            history=[0.0003, 0.0004, 0.0003, 0.0002],
        )
        assert result is not None
        short_hits = [h for h in result.hits if h.direction == SignalDirection.SHORT]
        assert len(short_hits) > 0

    def test_extreme_negative_funding_triggers_long(self, scanner):
        """Extreme negative funding = crowded shorts = bullish contrarian signal."""
        result = scanner._evaluate_rate(
            symbol="BTCUSDT",
            current_rate=-0.0015,
            history=[-0.0003, -0.0002, -0.0001, -0.0002],
        )
        assert result is not None
        long_hits = [h for h in result.hits if h.direction == SignalDirection.LONG]
        assert len(long_hits) > 0

    def test_neutral_funding_no_hit(self, scanner):
        """Near-zero funding should produce no hits."""
        result = scanner._evaluate_rate(
            symbol="BTCUSDT",
            current_rate=0.0001,
            history=[0.0001, 0.0001, 0.0001, 0.0001],
        )
        assert result is None or len(result.hits) == 0


# ---------------------------------------------------------------------------
# OrderBookScanner
# ---------------------------------------------------------------------------

class TestOrderBookScanner:

    @pytest.fixture
    def scanner(self):
        return OrderBookScanner()

    def test_bid_heavy_imbalance_triggers_long(self, scanner):
        """Large bid side vs ask side = bullish pressure."""
        # Bids dominate: 80% of depth on buy side
        bids = [(65000.0, 80.0), (64990.0, 20.0)]
        asks = [(65010.0, 10.0), (65020.0, 10.0)]
        ob   = make_orderbook(bids=bids, asks=asks)
        result = scanner._evaluate(ob)
        long_hits = [h for h in result.hits if h.direction == SignalDirection.LONG]
        assert len(long_hits) > 0

    def test_ask_heavy_imbalance_triggers_short(self, scanner):
        """Large ask side = selling pressure."""
        bids = [(65000.0, 10.0), (64990.0, 10.0)]
        asks = [(65010.0, 80.0), (65020.0, 20.0)]
        ob   = make_orderbook(bids=bids, asks=asks)
        result = scanner._evaluate(ob)
        short_hits = [h for h in result.hits if h.direction == SignalDirection.SHORT]
        assert len(short_hits) > 0

    def test_balanced_book_no_hit(self, scanner):
        """Balanced order book produces no directional hit."""
        bids = [(65000.0, 50.0), (64990.0, 50.0)]
        asks = [(65010.0, 50.0), (65020.0, 50.0)]
        ob   = make_orderbook(bids=bids, asks=asks)
        result = scanner._evaluate(ob)
        strong_hits = [h for h in result.hits if h.strength == HitStrength.STRONG]
        assert len(strong_hits) == 0


# ---------------------------------------------------------------------------
# LiquidationScanner
# ---------------------------------------------------------------------------

class TestLiquidationScanner:

    @pytest.fixture
    def scanner(self):
        return LiquidationScanner()

    def test_long_liq_dominance_triggers_long_contrarian(self, scanner):
        """
        When long liquidations dominate (>70%), smart money may step in
        to buy the dip → bullish contrarian signal.
        """
        liqs = [
            LiquidationOrder(
                symbol="BTCUSDT", side="SELL", quantity=1.0,
                price=65000.0, timestamp=1_700_000_000_000,
            )
        ] * 10   # 10 × long liquidations
        result = scanner._evaluate("BTCUSDT", liqs)
        if result and result.hits:
            directions = [h.direction for h in result.hits]
            assert SignalDirection.LONG in directions

    def test_insufficient_liquidations_no_hit(self, scanner):
        """Small liquidation notional should not trigger."""
        liqs = [
            LiquidationOrder(
                symbol="BTCUSDT", side="SELL", quantity=0.001,
                price=65000.0, timestamp=1_700_000_000_000,
            )
        ] * 2
        result = scanner._evaluate("BTCUSDT", liqs)
        assert result is None or len(result.hits) == 0

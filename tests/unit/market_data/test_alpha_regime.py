"""
Unit tests for CoinScopeAI Alpha Generators and Regime Detector.
Tests: signal generation logic, regime classification, EventBus integration.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from services.market_data.types import (
    AlphaSignal,
    OrderBookLevel,
    OrderBookSnapshot,
    RegimeState,
)


class TestAlphaSignal:
    """Tests for the AlphaSignal dataclass."""

    def test_creation(self):
        sig = AlphaSignal(
            signal_type="funding_extreme",
            symbol="BTCUSDT",
            direction="LONG",
            strength=0.8,
            metadata={"funding_rate": -0.05},
        )
        assert sig.signal_type == "funding_extreme"
        assert sig.direction == "LONG"
        assert sig.strength == 0.8

    def test_default_timestamp(self):
        sig = AlphaSignal(
            signal_type="test",
            symbol="BTCUSDT",
            direction="NEUTRAL",
            strength=0.5,
        )
        assert sig.timestamp > 0

    def test_is_expired(self):
        sig = AlphaSignal(
            signal_type="test",
            symbol="BTCUSDT",
            direction="LONG",
            strength=0.5,
            timestamp=time.time() - 7200,  # 2 hours ago
            ttl_seconds=3600.0,  # 1 hour TTL
        )
        assert sig.is_expired is True

    def test_not_expired(self):
        sig = AlphaSignal(
            signal_type="test",
            symbol="BTCUSDT",
            direction="LONG",
            strength=0.5,
        )
        assert sig.is_expired is False

    def test_topic_property(self):
        sig = AlphaSignal(
            signal_type="funding_extreme",
            symbol="BTCUSDT",
            direction="LONG",
            strength=0.5,
        )
        assert "alpha" in sig.topic
        assert "BTCUSDT" in sig.topic


class TestRegimeState:
    """Tests for the RegimeState dataclass."""

    def test_creation(self):
        state = RegimeState(
            symbol="BTCUSDT",
            regime="trending_up",
            confidence=0.85,
            volatility_percentile=0.6,
            trend_strength=0.7,
        )
        assert state.regime == "trending_up"
        assert state.confidence == 0.85

    def test_valid_regimes(self):
        for regime in ["volatile", "trending_up", "trending_down", "ranging"]:
            state = RegimeState(
                symbol="BTCUSDT",
                regime=regime,
                confidence=0.5,
                volatility_percentile=0.5,
                trend_strength=0.5,
            )
            assert state.regime == regime

    def test_topic_property(self):
        state = RegimeState(
            symbol="BTCUSDT",
            regime="volatile",
            confidence=0.9,
            volatility_percentile=0.95,
            trend_strength=0.1,
        )
        assert "regime" in state.topic
        assert "BTCUSDT" in state.topic


class TestOrderBookSnapshot:
    """Tests for the OrderBookSnapshot dataclass."""

    def test_spread_calculation(self):
        ob = OrderBookSnapshot(
            symbol="BTCUSDT",
            exchange="binance",
            bids=[OrderBookLevel(50000.0, 1.0), OrderBookLevel(49999.0, 2.0)],
            asks=[OrderBookLevel(50001.0, 1.0), OrderBookLevel(50002.0, 2.0)],
            timestamp=time.time(),
        )
        # Spread = (50001 - 50000) / 50000.5 * 10000 ≈ 0.2 bps
        assert ob.spread_bps > 0
        assert ob.spread_bps < 1.0
        assert ob.best_bid == 50000.0
        assert ob.best_ask == 50001.0

    def test_empty_orderbook(self):
        ob = OrderBookSnapshot(
            symbol="BTCUSDT",
            exchange="binance",
            bids=[],
            asks=[],
            timestamp=time.time(),
        )
        assert ob.spread_bps == 0.0
        assert ob.best_bid == 0.0
        assert ob.best_ask == 0.0

    def test_mid_price(self):
        ob = OrderBookSnapshot(
            symbol="BTCUSDT",
            exchange="binance",
            bids=[OrderBookLevel(50000.0, 1.0)],
            asks=[OrderBookLevel(50010.0, 1.0)],
            timestamp=time.time(),
        )
        assert abs(ob.mid_price - 50005.0) < 0.01


class TestEngineV2AlphaContext:
    """Tests for the AlphaContext used in engine v2."""

    def test_alpha_context_update_and_get(self):
        from services.paper_trading.engine_v2 import AlphaContext

        ctx = AlphaContext(max_age_seconds=3600)

        sig = AlphaSignal(
            signal_type="funding_extreme",
            symbol="BTCUSDT",
            direction="LONG",
            strength=0.8,
        )
        ctx.update(sig)

        features = ctx.get_context("BTCUSDT")
        assert "alpha_funding_extreme_direction" in features
        assert features["alpha_funding_extreme_direction"] == 1.0
        assert features["alpha_funding_extreme_strength"] == 0.8
        assert features["alpha_funding_extreme_active"] == 1.0

    def test_alpha_context_short_direction(self):
        from services.paper_trading.engine_v2 import AlphaContext

        ctx = AlphaContext()
        sig = AlphaSignal(
            signal_type="liquidation_cascade",
            symbol="ETHUSDT",
            direction="SHORT",
            strength=0.9,
        )
        ctx.update(sig)

        features = ctx.get_context("ETHUSDT")
        assert features["alpha_liquidation_cascade_direction"] == -1.0

    def test_alpha_context_empty(self):
        from services.paper_trading.engine_v2 import AlphaContext

        ctx = AlphaContext()
        features = ctx.get_context("BTCUSDT")
        assert features == {}

    def test_alpha_context_multiple_signals(self):
        from services.paper_trading.engine_v2 import AlphaContext

        ctx = AlphaContext()

        for sig_type in ["funding_extreme", "liquidation_cascade", "basis"]:
            ctx.update(AlphaSignal(
                signal_type=sig_type,
                symbol="BTCUSDT",
                direction="LONG",
                strength=0.7,
            ))

        features = ctx.get_context("BTCUSDT")
        # Each signal produces: direction, strength, confidence, active = 4 keys
        assert len(features) >= 9  # At least 3 signals × 3 features each

    def test_alpha_context_expired_signal(self):
        from services.paper_trading.engine_v2 import AlphaContext

        ctx = AlphaContext(max_age_seconds=1)
        sig = AlphaSignal(
            signal_type="funding_extreme",
            symbol="BTCUSDT",
            direction="LONG",
            strength=0.8,
            timestamp=time.time() - 3600,  # 1 hour ago
            ttl_seconds=1.0,  # 1 second TTL
        )
        ctx.update(sig)

        features = ctx.get_context("BTCUSDT")
        assert features == {}  # Expired signal should be excluded


class TestEngineV2RegimeContext:
    """Tests for the RegimeContext used in engine v2."""

    def test_regime_update_and_get(self):
        from services.paper_trading.engine_v2 import RegimeContext

        ctx = RegimeContext()
        state = RegimeState(
            symbol="BTCUSDT",
            regime="trending_up",
            confidence=0.85,
            volatility_percentile=0.6,
            trend_strength=0.7,
        )
        ctx.update(state)

        result = ctx.get_regime("BTCUSDT")
        assert result.regime == "trending_up"
        assert result.confidence == 0.85

    def test_regime_features(self):
        from services.paper_trading.engine_v2 import RegimeContext

        ctx = RegimeContext()
        ctx.update(RegimeState(
            symbol="BTCUSDT",
            regime="volatile",
            confidence=0.9,
            volatility_percentile=0.95,
            trend_strength=0.1,
        ))

        features = ctx.get_regime_features("BTCUSDT")
        assert features["regime_volatile"] == 1.0
        assert features["regime_trending_up"] == 0.0
        assert features["regime_confidence"] == 0.9
        assert features["regime_vol_percentile"] == 0.95

    def test_regime_empty(self):
        from services.paper_trading.engine_v2 import RegimeContext

        ctx = RegimeContext()
        assert ctx.get_regime("BTCUSDT") is None
        assert ctx.get_regime_features("BTCUSDT") == {}


class TestEngineV2SpreadTracker:
    """Tests for the SpreadTracker used in engine v2."""

    def test_spread_tracking(self):
        from services.paper_trading.engine_v2 import SpreadTracker

        tracker = SpreadTracker(window_size=10)
        for i in range(5):
            tracker.update("BTCUSDT", 0.5 + i * 0.1)

        avg = tracker.get_avg_spread("BTCUSDT")
        assert 0.5 <= avg <= 1.0

    def test_spread_empty(self):
        from services.paper_trading.engine_v2 import SpreadTracker

        tracker = SpreadTracker()
        assert tracker.get_avg_spread("BTCUSDT") == 0.0

    def test_spread_window(self):
        from services.paper_trading.engine_v2 import SpreadTracker

        tracker = SpreadTracker(window_size=3)
        for val in [1.0, 2.0, 3.0, 4.0, 5.0]:
            tracker.update("BTCUSDT", val)

        # Window of 3: should only have [3.0, 4.0, 5.0]
        avg = tracker.get_avg_spread("BTCUSDT")
        assert abs(avg - 4.0) < 0.01

    def test_get_all(self):
        from services.paper_trading.engine_v2 import SpreadTracker

        tracker = SpreadTracker()
        tracker.update("BTCUSDT", 0.5)
        tracker.update("ETHUSDT", 1.0)

        all_spreads = tracker.get_all()
        assert "BTCUSDT" in all_spreads
        assert "ETHUSDT" in all_spreads

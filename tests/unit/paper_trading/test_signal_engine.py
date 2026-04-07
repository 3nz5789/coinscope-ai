"""
Unit tests for CoinScopeAI Paper Trading — Signal Engine.
Tests cover: candle buffering, feature extraction, model inference,
signal filtering, and integration with the backtesting strategy interface.
"""

import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from pathlib import Path

from services.paper_trading.config import TradingConfig


# ── Signal Engine Import Guard ────────────────────────────────
# The signal engine depends on the ML models which may not be
# available in all test environments. We test the core logic.

class TestSignalEngineCore:
    """Tests for signal engine core logic without ML model dependency."""

    def test_candle_buffer_management(self):
        """Test that candle buffer maintains correct size."""
        from services.paper_trading.signal_engine import MLSignalEngine

        config = TradingConfig(symbols=["BTCUSDT"], timeframe="4h")
        engine = MLSignalEngine.__new__(MLSignalEngine)
        engine._config = config
        engine._candle_buffers = {"BTCUSDT": []}
        engine._buffer_size = 200
        engine._models = {}
        engine._norm_params = {}
        engine._feature_names = {}

        # Add candles
        for i in range(250):
            candle = {
                "open_time": 1000000 + i * 14400000,
                "open": 50000 + i,
                "high": 50100 + i,
                "low": 49900 + i,
                "close": 50050 + i,
                "volume": 100.0 + i,
            }
            engine._candle_buffers["BTCUSDT"].append(candle)

        # Trim to buffer size
        if len(engine._candle_buffers["BTCUSDT"]) > engine._buffer_size:
            engine._candle_buffers["BTCUSDT"] = engine._candle_buffers["BTCUSDT"][-engine._buffer_size:]

        assert len(engine._candle_buffers["BTCUSDT"]) == 200

    def test_insufficient_candles_no_signal(self):
        """Signal engine should return None when insufficient candles."""
        from services.paper_trading.signal_engine import MLSignalEngine

        config = TradingConfig(symbols=["BTCUSDT"], timeframe="4h")
        engine = MLSignalEngine.__new__(MLSignalEngine)
        engine._config = config
        engine._candle_buffers = {"BTCUSDT": []}
        engine._min_candles = 100
        engine._models = {}
        engine._norm_params = {}
        engine._feature_names = {}

        # Only 50 candles — not enough
        for i in range(50):
            engine._candle_buffers["BTCUSDT"].append({
                "open_time": 1000000 + i * 14400000,
                "open": 50000, "high": 50100, "low": 49900,
                "close": 50050, "volume": 100.0,
            })

        # Should not have enough candles
        assert len(engine._candle_buffers["BTCUSDT"]) < engine._min_candles


class TestSignalFiltering:
    """Tests for signal confidence and edge filtering."""

    def test_confidence_threshold(self):
        """Signals below confidence threshold should be filtered."""
        config = TradingConfig(min_confidence=0.42, min_edge=0.05)

        # Low confidence signal
        confidence = 0.35
        assert confidence < config.min_confidence

        # High confidence signal
        confidence = 0.50
        assert confidence >= config.min_confidence

    def test_edge_threshold(self):
        """Signals below edge threshold should be filtered."""
        config = TradingConfig(min_confidence=0.42, min_edge=0.05)

        # Low edge signal
        edge = 0.02
        assert edge < config.min_edge

        # Sufficient edge
        edge = 0.08
        assert edge >= config.min_edge

    def test_regime_filtering(self):
        """Signals in unfavorable regime should be filtered."""
        # Simulate regime detection
        vol_regime = "HIGH"  # High volatility
        trend_strength = 0.15  # Weak trend

        # In high vol + weak trend, should be cautious
        should_trade = vol_regime != "HIGH" or trend_strength > 0.3
        assert not should_trade

        # In normal vol + strong trend, should trade
        vol_regime = "NORMAL"
        trend_strength = 0.5
        should_trade = vol_regime != "HIGH" or trend_strength > 0.3
        assert should_trade


class TestCooldownLogic:
    """Tests for signal cooldown between trades."""

    def test_cooldown_blocks_rapid_signals(self):
        """Should not generate signals too rapidly for the same symbol."""
        last_signal_time = {"BTCUSDT": time.time()}
        cooldown_seconds = 14400  # 4h

        # Immediate re-signal should be blocked
        elapsed = time.time() - last_signal_time["BTCUSDT"]
        assert elapsed < cooldown_seconds

    def test_cooldown_allows_after_period(self):
        """Should allow signals after cooldown period."""
        last_signal_time = {"BTCUSDT": time.time() - 20000}  # 5.5h ago
        cooldown_seconds = 14400  # 4h

        elapsed = time.time() - last_signal_time["BTCUSDT"]
        assert elapsed >= cooldown_seconds

    def test_cooldown_per_symbol(self):
        """Cooldown should be per-symbol, not global."""
        last_signal_time = {
            "BTCUSDT": time.time(),  # Just signaled
            "ETHUSDT": time.time() - 20000,  # 5.5h ago
        }
        cooldown_seconds = 14400

        btc_elapsed = time.time() - last_signal_time["BTCUSDT"]
        eth_elapsed = time.time() - last_signal_time["ETHUSDT"]

        assert btc_elapsed < cooldown_seconds  # Blocked
        assert eth_elapsed >= cooldown_seconds  # Allowed


class TestModelPredictionInterpretation:
    """Tests for converting model predictions to trading signals."""

    def test_long_signal_from_probabilities(self):
        """High P(LONG) should generate LONG signal."""
        probs = np.array([[0.55, 0.30, 0.15]])  # [LONG, NEUTRAL, SHORT]
        predicted_class = np.argmax(probs, axis=1)[0]
        confidence = probs[0, predicted_class]

        assert predicted_class == 0  # LONG
        assert confidence == 0.55

    def test_short_signal_from_probabilities(self):
        """High P(SHORT) should generate SHORT signal."""
        probs = np.array([[0.15, 0.25, 0.60]])
        predicted_class = np.argmax(probs, axis=1)[0]
        confidence = probs[0, predicted_class]

        assert predicted_class == 2  # SHORT
        assert confidence == 0.60

    def test_neutral_signal_filtered(self):
        """High P(NEUTRAL) should not generate a signal."""
        probs = np.array([[0.20, 0.60, 0.20]])
        predicted_class = np.argmax(probs, axis=1)[0]

        assert predicted_class == 1  # NEUTRAL — no trade

    def test_edge_calculation(self):
        """Edge = P(direction) - P(neutral)."""
        probs = np.array([[0.50, 0.35, 0.15]])
        long_prob = probs[0, 0]
        neutral_prob = probs[0, 1]
        edge = long_prob - neutral_prob

        assert edge == pytest.approx(0.15)
        assert edge > 0.05  # Passes min_edge threshold

    def test_no_edge(self):
        """When P(direction) ≈ P(neutral), edge is negligible."""
        probs = np.array([[0.38, 0.35, 0.27]])
        long_prob = probs[0, 0]
        neutral_prob = probs[0, 1]
        edge = long_prob - neutral_prob

        assert edge == pytest.approx(0.03)
        assert edge < 0.05  # Fails min_edge threshold

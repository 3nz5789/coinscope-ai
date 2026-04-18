"""
test_risk.py — Risk Management Layer Tests
==========================================
Tests position sizing, exposure tracking, correlation analysis,
and circuit breaker logic.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from scanner.base_scanner import SignalDirection
from signals.entry_exit_calculator import TradeSetup
from risk.position_sizer import PositionSizer, PositionSize
from risk.exposure_tracker import ExposureTracker
from risk.correlation_analyzer import CorrelationAnalyzer
from risk.circuit_breaker import CircuitBreaker, BreakerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_valid_setup(
    symbol:    str = "BTCUSDT",
    direction: SignalDirection = SignalDirection.LONG,
    entry:     float = 65_000.0,
    sl:        float = 64_000.0,
    tp2:       float = 67_000.0,
) -> TradeSetup:
    sl_dist  = abs(entry - sl)
    tp2_dist = abs(tp2 - entry)
    return TradeSetup(
        symbol       = symbol,
        direction    = direction,
        signal_score = 75.0,
        entry        = entry,
        stop_loss    = sl,
        tp1          = entry + sl_dist,
        tp2          = tp2,
        tp3          = entry + sl_dist * 3,
        risk_pct     = sl_dist / entry * 100,
        rr_ratio_tp2 = tp2_dist / sl_dist,
        rr_ratio_tp3 = (sl_dist * 3) / sl_dist,
        atr          = sl_dist / 1.5,
        atr_pct      = (sl_dist / 1.5) / entry * 100,
    )


# ---------------------------------------------------------------------------
# PositionSizer
# ---------------------------------------------------------------------------

class TestPositionSizer:

    @pytest.fixture
    def sizer(self):
        return PositionSizer(
            risk_per_trade_pct = 1.0,
            max_position_pct   = 20.0,
            max_leverage       = 10,
            tick_size          = 0.001,
        )

    def test_basic_position_size(self, sizer):
        setup = make_valid_setup()
        pos   = sizer.calculate(setup, balance=10_000.0)
        assert pos.valid
        assert pos.qty     > 0
        assert pos.notional > 0
        assert pos.risk_usdt > 0

    def test_risk_is_1pct_of_balance(self, sizer):
        balance = 10_000.0
        setup   = make_valid_setup()
        pos     = sizer.calculate(setup, balance=balance)
        # Risk should be approx 1% of balance = $100
        assert pos.risk_usdt == pytest.approx(100.0, rel=0.15)

    def test_notional_capped_at_max_position_pct(self, sizer):
        """Tiny SL distance would produce enormous qty — must be capped."""
        setup = make_valid_setup(sl=64_999.0)  # 1 USDT SL
        pos   = sizer.calculate(setup, balance=10_000.0)
        assert pos.notional <= 10_000.0 * 0.20 + 1  # max 20% of balance

    def test_invalid_setup_returns_invalid_position(self, sizer):
        setup         = make_valid_setup()
        setup.valid   = False
        setup.invalid_reason = "Test invalid"
        pos = sizer.calculate(setup, balance=10_000.0)
        assert pos.valid is False

    def test_zero_balance_returns_invalid(self, sizer):
        setup = make_valid_setup()
        pos   = sizer.calculate(setup, balance=0.0)
        assert pos.valid is False

    def test_kelly_method_returns_valid(self, sizer):
        sizer._method = "KELLY"
        setup = make_valid_setup()
        pos   = sizer.calculate(setup, balance=10_000.0, win_rate=0.55, avg_rr=2.0)
        assert pos.valid
        assert pos.method == "KELLY"


# ---------------------------------------------------------------------------
# ExposureTracker
# ---------------------------------------------------------------------------

class TestExposureTracker:

    @pytest.fixture
    def tracker(self):
        return ExposureTracker(balance=10_000.0)

    @pytest.mark.asyncio
    async def test_open_and_close_position(self, tracker):
        ok = await tracker.open_position("BTCUSDT", SignalDirection.LONG, qty=0.01, entry=65_000)
        assert ok
        assert tracker.position_count == 1
        pnl = await tracker.close_position("BTCUSDT", exit_price=66_000)
        assert pnl == pytest.approx(10.0, rel=0.01)
        assert tracker.position_count == 0

    @pytest.mark.asyncio
    async def test_unrealised_pnl_long(self, tracker):
        await tracker.open_position("BTCUSDT", SignalDirection.LONG, qty=0.01, entry=65_000)
        await tracker.update_mark_price("BTCUSDT", 66_000)
        assert tracker.unrealised_pnl == pytest.approx(10.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_unrealised_pnl_short(self, tracker):
        await tracker.open_position("ETHUSDT", SignalDirection.SHORT, qty=1.0, entry=3_000)
        await tracker.update_mark_price("ETHUSDT", 2_900)
        assert tracker.unrealised_pnl == pytest.approx(100.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_daily_loss_pct_negative_on_loss(self, tracker):
        await tracker.open_position("BTCUSDT", SignalDirection.LONG, qty=0.1, entry=65_000)
        await tracker.close_position("BTCUSDT", exit_price=64_000)  # -$100 loss
        assert tracker.daily_loss_pct < 0

    @pytest.mark.asyncio
    async def test_duplicate_position_rejected(self, tracker):
        await tracker.open_position("BTCUSDT", SignalDirection.LONG, qty=0.01, entry=65_000)
        ok2 = await tracker.open_position("BTCUSDT", SignalDirection.LONG, qty=0.01, entry=65_000)
        assert ok2 is False
        assert tracker.position_count == 1

    @pytest.mark.asyncio
    async def test_snapshot_structure(self, tracker):
        snap = tracker.snapshot()
        assert "balance"          in snap
        assert "position_count"   in snap
        assert "total_notional"   in snap
        assert "daily_loss_pct"   in snap
        assert "positions"        in snap


# ---------------------------------------------------------------------------
# CorrelationAnalyzer
# ---------------------------------------------------------------------------

class TestCorrelationAnalyzer:

    @pytest.fixture
    def analyzer(self):
        return CorrelationAnalyzer(lookback=30, threshold=0.80)

    def test_perfect_correlation(self, analyzer):
        prices = [float(i) for i in range(1, 51)]
        analyzer.update_prices("BTCUSDT", prices)
        analyzer.update_prices("ETHUSDT", prices)  # identical series
        r = analyzer.pearson("BTCUSDT", "ETHUSDT")
        assert r is not None
        assert r == pytest.approx(1.0, abs=0.01)

    def test_inverse_correlation(self, analyzer):
        prices_up   = [float(i) for i in range(1, 51)]
        prices_down = [float(50 - i) for i in range(50)]
        analyzer.update_prices("BTCUSDT", prices_up)
        analyzer.update_prices("ETHUSDT", prices_down)
        r = analyzer.pearson("BTCUSDT", "ETHUSDT")
        assert r is not None
        assert r < -0.9

    def test_insufficient_data_returns_none(self, analyzer):
        analyzer.update_prices("BTCUSDT", [100.0, 101.0])
        analyzer.update_prices("ETHUSDT", [50.0, 50.5])
        r = analyzer.pearson("BTCUSDT", "ETHUSDT")
        assert r is None

    def test_safety_gate_blocks_correlated_pair(self, analyzer):
        prices = [float(i) for i in range(1, 51)]
        analyzer.update_prices("BTCUSDT", prices)
        analyzer.update_prices("ETHUSDT", prices)  # r ≈ 1.0

        mock_pos = MagicMock()
        mock_pos.direction = SignalDirection.LONG
        open_positions = {"BTCUSDT": mock_pos}

        safe, reason = analyzer.is_safe_to_add(
            "ETHUSDT", SignalDirection.LONG, open_positions
        )
        assert safe is False
        assert "correlated" in reason.lower()


# ---------------------------------------------------------------------------
# CircuitBreaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    def test_initial_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == BreakerState.CLOSED
        assert cb.is_closed

    def test_trip_on_daily_loss_exceeded(self):
        cb = CircuitBreaker(max_daily_loss=2.0)
        result = cb.check(daily_loss_pct=-2.5)
        assert result is False
        assert cb.is_open

    def test_trip_on_drawdown_exceeded(self):
        cb = CircuitBreaker(max_drawdown=5.0)
        result = cb.check(drawdown_pct=6.0)
        assert result is False
        assert cb.is_open

    def test_trip_on_consecutive_losses(self):
        cb = CircuitBreaker(max_consec_loss=3)
        result = cb.check(consecutive_losses=4)
        assert result is False
        assert cb.is_open

    def test_manual_trip_and_reset(self):
        cb = CircuitBreaker()
        cb.trip("Manual test halt")
        assert cb.is_open
        cb.reset()
        assert cb.is_closed

    def test_auto_reset_after_cooldown(self):
        cb = CircuitBreaker(reset_after_s=0.1)
        cb.trip("Test auto-reset")
        assert cb.is_open
        time.sleep(0.15)
        # is_open property calls _maybe_auto_reset
        assert cb.is_closed

    def test_normal_conditions_pass(self):
        cb = CircuitBreaker(max_daily_loss=2.0, max_drawdown=5.0, max_consec_loss=5)
        result = cb.check(daily_loss_pct=-0.5, drawdown_pct=1.0, consecutive_losses=2)
        assert result is True
        assert cb.is_closed

    def test_trip_count_increments(self):
        cb = CircuitBreaker()
        assert cb.trip_count == 0
        cb.trip("First trip")
        cb.reset()
        cb.trip("Second trip")
        assert cb.trip_count == 2

    def test_rapid_loss_triggers_breaker(self):
        cb = CircuitBreaker(rapid_loss_pct=1.0, rapid_window_s=60.0)
        cb.record_trade_result(-0.6)
        cb.record_trade_result(-0.6)
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_async_on_trip_callback_called(self):
        callback = AsyncMock()
        cb = CircuitBreaker(on_trip=callback, max_daily_loss=1.0)
        cb.check(daily_loss_pct=-2.0)
        await asyncio.sleep(0.05)   # let the create_task run
        callback.assert_called_once()

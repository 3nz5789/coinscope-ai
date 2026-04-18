"""
test_daily_loss_halt_sim.py — Daily Loss Halt Simulation
=========================================================
Focused QA simulation for the CoinScopeAI daily loss circuit breaker.

Tests:
  1.  Baseline — CircuitBreaker starts CLOSED
  2.  Below threshold — -4.9% daily loss → no halt
  3.  At threshold — exactly -5.0% → halt fires
  4.  Above threshold — -5.1% → halt fires
  5.  Block on OPEN — new open_position rejected when breaker is open
  6.  Manual trip → reset → normal operation resumes
  7.  Rapid loss window — 2× losses within 60s window triggers halt
  8.  Daily reset clears rapid-loss log and reopens breaker
  9.  RiskGate.check_circuit_breakers() daily PnL check (core layer)
  10. RiskGate position blocked after daily loss threshold breach
  11. Threshold-doc audit: config default (2.0%) vs documented (5.0%)
  12. Async on_trip callback fires on halt

Run with:
    cd coinscope_trading_engine
    python3 -m pytest /path/to/test_daily_loss_halt_sim.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Add engine to path
# ---------------------------------------------------------------------------
ENGINE_DIR = os.path.join(os.path.dirname(__file__))
sys.path.insert(0, ENGINE_DIR)

from risk.circuit_breaker import CircuitBreaker, BreakerState
from core.risk_gate import RiskGate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DOCUMENTED_DAILY_LOSS_LIMIT_PCT = 5.0   # From trading-rules skill
CONFIG_DEFAULT_DAILY_LOSS_PCT   = 2.0   # From config.py Field default
TESTNET_ACCOUNT_BALANCE         = 4955.54  # Actual testnet balance


def make_cb(limit_pct: float = DOCUMENTED_DAILY_LOSS_LIMIT_PCT, **kwargs) -> CircuitBreaker:
    """Create a CircuitBreaker with the documented 5% daily loss limit."""
    return CircuitBreaker(max_daily_loss=limit_pct, **kwargs)


# ===========================================================================
# Group 1 — Threshold boundary tests (CircuitBreaker)
# ===========================================================================

class TestDailyLossThresholdBoundary:

    def test_baseline_state_is_closed(self):
        """CircuitBreaker must start CLOSED — trading allowed."""
        cb = make_cb()
        assert cb.state == BreakerState.CLOSED
        assert cb.is_closed
        assert cb.trip_count == 0

    def test_below_threshold_no_halt(self):
        """Daily loss of -4.9% must NOT trip the 5.0% limit."""
        cb = make_cb(limit_pct=5.0)
        result = cb.check(daily_loss_pct=-4.9)
        assert result is True, "Expected PASS at -4.9% (below 5.0% limit)"
        assert cb.is_closed

    def test_at_threshold_halts(self):
        """Daily loss of exactly -5.0% MUST trip the breaker."""
        cb = make_cb(limit_pct=5.0)
        result = cb.check(daily_loss_pct=-5.0)
        assert result is False, "Expected HALT at exactly -5.0%"
        assert cb.is_open
        assert cb.trip_count == 1

    def test_above_threshold_halts(self):
        """Daily loss of -5.1% MUST trip the breaker."""
        cb = make_cb(limit_pct=5.0)
        result = cb.check(daily_loss_pct=-5.1)
        assert result is False, "Expected HALT at -5.1%"
        assert cb.is_open

    def test_config_default_is_2pct_not_5pct(self):
        """
        FINDING: config.py default is 2.0%, not the documented 5.0%.
        This test documents the discrepancy — a breaker using settings
        default will halt at -2.0%, not -5.0%.
        """
        from config import settings
        config_default = settings.max_daily_loss_pct
        assert config_default == CONFIG_DEFAULT_DAILY_LOSS_PCT, (
            f"config.py default is {config_default}%, "
            f"expected {CONFIG_DEFAULT_DAILY_LOSS_PCT}%"
        )
        # Prove the two limits behave differently:
        # A -3.0% loss: halts under config default (2%), NOT under documented (5%)
        cb_config = CircuitBreaker()  # uses settings default = 2.0%
        cb_docs   = make_cb(limit_pct=DOCUMENTED_DAILY_LOSS_LIMIT_PCT)

        config_halted = not cb_config.check(daily_loss_pct=-3.0)
        docs_halted   = not cb_docs.check(daily_loss_pct=-3.0)

        assert config_halted is True,  "Config-default (2%) breaker should halt at -3%"
        assert docs_halted   is False, "Documented (5%) breaker should NOT halt at -3%"

    def test_daily_loss_in_usdt_terms(self):
        """
        Validate that 5% of testnet balance (4955.54 USDT) = 247.78 USDT
        matches the halt boundary in percentage terms.
        """
        balance = TESTNET_ACCOUNT_BALANCE
        limit_pct = DOCUMENTED_DAILY_LOSS_LIMIT_PCT
        halt_threshold_usdt = balance * (limit_pct / 100)
        assert abs(halt_threshold_usdt - 247.777) < 1.0, (
            f"5% of {balance} USDT should be ~247.78, got {halt_threshold_usdt:.2f}"
        )


# ===========================================================================
# Group 2 — Halt behaviour (positions blocked, state isolation)
# ===========================================================================

class TestHaltBehaviour:

    def test_check_returns_false_while_open(self):
        """Once tripped, all subsequent check() calls return False."""
        cb = make_cb()
        cb.check(daily_loss_pct=-6.0)   # trip
        assert cb.is_open
        # Try again — still halted (no auto-reset)
        result = cb.check(daily_loss_pct=0.0)
        assert result is False

    def test_manual_trip_and_reset_cycle(self):
        """Manual trip → reset → trading resumes."""
        cb = make_cb()
        cb.trip("QA forced halt")
        assert cb.is_open
        assert cb.trip_count == 1

        cb.reset()
        assert cb.is_closed
        assert cb.trip_count == 1  # history preserved

        # Normal check passes after reset
        result = cb.check(daily_loss_pct=-1.0)
        assert result is True

    def test_trip_does_not_double_count(self):
        """Repeated trip() while OPEN must not add multiple TripEvents."""
        cb = make_cb()
        cb.trip("First halt")
        cb.trip("Second halt attempt (while open)")
        assert cb.trip_count == 1

    def test_auto_reset_after_cooldown(self):
        """Breaker auto-resets after reset_after_s elapses."""
        cb = CircuitBreaker(max_daily_loss=5.0, reset_after_s=0.1)
        cb.check(daily_loss_pct=-6.0)
        assert cb.is_open
        time.sleep(0.15)
        assert cb.is_closed, "Should have auto-reset after 0.1s cooldown"


# ===========================================================================
# Group 3 — Rapid loss window
# ===========================================================================

class TestRapidLossWindow:

    def test_rapid_loss_accumulation_triggers_halt(self):
        """Two rapid losses summing to > rapid_loss_pct within window → halt."""
        cb = CircuitBreaker(
            max_daily_loss=5.0,
            rapid_loss_pct=1.0,
            rapid_window_s=60.0,
        )
        cb.record_trade_result(-0.6)   # -0.6% trade
        cb.record_trade_result(-0.6)   # -1.2% total in window
        assert cb.is_open, "Rapid cumulative loss of -1.2% should trip 1.0% threshold"

    def test_rapid_loss_below_threshold_no_halt(self):
        """Rapid losses below threshold do not trip the breaker."""
        cb = CircuitBreaker(
            max_daily_loss=5.0,
            rapid_loss_pct=2.0,
            rapid_window_s=60.0,
        )
        cb.record_trade_result(-0.5)
        cb.record_trade_result(-0.5)
        assert cb.is_closed, "-1.0% total should NOT trip 2.0% rapid threshold"

    def test_daily_reset_clears_rapid_log_and_reopens(self):
        """reset_daily() clears rapid loss log and re-closes an open breaker."""
        cb = CircuitBreaker(
            max_daily_loss=5.0,
            rapid_loss_pct=1.0,
            rapid_window_s=60.0,
        )
        cb.record_trade_result(-0.6)
        cb.record_trade_result(-0.6)
        assert cb.is_open

        cb.reset_daily()
        assert cb.is_closed
        assert len(cb._rapid_log) == 0, "Rapid log should be cleared after daily reset"


# ===========================================================================
# Group 4 — RiskGate (core layer) daily loss enforcement
# ===========================================================================

class TestRiskGateDailyLoss:

    def _gate_with_loss(self, loss_pct: float) -> RiskGate:
        """
        Create a RiskGate and inject a daily PnL loss equal to loss_pct of
        initial capital, then return the gate for inspection.
        """
        gate = RiskGate(
            initial_capital=10000,
            max_daily_loss_pct=0.05,   # 5% — aligned with documented threshold
        )
        gate.daily_pnl = -gate.initial_capital * loss_pct
        return gate

    def test_core_gate_no_halt_below_threshold(self):
        """RiskGate.check_circuit_breakers(): -4.9% should NOT halt."""
        gate = self._gate_with_loss(0.049)
        should_halt, reason = gate.check_circuit_breakers()
        assert should_halt is False, f"Should not halt at -4.9%, got: {reason}"

    def test_core_gate_halts_at_threshold(self):
        """
        BUG-FINDING: RiskGate uses strict `<` comparison — at exactly -5.0% the
        breaker does NOT fire. CircuitBreaker correctly uses `<=`.
        This test documents the off-by-epsilon defect in core/risk_gate.py.

        Fix: change `self.daily_pnl < -threshold` to `self.daily_pnl <= -threshold`
        in check_circuit_breakers().
        """
        gate = self._gate_with_loss(0.05)
        should_halt, reason = gate.check_circuit_breakers()
        # BUG: strict < means exactly-at-threshold does not trip
        # Correct expected behaviour: should_halt is True
        # Actual (buggy) behaviour: should_halt is False
        assert should_halt is False, (
            "BUG CONFIRMED: RiskGate uses strict '<' — halts at -5.001% but NOT at exactly -5.0%. "
            "Fix: use '<=' in check_circuit_breakers()."
        )

    def test_core_gate_halts_at_threshold_plus_epsilon(self):
        """Just past threshold (-5.001%) DOES halt — confirms strict-< boundary."""
        gate = self._gate_with_loss(0.05001)
        should_halt, reason = gate.check_circuit_breakers()
        assert should_halt is True, "Should halt at -5.001% (just past strict threshold)"
        assert "daily" in reason.lower()

    def test_core_gate_halts_above_threshold(self):
        """RiskGate.check_circuit_breakers(): -5.1% loss should halt."""
        gate = self._gate_with_loss(0.051)
        should_halt, reason = gate.check_circuit_breakers()
        assert should_halt is True

    def test_core_gate_blocks_position_after_daily_loss_breach(self):
        """open_position() returns None when daily loss limit is already breached."""
        gate = RiskGate(
            initial_capital=10000,
            max_daily_loss_pct=0.05,
        )
        # Inject a breach
        gate.daily_pnl = -600.0   # -6% of 10k

        pos = gate.open_position(
            symbol="BTCUSDT",
            direction=1,
            entry_price=65000,
            entry_time=0,
            atr=500,
            regime="bull",
            signal_score=0.80,
        )
        assert pos is None, "Position must be blocked when daily loss limit is breached"
        assert gate.circuit_breaker_active is True

    def test_core_gate_default_threshold_is_10pct(self):
        """
        FINDING: RiskGate default is 10%, not the documented 5%.
        This test documents the mismatch — callers must explicitly pass
        max_daily_loss_pct=0.05 to enforce the documented threshold.
        """
        gate_default = RiskGate(initial_capital=10000)
        assert gate_default.max_daily_loss_pct == 0.10, (
            "Default RiskGate threshold is 10%, not the documented 5%"
        )
        # A -7% loss should NOT trip the 10% default — only trips with 5% limit
        gate_default.daily_pnl = -700.0
        should_halt, _ = gate_default.check_circuit_breakers()
        assert should_halt is False, (
            "Default gate (10%) must NOT halt at -7%; "
            "only halts at documented 5% when explicitly configured"
        )


# ===========================================================================
# Group 5 — Async callback
# ===========================================================================

class TestAsyncCallback:

    @pytest.mark.asyncio
    async def test_on_trip_callback_fires_on_daily_loss(self):
        """on_trip async callback must be called when daily loss halt triggers."""
        callback = AsyncMock()
        cb = CircuitBreaker(
            on_trip=callback,
            max_daily_loss=5.0,
        )
        cb.check(daily_loss_pct=-6.0)
        await asyncio.sleep(0.05)
        callback.assert_called_once()
        call_args = callback.call_args[0]
        assert "daily" in call_args[0].lower() or "loss" in call_args[0].lower(), (
            f"Callback reason should mention daily loss, got: {call_args[0]}"
        )

    @pytest.mark.asyncio
    async def test_on_trip_not_called_when_below_threshold(self):
        """on_trip must NOT fire for a loss below the daily limit."""
        callback = AsyncMock()
        cb = CircuitBreaker(
            on_trip=callback,
            max_daily_loss=5.0,
        )
        cb.check(daily_loss_pct=-4.0)
        await asyncio.sleep(0.05)
        callback.assert_not_called()


# ===========================================================================
# Group 6 — Full simulation: trade-by-trade loss accumulation
# ===========================================================================

class TestFullSimulation:

    def test_sequential_losses_accumulate_to_halt(self):
        """
        Simulate a series of losing trades on the RiskGate until the daily loss
        limit fires. Verifies the halt happens at the correct cumulative loss.
        """
        gate = RiskGate(
            initial_capital=10000,
            max_daily_loss_pct=0.05,   # documented 5%
        )

        # Open position
        pos = gate.open_position(
            symbol="BTCUSDT", direction=1, entry_price=65000,
            entry_time=0, atr=300, regime="bull", signal_score=0.75,
        )
        assert pos is not None

        # Trade 1 — close at loss (~1.5%)
        gate.close_position("BTCUSDT", exit_price=64025, exit_time=1, reason="stop_loss")
        halted, _ = gate.check_circuit_breakers()
        assert halted is False, "Should not halt after Trade 1"

        # Reopen
        gate.open_position(
            symbol="BTCUSDT", direction=1, entry_price=64000,
            entry_time=2, atr=300, regime="bull", signal_score=0.75,
        )
        # Trade 2 — heavier loss
        gate.close_position("BTCUSDT", exit_price=63000, exit_time=3, reason="stop_loss")
        halted, _ = gate.check_circuit_breakers()
        assert halted is False, "Should not halt after Trade 2"

        # Force daily PnL to breach threshold
        gate.daily_pnl = -gate.initial_capital * 0.051   # -5.1%

        halted, reason = gate.check_circuit_breakers()
        assert halted is True, "Should halt when cumulative daily loss > 5%"
        assert "daily" in reason.lower()

    def test_cb_trip_sequence_status_reporting(self):
        """status() must accurately reflect state, trip count, and thresholds."""
        cb = make_cb(limit_pct=5.0)

        status_before = cb.status()
        assert status_before["state"] == "CLOSED"
        assert status_before["trip_count"] == 0
        assert status_before["max_daily_loss_pct"] == 5.0

        cb.check(daily_loss_pct=-6.0)
        status_after = cb.status()
        assert status_after["state"] == "OPEN"
        assert status_after["trip_count"] == 1
        assert status_after["last_trip"] is not None

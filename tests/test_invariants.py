"""
tests/test_invariants.py — Invariant & Failure-Mode Test Suite
==============================================================

Tests uncertain-state halts, persistence invariants, and failure-mode
behaviour for the CoinScopeAI engine's risk and safety layer.

Scope
-----
  Section 1 — CircuitBreaker state machine invariants
  Section 2 — Halt persistence across instantiation
  Section 3 — Concurrent / re-entrant trip protection
  Section 4 — Boundary conditions at exact thresholds
  Section 5 — Rapid-loss window failure modes
  Section 6 — PositionSizer invalid-input invariants
  Section 7 — Kill-switch / manual-halt propagation
  Section 8 — Auto-reset timing invariants
  Section 9 — Trip history integrity
  Section 10 — Orchestrator scan-loop halt invariants

Run:
    pytest tests/test_invariants.py -v
    pytest tests/test_invariants.py -v -k "CircuitBreaker"
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import guards — skip sections cleanly if modules aren't importable
# ---------------------------------------------------------------------------

try:
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "coinscope_trading_engine"))

    from coinscope_trading_engine.risk.circuit_breaker import (
        CircuitBreaker,
        BreakerState,
        TripEvent,
    )
    CB_AVAILABLE = True
except ImportError:
    CB_AVAILABLE = False

try:
    from coinscope_trading_engine.risk.position_sizer import PositionSizer, PositionSize
    from coinscope_trading_engine.signals.entry_exit_calculator import TradeSetup
    from coinscope_trading_engine.scanner.base_scanner import SignalDirection
    SIZER_AVAILABLE = True
except ImportError:
    SIZER_AVAILABLE = False


# ===========================================================================
# SECTION 1 — CircuitBreaker State Machine Invariants
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestCircuitBreakerStateMachine:
    """
    Invariant: the breaker must only ever be in CLOSED, OPEN, or COOLDOWN.
    Once OPEN, trading must remain halted until an explicit reset or auto-reset.
    """

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == BreakerState.CLOSED
        assert cb.is_closed
        assert not cb.is_open

    def test_trip_transitions_to_open(self):
        cb = CircuitBreaker()
        cb.trip("test halt")
        assert cb.state == BreakerState.OPEN
        assert cb.is_open
        assert not cb.is_closed

    def test_check_returns_false_when_open(self):
        cb = CircuitBreaker()
        cb.trip("pre-tripped")
        result = cb.check(daily_loss_pct=0.0, drawdown_pct=0.0, consecutive_losses=0)
        assert result is False

    def test_check_returns_true_when_closed_and_healthy(self):
        cb = CircuitBreaker()
        result = cb.check(daily_loss_pct=0.0, drawdown_pct=0.0, consecutive_losses=0)
        assert result is True

    def test_manual_reset_transitions_to_closed(self):
        cb = CircuitBreaker()
        cb.trip("test")
        assert cb.is_open
        cb.reset()
        assert cb.is_closed

    def test_reset_on_closed_breaker_is_idempotent(self):
        cb = CircuitBreaker()
        assert cb.is_closed
        cb.reset()   # should not raise or change state
        assert cb.is_closed

    def test_trip_on_open_breaker_is_idempotent(self):
        """Double-tripping must not duplicate history."""
        cb = CircuitBreaker()
        cb.trip("first")
        cb.trip("second")   # breaker already open
        assert cb.trip_count == 1, "Second trip on open breaker must not add history entry"

    def test_state_never_undefined_after_check(self):
        """After any check call the state is always a valid BreakerState."""
        cb = CircuitBreaker()
        for _ in range(10):
            cb.check(daily_loss_pct=-99.0)
            assert cb.state in (BreakerState.CLOSED, BreakerState.OPEN, BreakerState.COOLDOWN)

    def test_is_open_and_is_closed_are_mutually_exclusive(self):
        cb = CircuitBreaker()
        for _ in range(3):
            cb.trip("x")
            assert not (cb.is_open and cb.is_closed)
            cb.reset()
            assert not (cb.is_open and cb.is_closed)


# ===========================================================================
# SECTION 2 — Halt Persistence (State Survives Re-Instantiation)
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestHaltPersistence:
    """
    Invariant: a tripped breaker's reason and timestamp must survive
    inspection after the trip. Trip history must never be silently cleared.
    """

    def test_trip_reason_survives_status_call(self):
        cb = CircuitBreaker()
        cb.trip("disk I/O failure")
        status = cb.status()
        assert "disk I/O failure" in status["last_trip"]

    def test_trip_history_accumulates_across_reset_cycles(self):
        cb = CircuitBreaker()
        cb.trip("first failure")
        cb.reset()
        cb.trip("second failure")
        assert cb.trip_count == 2

    def test_last_trip_is_most_recent(self):
        cb = CircuitBreaker()
        cb.trip("alpha")
        cb.reset()
        cb.trip("beta")
        assert "beta" in cb.last_trip.reason

    def test_no_trip_means_last_trip_is_none(self):
        cb = CircuitBreaker()
        assert cb.last_trip is None

    def test_trip_event_records_all_metrics(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        cb.check(daily_loss_pct=-6.0, drawdown_pct=3.0, consecutive_losses=2)
        assert cb.last_trip is not None
        assert cb.last_trip.daily_loss_pct == -6.0
        assert cb.last_trip.drawdown_pct == 3.0
        assert cb.last_trip.consecutive_losses == 2

    def test_trip_event_has_valid_timestamp(self):
        from datetime import datetime, timezone
        cb = CircuitBreaker()
        before = datetime.now(timezone.utc)
        cb.trip("timing test")
        after = datetime.now(timezone.utc)
        ts = cb.last_trip.tripped_at
        assert before <= ts <= after, f"Trip timestamp {ts} outside [{before}, {after}]"

    def test_daily_reset_clears_rapid_log_only(self):
        """reset_daily must not clear trip history."""
        cb = CircuitBreaker()
        cb.trip("manual halt")
        cb.reset()
        cb.reset_daily()
        # Trip history must still contain the earlier event
        assert cb.trip_count == 1


# ===========================================================================
# SECTION 3 — Re-entrant Trip Protection
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestReentrantTripProtection:
    """
    Invariant: concurrent or cascading trip calls must not corrupt the
    trip history or create phantom TripEvents.
    """

    def test_trip_from_check_does_not_double_log(self):
        """check() internally calls _trip(); manual trip() on open CB must not add second event."""
        cb = CircuitBreaker(max_daily_loss=5.0)
        cb.check(daily_loss_pct=-6.0)   # trips internally
        assert cb.is_open
        initial_count = cb.trip_count
        cb.trip("external manual")      # breaker already open
        assert cb.trip_count == initial_count, "Re-trip on open breaker added phantom event"

    def test_multiple_threshold_breaches_in_one_check_trip_once(self):
        """If daily_loss AND drawdown both breach, only one trip must be recorded."""
        cb = CircuitBreaker(max_daily_loss=5.0, max_drawdown=10.0)
        cb.check(daily_loss_pct=-6.0, drawdown_pct=15.0, consecutive_losses=0)
        assert cb.trip_count == 1, f"Expected 1 trip, got {cb.trip_count}"

    def test_consecutive_check_calls_while_open_do_not_accumulate(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        for _ in range(10):
            cb.check(daily_loss_pct=-6.0)
        assert cb.trip_count == 1


# ===========================================================================
# SECTION 4 — Exact Threshold Boundary Conditions
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestExactThresholdBoundaries:
    """
    Invariant: the breaker must fire at exactly the threshold, not one
    epsilon above or below it. Off-by-one threshold handling is a
    common source of real-money loss.
    """

    def test_daily_loss_at_exact_threshold_trips(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        # loss expressed as negative: -5.0 means 5% loss
        result = cb.check(daily_loss_pct=-5.0)
        assert result is False, "Exact threshold must trip"
        assert cb.is_open

    def test_daily_loss_just_below_threshold_does_not_trip(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        result = cb.check(daily_loss_pct=-4.999)
        assert result is True, "Just below threshold must not trip"
        assert cb.is_closed

    def test_drawdown_at_exact_threshold_trips(self):
        cb = CircuitBreaker(max_drawdown=10.0)
        result = cb.check(drawdown_pct=10.0)
        assert result is False
        assert cb.is_open

    def test_drawdown_just_below_threshold_does_not_trip(self):
        cb = CircuitBreaker(max_drawdown=10.0)
        result = cb.check(drawdown_pct=9.999)
        assert result is True
        assert cb.is_closed

    def test_consecutive_losses_at_exact_threshold_trips(self):
        cb = CircuitBreaker(max_consec_loss=5)
        result = cb.check(consecutive_losses=5)
        assert result is False
        assert cb.is_open

    def test_consecutive_losses_one_below_threshold_does_not_trip(self):
        cb = CircuitBreaker(max_consec_loss=5)
        result = cb.check(consecutive_losses=4)
        assert result is True
        assert cb.is_closed

    def test_zero_loss_never_trips_daily_limit(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        result = cb.check(daily_loss_pct=0.0)
        assert result is True
        assert cb.is_closed

    def test_positive_pnl_never_trips_daily_limit(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        result = cb.check(daily_loss_pct=3.0)   # profit
        assert result is True
        assert cb.is_closed


# ===========================================================================
# SECTION 5 — Rapid-Loss Window Failure Modes
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestRapidLossWindow:
    """
    Invariant: losses accumulated within the rapid-loss window must
    trip the breaker when the threshold is crossed.
    Losses outside the window must not count.
    """

    def test_rapid_loss_trips_within_window(self):
        cb = CircuitBreaker(rapid_loss_pct=1.5, rapid_window_s=60.0)
        cb.record_trade_result(-0.8)
        cb.record_trade_result(-0.8)   # total = -1.6% — exceeds 1.5%
        assert cb.is_open, "Rapid loss should trip the breaker"

    def test_rapid_loss_single_below_threshold_no_trip(self):
        cb = CircuitBreaker(rapid_loss_pct=1.5, rapid_window_s=60.0)
        cb.record_trade_result(-1.0)
        assert cb.is_closed

    def test_profit_trades_do_not_accumulate_toward_rapid_trip(self):
        cb = CircuitBreaker(rapid_loss_pct=1.5, rapid_window_s=60.0)
        cb.record_trade_result(2.0)    # profit
        cb.record_trade_result(-1.0)   # loss — total loss in window is still -1%
        assert cb.is_closed, "Profit trade should not count toward rapid-loss trigger"

    def test_rapid_log_purges_expired_entries(self):
        """Entries older than rapid_window_s must be pruned on next record_trade_result."""
        cb = CircuitBreaker(rapid_loss_pct=1.5, rapid_window_s=0.1)  # 100ms window
        cb.record_trade_result(-1.0)
        time.sleep(0.15)   # let the window expire
        # A fresh small loss should not trip because the old entry is stale
        cb.record_trade_result(-0.1)
        assert cb.is_closed, "Expired rapid-loss entries should be pruned"

    def test_rapid_loss_reason_in_trip_event(self):
        cb = CircuitBreaker(rapid_loss_pct=1.5, rapid_window_s=60.0)
        cb.record_trade_result(-0.8)
        cb.record_trade_result(-0.8)
        assert cb.last_trip is not None
        assert "rapid" in cb.last_trip.reason.lower() or "loss" in cb.last_trip.reason.lower()

    def test_daily_reset_clears_rapid_log(self):
        """After reset_daily, rapid-loss window starts fresh."""
        cb = CircuitBreaker(rapid_loss_pct=1.5, rapid_window_s=300.0)
        cb.record_trade_result(-1.0)
        cb.reset_daily()
        cb.record_trade_result(-1.0)   # same amount — window is fresh, should not trip
        assert cb.is_closed, "rapid log should be cleared by reset_daily"


# ===========================================================================
# SECTION 6 — PositionSizer Invalid-Input Invariants
# ===========================================================================

@pytest.mark.skipif(not SIZER_AVAILABLE, reason="PositionSizer not importable")
class TestPositionSizerInvalidInputs:
    """
    Invariant: PositionSizer.calculate() must never raise — it must return
    an invalid PositionSize with valid=False and a non-empty reason.
    """

    def _make_valid_setup(self, symbol="BTCUSDT", entry=50000.0, sl=49000.0):
        setup = MagicMock(spec=TradeSetup)
        setup.valid = True
        setup.invalid_reason = ""
        setup.symbol = symbol
        setup.direction = SignalDirection.LONG
        setup.entry = entry
        setup.sl_distance = abs(entry - sl)
        setup.take_profit = entry + 2 * abs(entry - sl)
        return setup

    def test_zero_balance_returns_invalid(self):
        sizer = PositionSizer()
        setup = self._make_valid_setup()
        result = sizer.calculate(setup, balance=0.0)
        assert not result.valid
        assert result.qty == 0
        assert result.reason != ""

    def test_negative_balance_returns_invalid(self):
        sizer = PositionSizer()
        setup = self._make_valid_setup()
        result = sizer.calculate(setup, balance=-1000.0)
        assert not result.valid

    def test_zero_sl_distance_returns_invalid(self):
        sizer = PositionSizer()
        setup = self._make_valid_setup()
        setup.sl_distance = 0.0
        result = sizer.calculate(setup, balance=10000.0)
        assert not result.valid
        assert result.qty == 0

    def test_invalid_setup_returns_invalid(self):
        sizer = PositionSizer()
        setup = self._make_valid_setup()
        setup.valid = False
        setup.invalid_reason = "entry below stop"
        result = sizer.calculate(setup, balance=10000.0)
        assert not result.valid

    def test_valid_result_has_positive_qty(self):
        sizer = PositionSizer()
        setup = self._make_valid_setup()
        result = sizer.calculate(setup, balance=10000.0)
        if result.valid:
            assert result.qty > 0
            assert result.notional > 0

    def test_notional_never_exceeds_max_position_pct(self):
        max_pos_pct = 5.0
        sizer = PositionSizer(max_position_pct=max_pos_pct)
        setup = self._make_valid_setup(entry=50000.0, sl=49900.0)   # tiny SL → huge qty
        result = sizer.calculate(setup, balance=10000.0)
        if result.valid:
            max_allowed = 10000.0 * (max_pos_pct / 100)
            assert result.notional <= max_allowed + 0.01, (
                f"Notional {result.notional:.2f} exceeds {max_allowed:.2f} cap"
            )

    def test_leverage_never_exceeds_max_leverage(self):
        max_lev = 10
        sizer = PositionSizer(max_leverage=max_lev)
        setup = self._make_valid_setup()
        result = sizer.calculate(setup, balance=10000.0)
        if result.valid:
            assert result.leverage_used <= max_lev

    def test_invalid_result_never_raises(self):
        sizer = PositionSizer()
        for bad_balance in [0, -1, float("inf"), float("nan")]:
            setup = self._make_valid_setup()
            try:
                result = sizer.calculate(setup, balance=bad_balance)
                # Must return a PositionSize, not raise
                assert isinstance(result, PositionSize)
            except Exception as exc:
                pytest.fail(f"PositionSizer raised {type(exc).__name__} for balance={bad_balance}: {exc}")

    def test_kelly_fraction_always_between_0_and_max(self):
        """_kelly_fraction must always return a value in [0, MAX_KELLY_FRACTION]."""
        for win_rate in [0.0, 0.1, 0.44, 0.55, 0.9, 1.0]:
            for avg_rr in [0.01, 0.5, 1.0, 2.0, 10.0]:
                f = PositionSizer._kelly_fraction(win_rate, avg_rr)
                assert 0.0 <= f <= 0.25, (
                    f"kelly_fraction={f:.4f} out of [0, 0.25] for win={win_rate}, rr={avg_rr}"
                )

    def test_kelly_fraction_negative_edge_returns_zero(self):
        """win_rate=0.1, avg_rr=0.1 → full Kelly deeply negative → must clamp to 0."""
        f = PositionSizer._kelly_fraction(win_rate=0.1, avg_rr=0.1)
        assert f == 0.0


# ===========================================================================
# SECTION 7 — Manual Kill-Switch / Halt Propagation
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestManualHaltPropagation:
    """
    Invariant: a manually-tripped breaker must block all subsequent
    check() calls regardless of the metric values passed.
    """

    def test_manual_trip_blocks_healthy_metrics(self):
        cb = CircuitBreaker()
        cb.trip("operator kill switch")
        # All metrics are healthy — gate should still be blocked
        result = cb.check(daily_loss_pct=0.0, drawdown_pct=0.0, consecutive_losses=0)
        assert result is False

    def test_manual_trip_reason_is_preserved(self):
        cb = CircuitBreaker()
        cb.trip("mainnet kill switch engaged by operator")
        assert "mainnet kill switch" in cb.last_trip.reason

    def test_reset_after_manual_trip_allows_trading(self):
        cb = CircuitBreaker()
        cb.trip("manual halt")
        cb.reset()
        result = cb.check(daily_loss_pct=0.0, drawdown_pct=0.0, consecutive_losses=0)
        assert result is True

    def test_on_trip_callback_is_called_once_on_trip(self):
        callback = MagicMock(return_value=None)
        cb = CircuitBreaker(on_trip=callback)
        cb.trip("callback test")
        assert callback.call_count == 1

    def test_on_trip_callback_not_called_on_re_trip(self):
        callback = MagicMock(return_value=None)
        cb = CircuitBreaker(on_trip=callback)
        cb.trip("first")
        cb.trip("second — breaker already open")
        assert callback.call_count == 1, "Callback must not fire for re-trip on open breaker"

    def test_on_trip_callback_exception_does_not_propagate(self):
        """If the callback raises, the trip must still complete."""
        def bad_callback(reason, pct):
            raise RuntimeError("callback blew up")

        cb = CircuitBreaker(on_trip=bad_callback)
        # Must not raise
        try:
            cb.trip("test")
        except RuntimeError:
            pytest.fail("CircuitBreaker propagated callback exception")
        assert cb.is_open


# ===========================================================================
# SECTION 8 — Auto-Reset Timing Invariants
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestAutoResetTimingInvariants:
    """
    Invariant: with reset_after_s > 0, the breaker must auto-close
    after the cooldown elapses — but not before.
    """

    def test_auto_reset_does_not_fire_before_cooldown(self):
        cb = CircuitBreaker(reset_after_s=10.0)   # 10s — won't elapse in test
        cb.trip("timeout test")
        assert cb.is_open, "Breaker should still be open before cooldown"

    def test_auto_reset_fires_after_cooldown(self):
        cb = CircuitBreaker(reset_after_s=0.05)   # 50ms
        cb.trip("fast cooldown")
        time.sleep(0.1)
        # Accessing .state triggers _maybe_auto_reset
        assert cb.is_closed, "Breaker should auto-reset after cooldown"

    def test_auto_reset_records_reset_timestamp(self):
        cb = CircuitBreaker(reset_after_s=0.05)
        cb.trip("timing")
        time.sleep(0.1)
        _ = cb.state   # trigger auto-reset
        assert cb.last_trip.reset_at is not None

    def test_no_auto_reset_when_reset_after_s_is_zero(self):
        cb = CircuitBreaker(reset_after_s=0)
        cb.trip("no-auto")
        time.sleep(0.1)
        _ = cb.state
        assert cb.is_open, "reset_after_s=0 means manual reset only"

    def test_auto_reset_re_evaluates_fresh_checks(self):
        """After auto-reset, check() with healthy metrics must return True."""
        cb = CircuitBreaker(reset_after_s=0.05)
        cb.trip("fast reset")
        time.sleep(0.1)
        result = cb.check(daily_loss_pct=0.0, drawdown_pct=0.0, consecutive_losses=0)
        assert result is True


# ===========================================================================
# SECTION 9 — Trip History Integrity
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestTripHistoryIntegrity:
    """
    Invariant: every trip must produce exactly one TripEvent with all
    fields populated. The history must be append-only and ordered.
    """

    def test_each_trip_cycle_adds_exactly_one_event(self):
        cb = CircuitBreaker()
        for i in range(5):
            cb.trip(f"failure {i}")
            assert cb.trip_count == i + 1
            cb.reset()

    def test_trip_events_are_ordered_chronologically(self):
        cb = CircuitBreaker()
        cb.trip("a"); cb.reset()
        cb.trip("b"); cb.reset()
        cb.trip("c")
        reasons = [e.reason for e in cb._trip_history]
        assert reasons == ["a", "b", "c"]

    def test_trip_event_fields_are_fully_populated(self):
        cb = CircuitBreaker(max_daily_loss=5.0)
        cb.check(daily_loss_pct=-6.0, drawdown_pct=2.0, consecutive_losses=1)
        e = cb.last_trip
        assert isinstance(e, TripEvent)
        assert e.reason != ""
        assert e.daily_loss_pct == -6.0
        assert e.drawdown_pct == 2.0
        assert e.consecutive_losses == 1
        assert e.tripped_at is not None

    def test_status_reflects_current_trip_count(self):
        cb = CircuitBreaker()
        for i in range(3):
            cb.trip(f"trip {i}"); cb.reset()
        status = cb.status()
        assert status["trip_count"] == 3

    def test_status_last_trip_is_repr_string(self):
        cb = CircuitBreaker()
        cb.trip("status test")
        status = cb.status()
        assert isinstance(status["last_trip"], str)
        assert len(status["last_trip"]) > 0

    def test_status_last_trip_none_when_no_trips(self):
        cb = CircuitBreaker()
        status = cb.status()
        assert status["last_trip"] is None


# ===========================================================================
# SECTION 10 — Orchestrator Scan-Loop Halt Invariants
# ===========================================================================

@pytest.mark.skipif(not CB_AVAILABLE, reason="CircuitBreaker not importable")
class TestOrchestratorHaltInvariants:
    """
    Invariant: when the circuit breaker is open, the orchestrator's
    scan_pair() must return a BLOCKED_RISKGATE result and must not
    attempt to size or execute a position.
    """

    def test_scan_pair_blocked_when_circuit_open(self):
        """
        Simulate the path inside CoinScopeOrchestrator.scan_pair() where
        risk_gate.check_circuit_breakers() is consulted.

        We don't import the orchestrator directly (it requires live API keys)
        — instead we verify the gate check interface the orchestrator relies on.
        """
        try:
            from coinscope_trading_engine.core.risk_gate import RiskGate
        except ImportError:
            pytest.skip("RiskGate not importable")

        gate = RiskGate(initial_capital=10_000)
        # Force a circuit breaker condition
        gate.consecutive_losses = 10
        cb_active, reason = gate.check_circuit_breakers()
        assert cb_active is True
        assert reason != ""

    def test_gate_blocks_position_open_after_max_consecutive_losses(self):
        try:
            from coinscope_trading_engine.core.risk_gate import RiskGate
        except ImportError:
            pytest.skip("RiskGate not importable")

        gate = RiskGate(initial_capital=10_000)
        gate.consecutive_losses = 10
        pos = gate.open_position(
            symbol="BTCUSDT", direction=1, entry_price=50_000,
            entry_time=0, atr=500, regime="bull", signal_score=0.80
        )
        assert pos is None, "Position must be blocked when circuit breaker is active"

    def test_gate_blocks_position_open_after_drawdown_breach(self):
        try:
            from coinscope_trading_engine.core.risk_gate import RiskGate
        except ImportError:
            pytest.skip("RiskGate not importable")

        gate = RiskGate(initial_capital=10_000, max_drawdown_pct=0.10)
        gate.peak_equity = 10_000
        gate.current_equity = 8_000   # 20% drawdown — exceeds 10%
        cb_active, reason = gate.check_circuit_breakers()
        assert cb_active is True

    def test_circuit_breaker_status_exposes_all_required_fields(self):
        cb = CircuitBreaker()
        status = cb.status()
        required = {
            "state", "trip_count", "last_trip",
            "max_daily_loss_pct", "max_drawdown_pct", "max_consec_losses"
        }
        missing = required - set(status.keys())
        assert not missing, f"status() missing fields: {missing}"

    def test_concurrent_check_calls_do_not_corrupt_state(self):
        """
        Simulate rapid sequential checks (as would happen in a tight scan loop)
        — state must remain consistent and trip_count must be exactly 1.
        """
        cb = CircuitBreaker(max_daily_loss=5.0)
        results = []
        for _ in range(20):
            results.append(cb.check(daily_loss_pct=-6.0))
        # First call trips. All subsequent return False (already open).
        assert results[0] is False
        assert all(r is False for r in results)
        assert cb.trip_count == 1, f"Expected exactly 1 trip, got {cb.trip_count}"


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short"])

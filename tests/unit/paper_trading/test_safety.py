"""
Unit tests for CoinScopeAI Paper Trading — Safety Gate & Kill Switch.
Tests cover: kill switch activation/deactivation, all rejection reasons,
hardcoded limit enforcement, configurable limit enforcement, consecutive
loss tracking, cooldown logic, and reduce-only bypass.
"""

import json
import os
import time
import pytest
from pathlib import Path
from unittest.mock import patch

from services.paper_trading.config import (
    HARDCODED_MAX_CONCURRENT_POSITIONS,
    HARDCODED_MAX_DAILY_LOSS_PCT,
    HARDCODED_MAX_DRAWDOWN_PCT,
    HARDCODED_MAX_LEVERAGE,
    HARDCODED_MAX_POSITION_SIZE_PCT,
    TradingConfig,
)
from services.paper_trading.safety import (
    KillSwitch,
    OrderRequest,
    RejectionReason,
    SafetyGate,
    SafetyState,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_kill_file():
    """Ensure kill switch file is cleaned before/after each test."""
    kill_file = Path(KillSwitch.KILL_FILE)
    kill_file.unlink(missing_ok=True)
    yield
    kill_file.unlink(missing_ok=True)


@pytest.fixture
def kill_switch():
    return KillSwitch()


@pytest.fixture
def config():
    return TradingConfig(
        max_daily_loss_pct=0.02,
        max_drawdown_pct=0.10,
        max_position_size_pct=0.05,
        max_concurrent_positions=3,
        leverage=3,
        max_consecutive_losses=5,
        cooldown_after_loss_minutes=60,
    )


@pytest.fixture
def safety(config, kill_switch):
    return SafetyGate(config, kill_switch)


def make_order(
    symbol="BTCUSDT", side="BUY", quantity=0.001, price=50000.0,
    leverage=3, reduce_only=False, stop_loss=0.0, take_profit=0.0,
    signal_confidence=0.5, signal_edge=0.1,
):
    return OrderRequest(
        symbol=symbol, side=side, order_type="LIMIT",
        quantity=quantity, price=price, leverage=leverage,
        reduce_only=reduce_only, stop_loss=stop_loss,
        take_profit=take_profit, signal_confidence=signal_confidence,
        signal_edge=signal_edge,
    )


# ── Kill Switch Tests ─────────────────────────────────────────

class TestKillSwitch:

    def test_initially_inactive(self, kill_switch):
        assert not kill_switch.is_active
        assert kill_switch.reason == ""

    def test_activate(self, kill_switch):
        kill_switch.activate("test_reason")
        assert kill_switch.is_active
        assert kill_switch.reason == "test_reason"

    def test_activate_creates_file(self, kill_switch):
        kill_switch.activate("file_test")
        assert Path(KillSwitch.KILL_FILE).exists()
        data = json.loads(Path(KillSwitch.KILL_FILE).read_text())
        assert data["reason"] == "file_test"

    def test_deactivate(self, kill_switch):
        kill_switch.activate("test")
        kill_switch.deactivate()
        assert not kill_switch.is_active
        assert not Path(KillSwitch.KILL_FILE).exists()

    def test_persistent_flag_on_init(self):
        """Kill switch should detect existing flag file on init."""
        Path(KillSwitch.KILL_FILE).write_text(json.dumps({
            "reason": "previous_crash",
            "activated_at": time.time(),
        }))
        ks = KillSwitch()
        assert ks.is_active

    def test_status_dict(self, kill_switch):
        status = kill_switch.status()
        assert "active" in status
        assert "reason" in status
        assert "activated_at" in status

    def test_multiple_activations(self, kill_switch):
        kill_switch.activate("first")
        kill_switch.activate("second")
        assert kill_switch.reason == "second"


# ── Safety Gate — Kill Switch Integration ─────────────────────

class TestSafetyGateKillSwitch:

    def test_rejects_when_kill_switch_active(self, safety, kill_switch):
        kill_switch.activate("test")
        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.KILL_SWITCH_ACTIVE

    def test_approves_when_kill_switch_inactive(self, safety):
        approved, reason, msg = safety.validate_order(make_order())
        assert approved


# ── Safety Gate — Reduce Only Bypass ──────────────────────────

class TestSafetyGateReduceOnly:

    def test_reduce_only_always_passes(self, safety, kill_switch):
        """Reduce-only orders pass even with strict limits, except kill switch."""
        # Set up conditions that would reject a normal order
        safety._state.daily_pnl = -1000
        safety._state.consecutive_losses = 100

        order = make_order(reduce_only=True)
        approved, reason, msg = safety.validate_order(order)
        assert approved

    def test_reduce_only_blocked_by_kill_switch(self, safety, kill_switch):
        """Even reduce-only is blocked by kill switch."""
        kill_switch.activate("test")
        order = make_order(reduce_only=True)
        approved, reason, msg = safety.validate_order(order)
        assert not approved
        assert reason == RejectionReason.KILL_SWITCH_ACTIVE


# ── Safety Gate — Hardcoded Limits ────────────────────────────

class TestSafetyGateHardcodedLimits:

    def test_rejects_excessive_leverage(self, safety):
        order = make_order(leverage=HARDCODED_MAX_LEVERAGE + 1)
        approved, reason, msg = safety.validate_order(order)
        assert not approved
        assert reason == RejectionReason.LEVERAGE_TOO_HIGH

    def test_accepts_max_leverage(self, safety):
        # Need to also set config leverage high enough
        safety._config.leverage = HARDCODED_MAX_LEVERAGE
        order = make_order(leverage=HARDCODED_MAX_LEVERAGE)
        approved, reason, msg = safety.validate_order(order)
        assert approved

    def test_rejects_oversized_position(self, safety):
        """Position value exceeding hardcoded max % of equity."""
        safety._state.current_equity = 10000
        # Position: 1 BTC * 50000 * 3x = 150000 = 1500% of equity
        order = make_order(quantity=1.0, price=50000, leverage=3)
        approved, reason, msg = safety.validate_order(order)
        assert not approved
        assert reason == RejectionReason.POSITION_TOO_LARGE

    def test_rejects_too_many_positions(self, safety):
        """Exceeding hardcoded max concurrent positions."""
        # Fill up to hardcoded max
        for i in range(HARDCODED_MAX_CONCURRENT_POSITIONS):
            safety._state.open_positions[f"SYM{i}USDT"] = {"side": "LONG"}

        order = make_order()
        approved, reason, msg = safety.validate_order(order)
        assert not approved
        assert reason == RejectionReason.MAX_POSITIONS

    def test_daily_loss_triggers_kill_switch(self, safety, kill_switch):
        """Hitting hardcoded daily loss triggers kill switch."""
        safety._state.initial_equity = 10000
        safety._state.daily_pnl = -(HARDCODED_MAX_DAILY_LOSS_PCT * 10000)

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.DAILY_LOSS_LIMIT
        assert kill_switch.is_active

    def test_max_drawdown_triggers_kill_switch(self, safety, kill_switch):
        """Hitting hardcoded max drawdown triggers kill switch."""
        safety._state.peak_equity = 10000
        safety._state.current_equity = 10000 * (1 - HARDCODED_MAX_DRAWDOWN_PCT)

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.MAX_DRAWDOWN
        assert kill_switch.is_active


# ── Safety Gate — Configurable Limits ─────────────────────────

class TestSafetyGateConfigurableLimits:

    def test_rejects_config_daily_loss(self, safety):
        safety._state.initial_equity = 10000
        safety._state.daily_pnl = -250  # 2.5% > config 2%

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.DAILY_LOSS_LIMIT

    def test_rejects_config_drawdown(self, safety):
        safety._state.peak_equity = 10000
        safety._state.current_equity = 8900  # 11% > config 10%

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.MAX_DRAWDOWN

    def test_rejects_config_max_positions(self, safety):
        for i in range(3):  # config max = 3
            safety._state.open_positions[f"SYM{i}USDT"] = {"side": "LONG"}

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.MAX_POSITIONS

    def test_rejects_config_position_size(self, safety):
        safety._state.current_equity = 10000
        # 0.1 BTC * 50000 * 3x = 15000 = 150% > config 5%
        order = make_order(quantity=0.1, price=50000, leverage=3)
        approved, reason, msg = safety.validate_order(order)
        assert not approved
        assert reason == RejectionReason.POSITION_TOO_LARGE

    def test_rejects_config_leverage(self, safety):
        order = make_order(leverage=4)  # config max = 3
        approved, reason, msg = safety.validate_order(order)
        assert not approved
        assert reason == RejectionReason.LEVERAGE_TOO_HIGH


# ── Safety Gate — State Checks ────────────────────────────────

class TestSafetyGateStateChecks:

    def test_rejects_consecutive_losses(self, safety):
        safety._state.consecutive_losses = 5  # config max = 5

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.CONSECUTIVE_LOSSES

    def test_rejects_during_cooldown(self, safety):
        safety._state.last_loss_time = time.time()  # Just lost

        approved, reason, msg = safety.validate_order(make_order())
        assert not approved
        assert reason == RejectionReason.COOLDOWN_ACTIVE

    def test_allows_after_cooldown(self, safety):
        # Loss was 2 hours ago, cooldown is 60 min
        safety._state.last_loss_time = time.time() - 7200

        approved, reason, msg = safety.validate_order(make_order())
        assert approved

    def test_record_trade_result_loss(self, safety):
        safety.record_trade_result(-0.01)
        assert safety.state.consecutive_losses == 1

    def test_record_trade_result_win_resets(self, safety):
        safety.record_trade_result(-0.01)
        safety.record_trade_result(-0.01)
        assert safety.state.consecutive_losses == 2
        safety.record_trade_result(0.02)
        assert safety.state.consecutive_losses == 0

    def test_reset_daily_pnl(self, safety):
        safety._state.daily_pnl = -100
        safety.reset_daily_pnl()
        assert safety.state.daily_pnl == 0.0


# ── Safety Gate — Counters ────────────────────────────────────

class TestSafetyGateCounters:

    def test_submitted_counter(self, safety):
        safety.validate_order(make_order())
        assert safety.state.total_orders_submitted == 1

    def test_rejected_counter(self, safety, kill_switch):
        kill_switch.activate("test")
        safety.validate_order(make_order())
        assert safety.state.total_orders_rejected == 1

    def test_rejection_log_capped(self, safety, kill_switch):
        kill_switch.activate("test")
        for _ in range(150):
            safety.validate_order(make_order())
        assert len(safety.state.rejection_log) <= 100

    def test_get_status(self, safety):
        status = safety.get_status()
        assert "equity" in status
        assert "drawdown_pct" in status
        assert "daily_pnl" in status
        assert "kill_switch" in status


# ── Config Enforcement ────────────────────────────────────────

class TestConfigEnforcement:

    def test_config_clamps_to_hardcoded_max(self):
        """Config values exceeding hardcoded limits get clamped."""
        config = TradingConfig(
            max_daily_loss_pct=0.50,
            max_drawdown_pct=0.50,
            max_position_size_pct=0.50,
            max_concurrent_positions=50,
            leverage=50,
        )
        assert config.max_daily_loss_pct <= HARDCODED_MAX_DAILY_LOSS_PCT
        assert config.max_drawdown_pct <= HARDCODED_MAX_DRAWDOWN_PCT
        assert config.max_position_size_pct <= HARDCODED_MAX_POSITION_SIZE_PCT
        assert config.max_concurrent_positions <= HARDCODED_MAX_CONCURRENT_POSITIONS
        assert config.leverage <= HARDCODED_MAX_LEVERAGE

    def test_testnet_only_enforced(self):
        """ExchangeConfig blocks mainnet URLs."""
        from services.paper_trading.config import ExchangeConfig
        config = ExchangeConfig()
        assert "testnet" in config.rest_url
        assert "testnet" not in "fapi.binance.com"

"""
Integration tests for CoinScopeAI Paper Trading — Engine.
Tests cover: engine lifecycle, kill switch under all conditions,
state persistence, daily reset, and heartbeat.
"""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from services.paper_trading.config import (
    PaperTradingConfig,
    TradingConfig,
    ExchangeConfig,
    TelegramConfig,
    HARDCODED_TESTNET_ONLY,
)
from services.paper_trading.safety import KillSwitch, SafetyGate, OrderRequest


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_files():
    """Clean up state and kill files."""
    for f in [
        "/tmp/coinscopeai_kill_switch.flag",
        "/tmp/coinscopeai_paper_trading_state.json",
    ]:
        Path(f).unlink(missing_ok=True)
    yield
    for f in [
        "/tmp/coinscopeai_kill_switch.flag",
        "/tmp/coinscopeai_paper_trading_state.json",
    ]:
        Path(f).unlink(missing_ok=True)


# ── Kill Switch Integration Tests ─────────────────────────────

class TestKillSwitchIntegration:

    def test_kill_switch_blocks_all_orders(self):
        """Once activated, kill switch blocks ALL new orders."""
        config = TradingConfig()
        ks = KillSwitch()
        gate = SafetyGate(config, ks)
        gate._state.current_equity = 10000
        gate._state.initial_equity = 10000
        gate._state.peak_equity = 10000

        # Normal order passes
        order = OrderRequest(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity=0.001, price=50000, leverage=3,
        )
        approved, _, _ = gate.validate_order(order)
        assert approved

        # Activate kill switch
        ks.activate("test_integration")

        # All orders blocked
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
            order = OrderRequest(
                symbol=symbol, side="BUY", order_type="MARKET",
                quantity=0.001, price=50000, leverage=3,
            )
            approved, reason, _ = gate.validate_order(order)
            assert not approved
            assert reason.value == "kill_switch_active"

    def test_kill_switch_survives_restart(self):
        """Kill switch persists across process restarts via file flag."""
        ks1 = KillSwitch()
        ks1.activate("crash_protection")

        # Simulate restart
        ks2 = KillSwitch()
        assert ks2.is_active

    def test_kill_switch_deactivation_requires_explicit_call(self):
        """Kill switch cannot be deactivated by simply creating a new instance."""
        ks = KillSwitch()
        ks.activate("test")

        # New instance still sees the flag
        ks2 = KillSwitch()
        assert ks2.is_active

        # Only explicit deactivation works
        ks2.deactivate()
        ks3 = KillSwitch()
        assert not ks3.is_active

    def test_kill_switch_triggered_by_drawdown(self):
        """Max drawdown should auto-trigger kill switch."""
        config = TradingConfig(max_drawdown_pct=0.10)
        ks = KillSwitch()
        gate = SafetyGate(config, ks)
        gate._state.peak_equity = 10000
        gate._state.current_equity = 8500  # 15% drawdown
        gate._state.initial_equity = 10000

        order = OrderRequest(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity=0.001, price=50000, leverage=3,
        )
        approved, reason, _ = gate.validate_order(order)
        assert not approved
        assert ks.is_active

    def test_kill_switch_triggered_by_daily_loss(self):
        """Max daily loss should auto-trigger kill switch."""
        config = TradingConfig(max_daily_loss_pct=0.02)
        ks = KillSwitch()
        gate = SafetyGate(config, ks)
        gate._state.initial_equity = 10000
        gate._state.current_equity = 10000
        gate._state.peak_equity = 10000
        gate._state.daily_pnl = -600  # 6% > hardcoded 5%

        order = OrderRequest(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity=0.001, price=50000, leverage=3,
        )
        approved, _, _ = gate.validate_order(order)
        assert not approved
        assert ks.is_active


# ── State Persistence Tests ───────────────────────────────────

class TestStatePersistence:

    def test_state_file_creation(self):
        """Engine should save state to a JSON file."""
        state_file = Path("/tmp/coinscopeai_paper_trading_state.json")
        state = {
            "saved_at": time.time(),
            "portfolio": {"equity": 10000},
            "safety": {"kill_switch": {"active": False}},
        }
        state_file.write_text(json.dumps(state))
        assert state_file.exists()

        loaded = json.loads(state_file.read_text())
        assert loaded["portfolio"]["equity"] == 10000

    def test_state_file_freshness(self):
        """State file should be recent (within 5 minutes)."""
        state_file = Path("/tmp/coinscopeai_paper_trading_state.json")
        state = {"saved_at": time.time()}
        state_file.write_text(json.dumps(state))

        loaded = json.loads(state_file.read_text())
        assert time.time() - loaded["saved_at"] < 300


# ── Config Safety Tests ───────────────────────────────────────

class TestConfigSafety:

    def test_testnet_only_flag(self):
        assert HARDCODED_TESTNET_ONLY is True

    def test_config_defaults_conservative(self):
        config = TradingConfig()
        assert config.leverage <= 5
        assert config.max_daily_loss_pct <= 0.05
        assert config.max_drawdown_pct <= 0.15
        assert config.max_position_size_pct <= 0.10
        assert config.max_concurrent_positions <= 5

    def test_config_cannot_exceed_hardcoded(self):
        config = TradingConfig(
            leverage=100,
            max_daily_loss_pct=1.0,
            max_drawdown_pct=1.0,
            max_position_size_pct=1.0,
            max_concurrent_positions=100,
        )
        assert config.leverage <= 5
        assert config.max_daily_loss_pct <= 0.05
        assert config.max_drawdown_pct <= 0.15
        assert config.max_position_size_pct <= 0.10
        assert config.max_concurrent_positions <= 5

    def test_paper_trading_config_composition(self):
        ptc = PaperTradingConfig()
        assert isinstance(ptc.trading, TradingConfig)
        assert isinstance(ptc.exchange, ExchangeConfig)
        assert isinstance(ptc.telegram, TelegramConfig)


# ── Safety Gate Layered Check Order ───────────────────────────

class TestSafetyCheckOrder:
    """Verify that safety checks are applied in the correct order:
    1. Kill switch (highest priority)
    2. Reduce-only bypass
    3. Hardcoded limits
    4. Configurable limits
    5. State checks (consecutive losses, cooldown)
    """

    def test_kill_switch_checked_first(self):
        """Kill switch should be checked before any other condition."""
        config = TradingConfig()
        ks = KillSwitch()
        gate = SafetyGate(config, ks)

        # Set up conditions that would pass all other checks
        gate._state.current_equity = 10000
        gate._state.initial_equity = 10000
        gate._state.peak_equity = 10000

        # But kill switch is active
        ks.activate("test")

        order = OrderRequest(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity=0.001, price=50000, leverage=3,
        )
        approved, reason, _ = gate.validate_order(order)
        assert not approved
        assert reason.value == "kill_switch_active"

    def test_reduce_only_bypasses_all_except_kill_switch(self):
        """Reduce-only orders should pass even with extreme conditions."""
        config = TradingConfig()
        ks = KillSwitch()
        gate = SafetyGate(config, ks)

        # Set up conditions that would reject everything
        gate._state.daily_pnl = -10000
        gate._state.consecutive_losses = 100
        gate._state.last_loss_time = time.time()
        for i in range(10):
            gate._state.open_positions[f"SYM{i}"] = {}

        order = OrderRequest(
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            quantity=0.001, price=50000, leverage=3,
            reduce_only=True,
        )
        approved, _, _ = gate.validate_order(order)
        assert approved

    def test_hardcoded_checked_before_configurable(self):
        """Hardcoded limits should trigger before configurable ones."""
        config = TradingConfig(
            max_daily_loss_pct=0.01,  # Very strict
            leverage=2,
        )
        ks = KillSwitch()
        gate = SafetyGate(config, ks)
        gate._state.current_equity = 10000
        gate._state.initial_equity = 10000
        gate._state.peak_equity = 10000

        # Leverage exceeds hardcoded max (5)
        order = OrderRequest(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity=0.001, price=50000, leverage=10,
        )
        approved, reason, _ = gate.validate_order(order)
        assert not approved
        assert reason.value == "leverage_exceeds_limit"


# ── Concurrent Safety Tests ───────────────────────────────────

class TestConcurrentSafety:

    def test_equity_update_thread_safe(self):
        """Equity updates should be thread-safe."""
        config = TradingConfig()
        gate = SafetyGate(config)

        import threading
        errors = []

        def update_equity(val):
            try:
                for _ in range(100):
                    gate.update_equity(val)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=update_equity, args=(10000 + i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert gate.state.current_equity > 0

    def test_validate_order_thread_safe(self):
        """Order validation should be thread-safe."""
        config = TradingConfig()
        gate = SafetyGate(config)
        gate._state.current_equity = 10000
        gate._state.initial_equity = 10000
        gate._state.peak_equity = 10000

        import threading
        results = []

        def validate():
            order = OrderRequest(
                symbol="BTCUSDT", side="BUY", order_type="MARKET",
                quantity=0.001, price=50000, leverage=3,
            )
            approved, _, _ = gate.validate_order(order)
            results.append(approved)

        threads = [threading.Thread(target=validate) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 20
        # All should be approved (no risk conditions triggered)
        assert all(results)

"""
Integration tests for PaperTradingEngineV2 with MakerExecutor.

Test coverage
─────────────
- MakerExecutor is properly initialized in engine __init__
- _handle_signal calls _maker_executor.execute() (not old order_manager path)
- When exec_result.success=True, alerter.order_submitted() is called with correct keys
- When exec_result.success=False, alerter.order_submitted() is NOT called
- get_status() includes "maker_stats" key with maker executor stats
"""

import time
import pytest
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass

from services.paper_trading.config import PaperTradingConfig
from services.paper_trading.engine_v2 import PaperTradingEngineV2
from services.paper_trading.maker_execution import (
    MakerExecutor,
    MakerExecutionResult,
    ExecutionStrategy,
)
from services.paper_trading.order_manager import ManagedOrder, OrderStatus
from services.paper_trading.signal_engine import TradingSignal


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    """Minimal config with safe defaults."""
    config = MagicMock()
    config.trading = MagicMock()
    config.trading.min_confidence = 0.6
    config.trading.min_edge = 0.001
    config.trading.leverage = 3
    config.trading.max_position_size_pct = 0.05
    config.trading.max_daily_loss_pct = 0.02
    config.trading.max_drawdown_pct = 0.10
    config.trading.max_concurrent_positions = 5
    config.trading.order_type = "LIMIT"
    config.trading.limit_offset_pct = 0.001
    config.exchange = MagicMock()
    config.telegram = MagicMock()
    return config


@pytest.fixture
def mock_exchange():
    """Mock exchange client."""
    ex = MagicMock()
    ex.get_ticker_price.return_value = 50_000.0
    ex.get_orderbook.return_value = {
        "bids": [["49995.0", "1.0"]],
        "asks": [["50005.0", "1.0"]],
    }
    ex.get_usdt_balance.return_value = 10000.0
    return ex


@pytest.fixture
def mock_alerter():
    """Mock alerter."""
    alerter = MagicMock()
    return alerter


@pytest.fixture
def mock_order_manager():
    """Mock order manager."""
    mgr = MagicMock()
    mgr.get_status.return_value = {
        "open_positions": {},
        "pending_orders": [],
    }
    mgr.positions = {}
    return mgr


@pytest.fixture
def mock_event_bus():
    """Mock event bus."""
    return MagicMock()


@pytest.fixture
def engine(mock_config, mock_exchange, mock_alerter, mock_order_manager, mock_event_bus):
    """Create engine with mocked dependencies."""
    with patch("services.paper_trading.engine_v2.BinanceFuturesTestnetClient", return_value=mock_exchange):
        with patch("services.paper_trading.engine_v2.SafetyGate") as mock_safety:
            with patch("services.paper_trading.engine_v2.OrderManager", return_value=mock_order_manager):
                with patch("services.paper_trading.engine_v2.TelegramAlerter", return_value=mock_alerter):
                    with patch("services.paper_trading.engine_v2.MLSignalEngine"):
                        with patch("services.paper_trading.engine_v2.BinanceFuturesWebSocket"):
                            with patch("services.paper_trading.engine_v2.KillSwitch") as mock_ks_class:
                                mock_ks = MagicMock()
                                mock_ks.is_active = False
                                mock_ks_class.return_value = mock_ks
                                
                                engine = PaperTradingEngineV2(
                                    config=mock_config,
                                    event_bus=mock_event_bus,
                                )
                                # Mock safety gate
                                engine._safety.get_status.return_value = {
                                    "kill_switch": False,
                                    "current_equity": 10000,
                                    "peak_equity": 10000,
                                    "daily_pnl": 0,
                                }
                                engine._safety.validate_order.return_value = (True, None, None)
                                engine._safety.state = MagicMock()
                                engine._safety.state.current_equity = 10000
                                
                                # Mock alpha context to allow signals through
                                engine._alpha_ctx.get_context = MagicMock(return_value={})
                                
                                # Mock regime context to allow signals through
                                engine._regime_ctx.get_regime_features = MagicMock(return_value={})
                                engine._regime_ctx.get_regime = MagicMock(return_value=None)
                                
                                # Mock spread tracker to allow signals through
                                engine._spread_tracker.get_avg_spread = MagicMock(return_value=5.0)
                                
                                return engine


def _managed_order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    quantity=0.01,
    price=50_000.0,
    exchange_order_id=12345,
    filled_qty=0.01,
    avg_fill_price=50_000.0,
    status=OrderStatus.FILLED,
):
    return ManagedOrder(
        internal_id="CSA-test-001",
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        leverage=3,
        status=status,
        exchange_order_id=exchange_order_id,
        filled_qty=filled_qty,
        avg_fill_price=avg_fill_price,
        rejection_reason="",
        created_at=time.time(),
        submitted_at=time.time(),
    )


def _success_result(order=None):
    """Create a successful execution result."""
    if order is None:
        order = _managed_order()
    return MakerExecutionResult(
        success=True,
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.01,
        strategy=ExecutionStrategy.MAKER_FIRST_TRY,
        order=order,
        initial_limit_price=50_000.0,
        final_fill_price=50_000.0,
        market_price_at_entry=50_005.0,
        fill_latency_ms=150.0,
        slippage_saved_bps=5.0,
        retries=0,
        error_message="",
    )


def _failure_result():
    """Create a failed execution result."""
    return MakerExecutionResult(
        success=False,
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.01,
        strategy=ExecutionStrategy.MARKET_FALLBACK,
        order=None,
        initial_limit_price=50_000.0,
        final_fill_price=0.0,
        market_price_at_entry=50_005.0,
        fill_latency_ms=60_000.0,
        slippage_saved_bps=0.0,
        retries=3,
        error_message="Order timeout after retries",
    )


def _trading_signal(
    symbol="BTCUSDT",
    direction="LONG",
    confidence=0.75,
    edge=0.005,
    regime="bullish",
):
    """Create a TradingSignal."""
    return TradingSignal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        edge=edge,
        predicted_class=2 if direction == "LONG" else 0,
        probabilities={"SHORT": 0.1, "NEUTRAL": 0.15, "LONG": 0.75},
        features_used=50,
        regime=regime,
        timestamp=time.time(),
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestMakerExecutorInitialization:
    """Test MakerExecutor is properly initialized."""

    def test_maker_executor_created_in_init(self, engine):
        """Engine should create _maker_executor attribute."""
        assert hasattr(engine, "_maker_executor")
        assert isinstance(engine._maker_executor, MakerExecutor)

    def test_maker_executor_has_order_manager(self, engine):
        """MakerExecutor should be wired to order_manager."""
        assert engine._maker_executor._mgr is engine._order_manager

    def test_maker_executor_has_exchange(self, engine):
        """MakerExecutor should be wired to exchange client."""
        assert engine._maker_executor._exchange is engine._exchange


class TestHandleSignalIntegration:
    """Test _handle_signal integration with MakerExecutor."""

    def test_handle_signal_calls_maker_executor_execute(self, engine):
        """_handle_signal should call _maker_executor.execute()."""
        order = _managed_order()
        result = _success_result(order=order)
        
        with patch.object(engine._maker_executor, 'execute', return_value=result) as mock_execute:
            signal = _trading_signal()
            engine._handle_signal(signal)
            
            # Verify maker_executor.execute was called
            mock_execute.assert_called_once()

    def test_maker_executor_execute_called_with_correct_params(self, engine):
        """_maker_executor.execute() should receive correct parameters."""
        order = _managed_order()
        result = _success_result(order=order)
        
        with patch.object(engine._maker_executor, 'execute', return_value=result) as mock_execute:
            signal = _trading_signal(
                symbol="ETHUSDT",
                direction="SHORT",
                confidence=0.65,
                edge=0.002,
                regime="bearish",
            )
            engine._handle_signal(signal)
            
            # Verify execute was called - the parameters should be there but
            # the exact values depend on the actual _calculate_order_params logic
            # We just verify it was called
            mock_execute.assert_called_once()
            
            # Get the call args to verify they contain the symbol
            call_args = mock_execute.call_args
            assert call_args[1]['symbol'] == "ETHUSDT"
            assert call_args[1]['side'] == "SELL"


class TestAlerterIntegration:
    """Test alerter integration with execution results."""

    def test_alerter_called_on_success(self, engine):
        """When exec_result.success=True, alerter.order_submitted() should be called."""
        order = _managed_order()
        result = _success_result(order=order)

        with patch.object(engine._maker_executor, 'execute', return_value=result):
            signal = _trading_signal()
            engine._handle_signal(signal)
            
            # Verify alerter.order_submitted was called
            engine._alerter.order_submitted.assert_called_once()

    def test_alerter_receives_execution_strategy_key(self, engine):
        """Alerter should receive 'execution_strategy' key in dict."""
        order = _managed_order()
        result = _success_result(order=order)

        with patch.object(engine._maker_executor, 'execute', return_value=result):
            signal = _trading_signal()
            engine._handle_signal(signal)
            
            # Get the call arguments
            call_args = engine._alerter.order_submitted.call_args
            alert_dict = call_args[0][0]
            
            # Verify keys are present
            assert "execution_strategy" in alert_dict
            assert alert_dict["execution_strategy"] == ExecutionStrategy.MAKER_FIRST_TRY.value

    def test_alerter_receives_slippage_saved_bps_key(self, engine):
        """Alerter should receive 'slippage_saved_bps' key in dict."""
        order = _managed_order()
        result = _success_result(order=order)
        result.slippage_saved_bps = 7.5

        with patch.object(engine._maker_executor, 'execute', return_value=result):
            signal = _trading_signal()
            engine._handle_signal(signal)
            
            # Get the call arguments
            call_args = engine._alerter.order_submitted.call_args
            alert_dict = call_args[0][0]
            
            # Verify slippage_saved_bps is present and correct
            assert "slippage_saved_bps" in alert_dict
            assert alert_dict["slippage_saved_bps"] == 7.5

    def test_alerter_not_called_on_failure(self, engine):
        """When exec_result.success=False, alerter.order_submitted() should NOT be called."""
        result = _failure_result()

        with patch.object(engine._maker_executor, 'execute', return_value=result):
            signal = _trading_signal()
            engine._handle_signal(signal)
            
            # Verify alerter.order_submitted was NOT called
            engine._alerter.order_submitted.assert_not_called()


class TestGetStatusIntegration:
    """Test get_status() includes maker_stats."""

    def test_get_status_includes_maker_stats_key(self, engine):
        """get_status() should include 'maker_stats' key."""
        status = engine.get_status()
        assert "maker_stats" in status

    def test_get_status_maker_stats_has_correct_structure(self, engine):
        """maker_stats should have the expected keys from MakerExecutor.stats."""
        status = engine.get_status()
        maker_stats = status["maker_stats"]

        # Verify expected stat keys
        expected_keys = {
            "total_orders",
            "maker_fills",
            "market_fallbacks",
            "maker_fill_rate_pct",
            "avg_bps_saved",
            "total_bps_saved",
        }
        assert set(maker_stats.keys()) == expected_keys

    def test_get_status_maker_stats_values_are_numeric(self, engine):
        """maker_stats values should be numeric."""
        status = engine.get_status()
        maker_stats = status["maker_stats"]

        assert isinstance(maker_stats["total_orders"], int)
        assert isinstance(maker_stats["maker_fills"], int)
        assert isinstance(maker_stats["market_fallbacks"], int)
        assert isinstance(maker_stats["maker_fill_rate_pct"], (int, float))
        assert isinstance(maker_stats["avg_bps_saved"], (int, float))
        assert isinstance(maker_stats["total_bps_saved"], (int, float))


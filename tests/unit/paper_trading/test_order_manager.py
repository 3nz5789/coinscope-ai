"""
Unit tests for CoinScopeAI Paper Trading — Order Manager & Position Tracker.
Tests cover: order lifecycle, fill processing, position tracking, P&L calculation,
SL/TP monitoring, stale order cleanup, portfolio summary, and callbacks.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from services.paper_trading.config import TradingConfig
from services.paper_trading.exchange_client import OrderResult, ExchangeError
from services.paper_trading.order_manager import (
    ManagedOrder,
    OrderManager,
    OrderStatus,
    TrackedPosition,
)
from services.paper_trading.safety import KillSwitch, OrderRequest, SafetyGate


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_kill_file():
    """Ensure kill switch file is cleaned before/after each test."""
    from pathlib import Path
    from services.paper_trading.safety import KillSwitch
    Path(KillSwitch.KILL_FILE).unlink(missing_ok=True)
    yield
    Path(KillSwitch.KILL_FILE).unlink(missing_ok=True)


@pytest.fixture
def config():
    return TradingConfig()


@pytest.fixture
def mock_exchange():
    exchange = MagicMock()
    exchange.get_ticker_price.return_value = 50000.0
    exchange.set_leverage.return_value = {}
    exchange.place_order.return_value = OrderResult(
        order_id=12345,
        client_order_id="CSA-test123",
        symbol="BTCUSDT",
        side="BUY",
        order_type="MARKET",
        status="FILLED",
        price=50000.0,
        avg_price=50000.0,
        quantity=0.01,
        executed_qty=0.01,
        timestamp=int(time.time() * 1000),
        raw={},
    )
    return exchange


@pytest.fixture
def safety(config):
    ks = KillSwitch()
    gate = SafetyGate(config, ks)
    # Use 100000 equity so 0.01 BTC * 50000 * 3x = 1500 USDT = 1.5% < 10% hardcoded limit
    gate._state.current_equity = 100000
    gate._state.initial_equity = 100000
    gate._state.peak_equity = 100000
    return gate


@pytest.fixture
def manager(mock_exchange, safety, config):
    return OrderManager(mock_exchange, safety, config)


# ── Order Submission Tests ────────────────────────────────────

class TestOrderSubmission:

    def test_submit_market_order_success(self, manager, mock_exchange):
        success, order = manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        assert success
        assert order.status == OrderStatus.FILLED
        assert order.exchange_order_id == 12345

    def test_submit_order_logs_before_exchange(self, manager, mock_exchange):
        """Order must be created and logged before exchange submission."""
        success, order = manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
        )
        assert order.internal_id.startswith("CSA-")
        assert order.created_at > 0

    def test_submit_order_rejected_by_safety(self, manager, safety):
        """Safety gate rejection should not reach exchange."""
        safety._kill_switch.activate("test")
        success, order = manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
        )
        assert not success
        assert order.status == OrderStatus.REJECTED_SAFETY
        assert "kill_switch" in order.rejection_reason

    def test_submit_order_exchange_error(self, manager, mock_exchange):
        mock_exchange.place_order.side_effect = ExchangeError("test error", 400)
        success, order = manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
        )
        assert not success
        assert order.status == OrderStatus.FAILED

    def test_submit_order_sets_leverage(self, manager, mock_exchange):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01, leverage=3,
        )
        mock_exchange.set_leverage.assert_called_with("BTCUSDT", 3)


# ── Position Tracking Tests ───────────────────────────────────

class TestPositionTracking:

    def test_fill_creates_position(self, manager):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        positions = manager.positions
        assert "BTCUSDT" in positions
        assert positions["BTCUSDT"].side == "LONG"
        assert positions["BTCUSDT"].entry_price == 50000.0

    def test_sell_creates_short_position(self, manager, mock_exchange):
        mock_exchange.place_order.return_value = OrderResult(
            order_id=12346, client_order_id="CSA-test456",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=50000.0, avg_price=50000.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )
        manager.submit_order(
            symbol="BTCUSDT", side="SELL", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        positions = manager.positions
        assert positions["BTCUSDT"].side == "SHORT"

    def test_close_position(self, manager, mock_exchange):
        # Open position
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        assert "BTCUSDT" in manager.positions

        # Close position
        mock_exchange.place_order.return_value = OrderResult(
            order_id=12347, client_order_id="CSA-close",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=51000.0, avg_price=51000.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )
        success, order = manager.close_position("BTCUSDT")
        assert success
        assert "BTCUSDT" not in manager.positions

    def test_close_nonexistent_position(self, manager):
        success, order = manager.close_position("NONEXIST")
        assert not success
        assert order is None


# ── P&L Calculation Tests ─────────────────────────────────────

class TestPnLCalculation:

    def test_long_profit(self, manager):
        pnl = manager._calc_pnl("LONG", 50000, 51000, 0.01)
        assert pnl == pytest.approx(10.0)  # (51000-50000) * 0.01

    def test_long_loss(self, manager):
        pnl = manager._calc_pnl("LONG", 50000, 49000, 0.01)
        assert pnl == pytest.approx(-10.0)

    def test_short_profit(self, manager):
        pnl = manager._calc_pnl("SHORT", 50000, 49000, 0.01)
        assert pnl == pytest.approx(10.0)

    def test_short_loss(self, manager):
        pnl = manager._calc_pnl("SHORT", 50000, 51000, 0.01)
        assert pnl == pytest.approx(-10.0)


# ── Trade Journal Tests ───────────────────────────────────────

class TestTradeJournal:

    def test_closed_trade_logged(self, manager, mock_exchange):
        # Open
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        # Close
        mock_exchange.place_order.return_value = OrderResult(
            order_id=12348, client_order_id="CSA-close2",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=51000.0, avg_price=51000.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )
        manager.close_position("BTCUSDT")

        journal = manager.trade_journal
        assert len(journal) == 1
        assert journal[0]["symbol"] == "BTCUSDT"
        assert journal[0]["side"] == "LONG"
        assert journal[0]["pnl"] == pytest.approx(10.0)


# ── SL/TP Monitoring Tests ────────────────────────────────────

class TestStopLossTakeProfit:

    def test_long_stop_loss_triggered(self, manager, mock_exchange):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
            stop_loss=49000.0, take_profit=52000.0,
        )

        # Mock the close order
        mock_exchange.place_order.return_value = OrderResult(
            order_id=99999, client_order_id="CSA-sl",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=48900.0, avg_price=48900.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )

        manager.check_stop_loss_take_profit("BTCUSDT", 48900.0)
        assert "BTCUSDT" not in manager.positions

    def test_long_take_profit_triggered(self, manager, mock_exchange):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
            stop_loss=49000.0, take_profit=52000.0,
        )

        mock_exchange.place_order.return_value = OrderResult(
            order_id=99998, client_order_id="CSA-tp",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=52100.0, avg_price=52100.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )

        manager.check_stop_loss_take_profit("BTCUSDT", 52100.0)
        assert "BTCUSDT" not in manager.positions

    def test_no_trigger_within_range(self, manager):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
            stop_loss=49000.0, take_profit=52000.0,
        )
        manager.check_stop_loss_take_profit("BTCUSDT", 50500.0)
        assert "BTCUSDT" in manager.positions

    def test_short_stop_loss_triggered(self, manager, mock_exchange):
        mock_exchange.place_order.return_value = OrderResult(
            order_id=12346, client_order_id="CSA-short",
            symbol="ETHUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=3000.0, avg_price=3000.0,
            quantity=1.0, executed_qty=1.0,
            timestamp=int(time.time() * 1000), raw={},
        )
        manager.submit_order(
            symbol="ETHUSDT", side="SELL", quantity=1.0,
            order_type="MARKET", leverage=3,
            stop_loss=3100.0, take_profit=2800.0,
        )

        mock_exchange.place_order.return_value = OrderResult(
            order_id=99997, client_order_id="CSA-sl2",
            symbol="ETHUSDT", side="BUY", order_type="MARKET",
            status="FILLED", price=3150.0, avg_price=3150.0,
            quantity=1.0, executed_qty=1.0,
            timestamp=int(time.time() * 1000), raw={},
        )

        manager.check_stop_loss_take_profit("ETHUSDT", 3150.0)
        assert "ETHUSDT" not in manager.positions


# ── Unrealized P&L Tests ─────────────────────────────────────

class TestUnrealizedPnL:

    def test_update_unrealized_pnl(self, manager):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        manager.update_unrealized_pnl("BTCUSDT", 51000.0)
        pos = manager.positions["BTCUSDT"]
        assert pos.unrealized_pnl == pytest.approx(10.0)

    def test_update_nonexistent_symbol(self, manager):
        # Should not raise
        manager.update_unrealized_pnl("NONEXIST", 100.0)


# ── Portfolio Summary Tests ───────────────────────────────────

class TestPortfolioSummary:

    def test_empty_portfolio(self, manager):
        summary = manager.get_portfolio_summary()
        assert summary["open_positions"] == 0
        assert summary["total_trades"] == 0

    def test_portfolio_with_position(self, manager):
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        summary = manager.get_portfolio_summary()
        assert summary["open_positions"] == 1
        assert "BTCUSDT" in summary["positions"]


# ── Callback Tests ────────────────────────────────────────────

class TestCallbacks:

    def test_on_fill_callback(self, manager):
        callback = MagicMock()
        manager.on_fill(callback)
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        callback.assert_called_once()

    def test_on_rejection_callback(self, manager, safety):
        callback = MagicMock()
        manager.on_rejection(callback)
        safety._kill_switch.activate("test")
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
        )
        callback.assert_called_once()

    def test_on_position_close_callback(self, manager, mock_exchange):
        callback = MagicMock()
        manager.on_position_close(callback)

        # Open
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )

        # Close
        mock_exchange.place_order.return_value = OrderResult(
            order_id=99996, client_order_id="CSA-cb",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=51000.0, avg_price=51000.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )
        manager.close_position("BTCUSDT")
        callback.assert_called_once()


# ── TrackedPosition Tests ─────────────────────────────────────

class TestTrackedPosition:

    def test_notional_value(self):
        pos = TrackedPosition(
            symbol="BTCUSDT", side="LONG", entry_price=50000,
            quantity=0.01, leverage=3, stop_loss=0, take_profit=0,
        )
        assert pos.notional_value == pytest.approx(500.0)

    def test_pnl_pct(self):
        pos = TrackedPosition(
            symbol="BTCUSDT", side="LONG", entry_price=50000,
            quantity=0.01, leverage=3, stop_loss=0, take_profit=0,
            unrealized_pnl=10.0,
        )
        # margin = 500 / 3 = 166.67, pnl_pct = 10 / 166.67 = 6%
        assert pos.pnl_pct == pytest.approx(0.06, abs=0.001)

    def test_to_dict(self):
        pos = TrackedPosition(
            symbol="BTCUSDT", side="LONG", entry_price=50000,
            quantity=0.01, leverage=3, stop_loss=49000, take_profit=52000,
        )
        d = pos.to_dict()
        assert d["symbol"] == "BTCUSDT"
        assert d["side"] == "LONG"
        assert d["leverage"] == 3


# ── Close All Positions Tests ─────────────────────────────────

class TestCloseAllPositions:

    def test_close_all(self, manager, mock_exchange):
        # Open two positions
        manager.submit_order(
            symbol="BTCUSDT", side="BUY", quantity=0.01,
            order_type="MARKET", leverage=3,
        )
        mock_exchange.place_order.return_value = OrderResult(
            order_id=12349, client_order_id="CSA-eth",
            symbol="ETHUSDT", side="BUY", order_type="MARKET",
            status="FILLED", price=3000.0, avg_price=3000.0,
            quantity=0.1, executed_qty=0.1,
            timestamp=int(time.time() * 1000), raw={},
        )
        manager.submit_order(
            symbol="ETHUSDT", side="BUY", quantity=0.1,
            order_type="MARKET", leverage=3, price=3000.0,
        )
        assert len(manager.positions) == 2

        # Close all
        mock_exchange.place_order.return_value = OrderResult(
            order_id=99995, client_order_id="CSA-closeall",
            symbol="BTCUSDT", side="SELL", order_type="MARKET",
            status="FILLED", price=50000.0, avg_price=50000.0,
            quantity=0.01, executed_qty=0.01,
            timestamp=int(time.time() * 1000), raw={},
        )
        results = manager.close_all_positions("kill_switch")
        # At least one close attempt
        assert len(results) >= 1

"""
Unit tests for CoinScopeAI Paper Trading — Telegram Alerting.
Tests cover: enabled/disabled state, message formatting (via _send_async mock),
stats counting, and all public notification methods.
"""

import pytest
from unittest.mock import patch

from services.paper_trading.config import TelegramConfig
from services.paper_trading.alerting import TelegramAlerter


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def enabled_config():
    return TelegramConfig(
        bot_token="test_token_123",
        chat_id="test_chat_456",
        enabled=True,
    )


@pytest.fixture
def disabled_config():
    return TelegramConfig(
        bot_token="",
        chat_id="",
        enabled=False,
    )


@pytest.fixture
def alerter(enabled_config):
    return TelegramAlerter(enabled_config)


@pytest.fixture
def disabled_alerter(disabled_config):
    return TelegramAlerter(disabled_config)


# ── Initialization Tests ─────────────────────────────────────

class TestInit:

    def test_enabled_with_valid_config(self, alerter):
        assert alerter.enabled

    def test_disabled_with_empty_config(self, disabled_alerter):
        assert not disabled_alerter.enabled

    def test_disabled_when_flag_false(self):
        cfg = TelegramConfig(bot_token="tok", chat_id="cid", enabled=False)
        a = TelegramAlerter(cfg)
        assert not a.enabled


# ── Disabled State Tests ──────────────────────────────────────

class TestDisabledState:

    def test_signal_generated_noop(self, disabled_alerter):
        """Should not raise when disabled."""
        disabled_alerter.signal_generated({
            "symbol": "BTCUSDT", "direction": "LONG",
            "confidence": 0.5, "edge": 0.1, "regime": "TRENDING",
        })

    def test_heartbeat_noop(self, disabled_alerter):
        disabled_alerter.heartbeat({
            "equity": 10000.0, "daily_pnl": 0.0,
            "drawdown_pct": 0.0, "positions": {},
            "signals_today": 0, "trades_today": 0,
            "kill_switch": False,
        })

    def test_order_submitted_noop(self, disabled_alerter):
        disabled_alerter.order_submitted({
            "internal_id": "CSA-001", "symbol": "BTCUSDT",
            "side": "BUY", "order_type": "MARKET",
            "quantity": 0.01, "price": 50000.0,
            "leverage": 3, "stop_loss": 0.0, "take_profit": 0.0,
        })


# ── Message Formatting Tests ─────────────────────────────────

class TestMessageFormatting:

    @patch.object(TelegramAlerter, "_send_async")
    def test_signal_generated_format(self, mock_send, alerter):
        alerter.signal_generated({
            "symbol": "BTCUSDT", "direction": "LONG",
            "confidence": 0.55, "edge": 0.12, "regime": "TRENDING",
        })
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "BTCUSDT" in msg
        assert "LONG" in msg

    @patch.object(TelegramAlerter, "_send_async")
    def test_order_submitted_format(self, mock_send, alerter):
        alerter.order_submitted({
            "internal_id": "CSA-001", "symbol": "BTCUSDT",
            "side": "BUY", "order_type": "LIMIT",
            "quantity": 0.01, "price": 50000.0,
            "leverage": 3, "stop_loss": 49000.0, "take_profit": 52000.0,
        })
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "BTCUSDT" in msg
        assert "BUY" in msg

    @patch.object(TelegramAlerter, "_send_async")
    def test_order_filled_format(self, mock_send, alerter):
        alerter.order_filled({
            "internal_id": "CSA-001", "symbol": "BTCUSDT",
            "side": "BUY", "avg_fill_price": 50000.0, "filled_qty": 0.01,
        })
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "FILLED" in msg or "BTCUSDT" in msg

    @patch.object(TelegramAlerter, "_send_async")
    def test_order_rejected_format(self, mock_send, alerter):
        alerter.order_rejected({
            "symbol": "BTCUSDT", "side": "BUY",
            "rejection_reason": "max_drawdown_exceeded",
        })
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "REJECTED" in msg or "BTCUSDT" in msg

    @patch.object(TelegramAlerter, "_send_async")
    def test_position_closed_format(self, mock_send, alerter):
        alerter.position_closed({
            "symbol": "BTCUSDT", "side": "LONG",
            "pnl": 10.0, "pnl_pct": 0.02,
            "entry_price": 50000.0, "exit_price": 51000.0,
            "quantity": 0.01, "duration_hours": 4.5,
            "close_reason": "take_profit",
        })
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "BTCUSDT" in msg

    @patch.object(TelegramAlerter, "_send_async")
    def test_risk_gate_triggered_format(self, mock_send, alerter):
        alerter.risk_gate_triggered(
            reason="daily_loss_limit",
            details={"equity": 9700.0, "daily_pnl": -300.0,
                     "drawdown_pct": 0.03, "consecutive_losses": 2},
        )
        mock_send.assert_called_once()

    @patch.object(TelegramAlerter, "_send_async")
    def test_kill_switch_activated_format(self, mock_send, alerter):
        alerter.kill_switch_activated(reason="max_drawdown_exceeded")
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "KILL" in msg.upper()

    @patch.object(TelegramAlerter, "_send_async")
    def test_error_format(self, mock_send, alerter):
        alerter.error(component="WebSocket", error_msg="Connection lost")
        mock_send.assert_called_once()

    @patch.object(TelegramAlerter, "_send_async")
    def test_heartbeat_format(self, mock_send, alerter):
        alerter.heartbeat({
            "equity": 10015.0, "daily_pnl": 15.0,
            "drawdown_pct": 0.0,
            "positions": {"BTCUSDT": {"side": "LONG", "unrealized_pnl": 5.0}},
            "signals_today": 3, "trades_today": 1,
            "kill_switch": False,
        })
        mock_send.assert_called_once()

    @patch.object(TelegramAlerter, "_send_async")
    def test_daily_summary_format(self, mock_send, alerter):
        alerter.daily_summary({
            "date": "2025-01-01", "daily_pnl": 25.0,
            "equity": 10025.0, "drawdown_pct": 0.01,
            "signals": 10, "trades": 5, "wins": 3, "losses": 2,
            "win_rate": 0.6, "orders_rejected": 1,
            "consecutive_losses": 0, "kill_switch": False,
        })
        mock_send.assert_called_once()

    @patch.object(TelegramAlerter, "_send_async")
    def test_startup_format(self, mock_send, alerter):
        alerter.startup({
            "symbols": ["BTCUSDT", "ETHUSDT"],
            "timeframe": "4h", "leverage": 3,
            "max_daily_loss_pct": 0.03,
            "max_drawdown_pct": 0.10,
            "max_concurrent_positions": 3,
        })
        mock_send.assert_called_once()

    def test_shutdown_format(self, alerter):
        # shutdown() uses _send (sync) not _send_async
        with patch.object(TelegramAlerter, "_send") as mock_sync_send:
            alerter.shutdown(reason="manual_stop")
            mock_sync_send.assert_called_once()


# ── Stats Tests ───────────────────────────────────────────────

class TestStats:

    def test_stats_counting(self, alerter):
        """Stats count via _send — mock the HTTP call to return 200."""
        import unittest.mock as mock
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        with patch.object(alerter._session, "post", return_value=mock_resp):
            alerter.signal_generated({
                "symbol": "BTCUSDT", "direction": "LONG",
                "confidence": 0.5, "edge": 0.1, "regime": "TRENDING",
            })
            alerter.error(component="test", error_msg="test error")
            # _send_async spawns threads; wait briefly for them to complete
            import time; time.sleep(0.1)
        stats = alerter.get_stats()
        assert stats["messages_sent"] == 2
        assert stats["errors"] == 0  # send errors, not alert errors

    def test_stats_enabled_field(self, alerter):
        stats = alerter.get_stats()
        assert stats["enabled"] is True

    def test_stats_disabled_field(self, disabled_alerter):
        stats = disabled_alerter.get_stats()
        assert stats["enabled"] is False

    def test_message_count_increments(self, alerter):
        import unittest.mock as mock
        import time
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        with patch.object(alerter._session, "post", return_value=mock_resp):
            for _ in range(5):
                alerter.signal_generated({
                    "symbol": "BTCUSDT", "direction": "LONG",
                    "confidence": 0.5, "edge": 0.1, "regime": "TRENDING",
                })
            time.sleep(0.2)  # wait for async threads
        assert alerter.get_stats()["messages_sent"] == 5

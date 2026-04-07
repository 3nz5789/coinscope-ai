"""
CoinScopeAI Paper Trading — Telegram Alerting System
=======================================================
Sends structured notifications for all trading events:
signals, orders, fills, position closes, P&L updates,
risk gate triggers, errors, heartbeats, and daily summaries.

Uses the Telegram Bot API directly (no external library needed).
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from .config import TelegramConfig

logger = logging.getLogger("coinscopeai.paper_trading.alerting")


class TelegramAlerter:
    """
    Sends formatted Telegram messages for all trading events.
    Non-blocking: messages are queued and sent asynchronously.
    """

    API_BASE = "https://api.telegram.org"
    MAX_MESSAGE_LENGTH = 4000  # Telegram limit is 4096

    def __init__(self, config: Optional[TelegramConfig] = None):
        self._config = config or TelegramConfig()
        self._session = requests.Session()
        self._send_lock = threading.Lock()
        self._message_count = 0
        self._error_count = 0

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._config.bot_token) and bool(self._config.chat_id)

    def _send(self, text: str, parse_mode: str = "HTML"):
        """Send a message via Telegram Bot API."""
        if not self.enabled:
            logger.debug("Telegram disabled, skipping message")
            return

        # Truncate if too long
        if len(text) > self.MAX_MESSAGE_LENGTH:
            text = text[:self.MAX_MESSAGE_LENGTH - 20] + "\n\n... (truncated)"

        url = f"{self.API_BASE}/bot{self._config.bot_token}/sendMessage"
        payload = {
            "chat_id": self._config.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            with self._send_lock:
                resp = self._session.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    self._message_count += 1
                else:
                    self._error_count += 1
                    logger.warning("Telegram send failed: %d %s", resp.status_code, resp.text[:200])
        except Exception as e:
            self._error_count += 1
            logger.error("Telegram error: %s", e)

    def _send_async(self, text: str, parse_mode: str = "HTML"):
        """Send message in a background thread to avoid blocking."""
        t = threading.Thread(target=self._send, args=(text, parse_mode), daemon=True)
        t.start()

    def _ts(self) -> str:
        """Current UTC timestamp string."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Event Notifications ───────────────────────────────────

    def signal_generated(self, signal: Dict):
        """Notify: new ML signal generated."""
        direction = signal.get("direction", "?")
        emoji = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"

        text = (
            f"{emoji} <b>NEW SIGNAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Symbol: <code>{signal.get('symbol', '?')}</code>\n"
            f"Direction: <b>{direction}</b>\n"
            f"Confidence: {signal.get('confidence', 0):.1%}\n"
            f"Edge: {signal.get('edge', 0):.1%}\n"
            f"Regime: {signal.get('regime', '?')}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def order_submitted(self, order: Dict):
        """Notify: order submitted to exchange."""
        text = (
            f"📤 <b>ORDER SUBMITTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"ID: <code>{order.get('internal_id', '?')}</code>\n"
            f"Symbol: <code>{order.get('symbol', '?')}</code>\n"
            f"Side: {order.get('side', '?')}\n"
            f"Type: {order.get('order_type', '?')}\n"
            f"Qty: {order.get('quantity', 0):.6f}\n"
            f"Price: {order.get('price', 0):.2f}\n"
            f"Leverage: {order.get('leverage', 0)}x\n"
            f"SL: {order.get('stop_loss', 0):.2f}\n"
            f"TP: {order.get('take_profit', 0):.2f}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def order_filled(self, order: Dict):
        """Notify: order filled."""
        text = (
            f"✅ <b>ORDER FILLED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"ID: <code>{order.get('internal_id', '?')}</code>\n"
            f"Symbol: <code>{order.get('symbol', '?')}</code>\n"
            f"Side: {order.get('side', '?')}\n"
            f"Fill Price: {order.get('avg_fill_price', 0):.2f}\n"
            f"Qty: {order.get('filled_qty', 0):.6f}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def order_rejected(self, order: Dict):
        """Notify: order rejected by safety gate."""
        text = (
            f"🚫 <b>ORDER REJECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Symbol: <code>{order.get('symbol', '?')}</code>\n"
            f"Side: {order.get('side', '?')}\n"
            f"Reason: {order.get('rejection_reason', '?')}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def position_closed(self, trade: Dict):
        """Notify: position closed."""
        pnl = trade.get("pnl", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        emoji = "💰" if pnl > 0 else "💸"

        text = (
            f"{emoji} <b>POSITION CLOSED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Symbol: <code>{trade.get('symbol', '?')}</code>\n"
            f"Side: {trade.get('side', '?')}\n"
            f"Entry: {trade.get('entry_price', 0):.2f}\n"
            f"Exit: {trade.get('exit_price', 0):.2f}\n"
            f"P&L: <b>{pnl:+.2f} USDT ({pnl_pct:+.2%})</b>\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def risk_gate_triggered(self, reason: str, details: Dict):
        """Notify: risk gate or circuit breaker triggered."""
        text = (
            f"🔴 <b>RISK GATE TRIGGERED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Reason: <b>{reason}</b>\n"
            f"Equity: {details.get('equity', 0):.2f}\n"
            f"Daily P&L: {details.get('daily_pnl', 0):+.2f}\n"
            f"Drawdown: {details.get('drawdown_pct', 0):.1%}\n"
            f"Consecutive Losses: {details.get('consecutive_losses', 0)}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def kill_switch_activated(self, reason: str):
        """Notify: KILL SWITCH activated — critical alert."""
        text = (
            f"🚨🚨🚨 <b>KILL SWITCH ACTIVATED</b> 🚨🚨🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Reason: <b>{reason}</b>\n"
            f"ALL TRADING HALTED\n"
            f"Manual intervention required.\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def error(self, component: str, error_msg: str):
        """Notify: system error."""
        text = (
            f"⚠️ <b>SYSTEM ERROR</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Component: {component}\n"
            f"Error: <code>{error_msg[:500]}</code>\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def heartbeat(self, status: Dict):
        """Notify: system heartbeat (every 15 minutes)."""
        positions = status.get("positions", {})
        pos_text = ""
        if positions:
            for sym, pos in positions.items():
                pnl = pos.get("unrealized_pnl", 0)
                pos_text += f"  {sym}: {pos.get('side', '?')} {pnl:+.2f}\n"
        else:
            pos_text = "  (none)\n"

        text = (
            f"💓 <b>HEARTBEAT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Status: {'🟢 ACTIVE' if not status.get('kill_switch', False) else '🔴 HALTED'}\n"
            f"Equity: {status.get('equity', 0):.2f} USDT\n"
            f"Daily P&L: {status.get('daily_pnl', 0):+.2f}\n"
            f"Drawdown: {status.get('drawdown_pct', 0):.1%}\n"
            f"Open Positions:\n{pos_text}"
            f"Signals Today: {status.get('signals_today', 0)}\n"
            f"Trades Today: {status.get('trades_today', 0)}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def daily_summary(self, summary: Dict):
        """Notify: end-of-day summary."""
        text = (
            f"📊 <b>DAILY SUMMARY</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Date: {summary.get('date', '?')}\n"
            f"\n<b>Performance</b>\n"
            f"  Daily P&L: {summary.get('daily_pnl', 0):+.2f} USDT\n"
            f"  Equity: {summary.get('equity', 0):.2f} USDT\n"
            f"  Drawdown: {summary.get('drawdown_pct', 0):.1%}\n"
            f"\n<b>Trading Activity</b>\n"
            f"  Signals: {summary.get('signals', 0)}\n"
            f"  Trades: {summary.get('trades', 0)}\n"
            f"  Wins: {summary.get('wins', 0)}\n"
            f"  Losses: {summary.get('losses', 0)}\n"
            f"  Win Rate: {summary.get('win_rate', 0):.1%}\n"
            f"\n<b>Risk</b>\n"
            f"  Orders Rejected: {summary.get('orders_rejected', 0)}\n"
            f"  Consecutive Losses: {summary.get('consecutive_losses', 0)}\n"
            f"  Kill Switch: {'🔴 ACTIVE' if summary.get('kill_switch', False) else '🟢 OFF'}\n"
            f"\nTime: {self._ts()}"
        )
        self._send_async(text)

    def startup(self, config_summary: Dict):
        """Notify: system startup."""
        text = (
            f"🚀 <b>CoinScopeAI Paper Trading STARTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Mode: TESTNET\n"
            f"Symbols: {', '.join(config_summary.get('symbols', []))}\n"
            f"Timeframe: {config_summary.get('timeframe', '?')}\n"
            f"Leverage: {config_summary.get('leverage', '?')}x\n"
            f"Max Daily Loss: {config_summary.get('max_daily_loss_pct', 0):.0%}\n"
            f"Max Drawdown: {config_summary.get('max_drawdown_pct', 0):.0%}\n"
            f"Max Positions: {config_summary.get('max_concurrent_positions', 0)}\n"
            f"Time: {self._ts()}"
        )
        self._send_async(text)

    def shutdown(self, reason: str = "normal"):
        """Notify: system shutdown."""
        text = (
            f"🛑 <b>CoinScopeAI Paper Trading STOPPED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Reason: {reason}\n"
            f"Messages Sent: {self._message_count}\n"
            f"Errors: {self._error_count}\n"
            f"Time: {self._ts()}"
        )
        # Send synchronously on shutdown
        self._send(text)

    def get_stats(self) -> Dict:
        return {
            "enabled": self.enabled,
            "messages_sent": self._message_count,
            "errors": self._error_count,
        }

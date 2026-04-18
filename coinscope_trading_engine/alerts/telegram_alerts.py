"""
Telegram Alerts - Real-time notifications

Sends trading signals, closed trades, and alerts via Telegram bot.
Falls back to console printing if credentials not configured.
"""

import os
import requests
from datetime import datetime


class TelegramAlerts:
    """Telegram bot alert sender"""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)

    def _send(self, text: str):
        """Send message via Telegram"""
        if not self.enabled:
            print(f"[TELEGRAM] {text}")
            return
        
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=5,
            )
        except Exception as e:
            print(f"Telegram error: {e}")

    def send_signal(
        self, symbol: str, direction: str, regime: str, confidence: float, price: float, kelly_usd: float
    ):
        """Send trading signal alert"""
        emoji = "🟢" if direction == "LONG" else "🔴"
        self._send(
            f"{emoji} *{direction} Signal*\n"
            f"Pair: `{symbol}`\n"
            f"Price: `${price:,.4f}`\n"
            f"Regime: `{regime.upper()}` ({confidence:.0%})\n"
            f"Kelly Size: `${kelly_usd:.2f}`\n"
            f"_{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_"
        )

    def send_trade_closed(self, symbol: str, pnl_pct: float, pnl_usd: float, equity: float):
        """Send trade closed alert"""
        emoji = "✅" if pnl_pct > 0 else "❌"
        self._send(
            f"{emoji} *Trade Closed* — `{symbol}`\n"
            f"PnL: `{pnl_pct:+.2%}` (${pnl_usd:+.2f})\n"
            f"Equity: `${equity:,.2f}`"
        )

    def send_alert(self, level: str, message: str):
        """Send generic alert"""
        emoji = {"INFO": "ℹ️", "WARN": "⚠️", "CRITICAL": "🚨"}.get(level, "📢")
        self._send(f"{emoji} *{level}*\n{message}")

    def send_heartbeat(self, stats: dict):
        """Send hourly heartbeat"""
        self._send(
            f"💓 *Hourly Heartbeat*\n"
            f"Trades: `{stats.get('trades', 0)}`\n"
            f"Win Rate: `{stats.get('win_rate', 0):.1%}`\n"
            f"Equity: `${stats.get('equity', 0):,.2f}`\n"
            f"Daily PnL: `{stats.get('daily_pnl', 0):+.2%}`"
        )

    def send_info(self, message: str):
        """Send info alert"""
        self.send_alert("INFO", message)

    def send_critical(self, message: str):
        """Send critical alert"""
        self.send_alert("CRITICAL", message)

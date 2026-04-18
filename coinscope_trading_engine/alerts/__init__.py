"""
alerts — CoinScopeAI Notification Layer
========================================
Exports all alert-related classes used by the engine core.
"""

from alerts.telegram_notifier import TelegramNotifier
from alerts.webhook_dispatcher import WebhookDispatcher
from alerts.alert_queue import AlertQueue, AlertPriority, AlertType
from alerts.rate_limiter import AlertRateLimiter

__all__ = [
    "TelegramNotifier",
    "WebhookDispatcher",
    "AlertQueue",
    "AlertPriority",
    "AlertType",
    "AlertRateLimiter",
]

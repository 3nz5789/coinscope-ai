"""CoinScopeAI Market Data — multi-exchange WebSocket price stream infrastructure."""

from .models import (
    Exchange,
    Side,
    ConnectionState,
    MarkPrice,
    OrderBook,
    OrderBookLevel,
    Trade,
    FundingRate,
    OpenInterest,
    Ticker,
    ConnectionMetrics,
    ScanSignal,
    EventType,
    MarketEvent,
)
from .base import BaseExchangeClient, EventBus, RateLimiter
from .aggregator import Aggregator

__all__ = [
    "Exchange", "Side", "ConnectionState",
    "MarkPrice", "OrderBook", "OrderBookLevel", "Trade",
    "FundingRate", "OpenInterest", "Ticker",
    "ConnectionMetrics", "ScanSignal", "EventType", "MarketEvent",
    "BaseExchangeClient", "EventBus", "RateLimiter",
    "Aggregator",
]

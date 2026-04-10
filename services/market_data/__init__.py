"""CoinScopeAI Market Data — multi-exchange WebSocket price stream infrastructure."""

from .models import (
    Exchange,
    Side,
    L2OrderBook,
    OrderBookLevel,
    Trade,
    FundingRate,
    OpenInterest,
    ConnectionState,
    MarkPrice,
    Ticker,
    ConnectionMetrics,
    EventType,
    MarketEvent,
    ScanSignal,
    OrderBook,
)
from .base import BaseExchangeClient, EventBus, RateLimiter
from .aggregator import Aggregator

__all__ = [
    "Exchange", "Side",
    "L2OrderBook", "OrderBook", "OrderBookLevel", "Trade",
    "FundingRate", "OpenInterest",
    "ConnectionState", "MarkPrice", "Ticker", "ConnectionMetrics",
    "EventType", "MarketEvent", "ScanSignal",
    "BaseExchangeClient", "EventBus", "RateLimiter",
    "Aggregator",
]

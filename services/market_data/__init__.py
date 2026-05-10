"""CoinScopeAI Market Data — multi-exchange WebSocket price stream infrastructure."""

from .aggregator import Aggregator
from .base import BaseExchangeClient, EventBus, RateLimiter
from .models import (
    ConnectionMetrics,
    ConnectionState,
    EventType,
    Exchange,
    FundingRate,
    L2OrderBook,
    MarketEvent,
    MarkPrice,
    OpenInterest,
    OrderBook,
    OrderBookLevel,
    ScanSignal,
    Side,
    Ticker,
    Trade,
)

__all__ = [
    "Exchange", "Side",
    "L2OrderBook", "OrderBook", "OrderBookLevel", "Trade",
    "FundingRate", "OpenInterest",
    "ConnectionState", "MarkPrice", "Ticker", "ConnectionMetrics",
    "EventType", "MarketEvent", "ScanSignal",
    "BaseExchangeClient", "EventBus", "RateLimiter",
    "Aggregator",
]

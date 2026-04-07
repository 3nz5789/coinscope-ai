"""
CoinScopeAI — Unified Data Models

Normalized schemas for all market data across exchanges.
Every model carries both normalized fields and the raw exchange payload
so that normalization is lossless.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Exchange(str, Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    HYPERLIQUID = "hyperliquid"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Unified data models
# ---------------------------------------------------------------------------

@dataclass
class MarkPrice:
    """Normalized mark / index price."""
    exchange: Exchange
    symbol: str                     # unified symbol, e.g. "BTCUSDT"
    mark_price: float
    index_price: Optional[float] = None
    estimated_settle_price: Optional[float] = None
    timestamp: float = field(default_factory=time.time)   # epoch seconds
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderBookLevel:
    price: float
    quantity: float


@dataclass
class OrderBook:
    """Normalized order book snapshot / update."""
    exchange: Exchange
    symbol: str
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    sequence: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2.0
        return None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        """Spread in basis points relative to mid price."""
        mid = self.mid_price
        s = self.spread
        if mid and s and mid > 0:
            return (s / mid) * 10_000
        return None


@dataclass
class Trade:
    """Normalized public trade."""
    exchange: Exchange
    symbol: str
    trade_id: str
    price: float
    quantity: float
    side: Side
    timestamp: float = field(default_factory=time.time)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FundingRate:
    """Normalized funding rate."""
    exchange: Exchange
    symbol: str
    funding_rate: float
    predicted_rate: Optional[float] = None
    next_funding_time: Optional[float] = None   # epoch seconds
    timestamp: float = field(default_factory=time.time)
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def annualized_rate(self) -> float:
        """Annualized funding rate assuming 8-hour intervals (3x/day)."""
        return self.funding_rate * 3 * 365


@dataclass
class OpenInterest:
    """Normalized open interest."""
    exchange: Exchange
    symbol: str
    open_interest: float            # in contracts or base currency
    open_interest_value: Optional[float] = None   # in quote currency (USD)
    timestamp: float = field(default_factory=time.time)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Ticker:
    """Normalized ticker / 24h summary."""
    exchange: Exchange
    symbol: str
    last_price: float
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    volume_24h_quote: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Connection / metrics models
# ---------------------------------------------------------------------------

@dataclass
class ConnectionMetrics:
    """Per-connection health metrics."""
    exchange: Exchange
    state: ConnectionState = ConnectionState.DISCONNECTED
    connected_at: Optional[float] = None
    last_message_at: Optional[float] = None
    messages_received: int = 0
    reconnect_count: int = 0
    errors: int = 0
    latency_ms: Optional[float] = None

    @property
    def uptime_seconds(self) -> Optional[float]:
        if self.connected_at:
            return time.time() - self.connected_at
        return None

    @property
    def messages_per_second(self) -> Optional[float]:
        up = self.uptime_seconds
        if up and up > 0:
            return self.messages_received / up
        return None


# ---------------------------------------------------------------------------
# Scanner result models
# ---------------------------------------------------------------------------

@dataclass
class ScanSignal:
    """A signal emitted by a scanner."""
    scanner_name: str
    exchange: Exchange
    symbol: str
    signal_type: str               # e.g. "breakout_oi_expansion"
    strength: float                # 0.0 – 1.0
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Event bus types
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    MARK_PRICE = "mark_price"
    ORDER_BOOK = "order_book"
    TRADE = "trade"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    TICKER = "ticker"
    SCAN_SIGNAL = "scan_signal"
    CONNECTION_STATE = "connection_state"


@dataclass
class MarketEvent:
    """Wrapper that carries any normalized payload through the event bus."""
    event_type: EventType
    data: Any                       # one of the model types above
    exchange: Exchange
    symbol: str
    timestamp: float = field(default_factory=time.time)

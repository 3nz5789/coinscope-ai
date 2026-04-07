"""
CoinScopeAI Market Data — Core Types
=======================================
Standardized data types for all market data flowing through the system.
Exchange-agnostic — each stream adapter normalizes to these types.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time


class Exchange(Enum):
    """Supported exchanges."""
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    DERIBIT = "deribit"


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


# ── Topic Naming Convention ──────────────────────────────────
# Format: {data_type}.{symbol}.{exchange}
# Examples:
#   trade.BTCUSDT.binance
#   orderbook.ETHUSDT.bybit
#   funding.BTCUSDT.binance
#   liquidation.SOLUSDT.okx
#   kline.BTCUSDT.binance.4h
#   alpha.funding_extreme.BTCUSDT
#   regime.BTCUSDT


def trade_topic(symbol: str, exchange: str) -> str:
    return f"trade.{symbol}.{exchange}"


def orderbook_topic(symbol: str, exchange: str) -> str:
    return f"orderbook.{symbol}.{exchange}"


def funding_topic(symbol: str, exchange: str) -> str:
    return f"funding.{symbol}.{exchange}"


def liquidation_topic(symbol: str, exchange: str) -> str:
    return f"liquidation.{symbol}.{exchange}"


def kline_topic(symbol: str, exchange: str, interval: str) -> str:
    return f"kline.{symbol}.{exchange}.{interval}"


def alpha_topic(signal_type: str, symbol: str) -> str:
    return f"alpha.{signal_type}.{symbol}"


def regime_topic(symbol: str) -> str:
    return f"regime.{symbol}"


# ── Market Data Types ────────────────────────────────────────

@dataclass
class Trade:
    """A single trade (tick)."""
    symbol: str
    exchange: str
    price: float
    quantity: float
    side: str           # "buy" or "sell"
    timestamp: float    # Unix timestamp in seconds
    trade_id: str = ""
    is_maker: bool = False

    @property
    def notional(self) -> float:
        return self.price * self.quantity

    @property
    def topic(self) -> str:
        return trade_topic(self.symbol, self.exchange)


@dataclass
class OrderBookLevel:
    """A single price level in the order book."""
    price: float
    quantity: float


@dataclass
class OrderBookSnapshot:
    """L2 order book snapshot (top N levels)."""
    symbol: str
    exchange: str
    bids: List[OrderBookLevel]  # Sorted descending by price
    asks: List[OrderBookLevel]  # Sorted ascending by price
    timestamp: float
    sequence: int = 0

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    @property
    def mid_price(self) -> float:
        bb, ba = self.best_bid, self.best_ask
        return (bb + ba) / 2 if bb and ba else 0.0

    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid

    @property
    def spread_bps(self) -> float:
        mid = self.mid_price
        return (self.spread / mid * 10_000) if mid > 0 else 0.0

    @property
    def bid_depth(self) -> float:
        """Total bid liquidity in quote currency."""
        return sum(l.price * l.quantity for l in self.bids)

    @property
    def ask_depth(self) -> float:
        """Total ask liquidity in quote currency."""
        return sum(l.price * l.quantity for l in self.asks)

    @property
    def imbalance(self) -> float:
        """Order book imbalance: (bid_depth - ask_depth) / (bid_depth + ask_depth)."""
        total = self.bid_depth + self.ask_depth
        return (self.bid_depth - self.ask_depth) / total if total > 0 else 0.0

    @property
    def topic(self) -> str:
        return orderbook_topic(self.symbol, self.exchange)


@dataclass
class FundingRate:
    """Perpetual futures funding rate."""
    symbol: str
    exchange: str
    rate: float             # Funding rate (e.g., 0.0001 = 0.01%)
    next_funding_time: float  # Unix timestamp
    timestamp: float
    mark_price: float = 0.0
    index_price: float = 0.0

    @property
    def annualized(self) -> float:
        """Annualized funding rate (3 payments per day × 365)."""
        return self.rate * 3 * 365

    @property
    def topic(self) -> str:
        return funding_topic(self.symbol, self.exchange)


@dataclass
class Liquidation:
    """A liquidation event."""
    symbol: str
    exchange: str
    side: str           # "buy" (short liquidated) or "sell" (long liquidated)
    price: float
    quantity: float
    timestamp: float

    @property
    def notional(self) -> float:
        return self.price * self.quantity

    @property
    def topic(self) -> str:
        return liquidation_topic(self.symbol, self.exchange)


@dataclass
class Kline:
    """A candlestick/kline bar."""
    symbol: str
    exchange: str
    interval: str
    open_time: float
    close_time: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool
    trades: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def topic(self) -> str:
        return kline_topic(self.symbol, self.exchange, self.interval)


# ── Alpha Signal Types ───────────────────────────────────────

@dataclass
class AlphaSignal:
    """An alpha signal generated by the alpha engine."""
    signal_type: str    # e.g., "funding_extreme", "liquidation_cascade"
    symbol: str
    direction: str      # "LONG", "SHORT", "NEUTRAL"
    strength: float     # 0.0 to 1.0
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: float = 3600.0  # Signal validity period

    @property
    def is_expired(self) -> bool:
        return time.time() > self.timestamp + self.ttl_seconds

    @property
    def topic(self) -> str:
        return alpha_topic(self.signal_type, self.symbol)


@dataclass
class RegimeState:
    """Market regime classification for a symbol."""
    symbol: str
    regime: str             # "trending_up", "trending_down", "ranging", "volatile"
    confidence: float       # 0.0 to 1.0
    volatility_percentile: float  # 0-100
    trend_strength: float   # -1.0 to 1.0
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def topic(self) -> str:
        return regime_topic(self.symbol)

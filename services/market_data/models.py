"""
CoinScopeAI Phase 2 — Unified Data Models

Extends Phase 1 models with alpha signals, regime states, liquidation data,
funding snapshots, order book depth, and cross-exchange aggregated metrics.
"""

from __future__ import annotations

import enum
import time as _time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Exchange(str, enum.Enum):
    """Supported exchanges across the system."""
    HYPERLIQUID = "hyperliquid"
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    DERIBIT = "deribit"
    COINGLASS = "coinglass"  # aggregated source


class Side(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class MarketRegime(str, enum.Enum):
    """Market regime classification labels."""
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    VOLATILE = "volatile"
    LOW_LIQUIDITY = "low_liquidity"
    UNKNOWN = "unknown"


class SignalDirection(str, enum.Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Core Market Data (Phase 1 compatible)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrderBookLevel:
    """Single price level in an order book."""
    price: float
    size: float
    num_orders: int = 1


@dataclass
class L2OrderBook:
    """Full Level-2 order book snapshot."""
    symbol: str
    exchange: Exchange
    timestamp: float
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2.0
        return None

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> Optional[float]:
        mid = self.mid_price
        spread = self.spread
        if mid and spread and mid > 0:
            return (spread / mid) * 10_000
        return None


@dataclass
class Trade:
    """Normalized trade record."""
    symbol: str
    exchange: Exchange
    price: float
    size: float
    side: Side
    timestamp: float
    trade_id: str = ""


# ---------------------------------------------------------------------------
# Funding Rate Models
# ---------------------------------------------------------------------------

@dataclass
class FundingRate:
    """Single funding rate observation."""
    symbol: str
    exchange: Exchange
    rate: float
    timestamp: float
    premium: float = 0.0
    next_funding_time: Optional[float] = None


@dataclass
class PredictedFunding:
    """Predicted next funding rate for a venue."""
    symbol: str
    venue: str  # e.g. "HlPerp", "BinPerp", "BybitPerp"
    predicted_rate: float
    next_funding_time: float


@dataclass
class FundingSnapshot:
    """Cross-exchange funding snapshot for a single symbol at a point in time."""
    symbol: str
    timestamp: float
    rates: Dict[str, float] = field(default_factory=dict)  # exchange -> rate
    predicted: Optional[Dict[str, PredictedFunding]] = None

    @property
    def mean_rate(self) -> float:
        if not self.rates:
            return 0.0
        return sum(self.rates.values()) / len(self.rates)

    @property
    def max_divergence(self) -> float:
        if len(self.rates) < 2:
            return 0.0
        vals = list(self.rates.values())
        return max(vals) - min(vals)


# ---------------------------------------------------------------------------
# Asset Context (Hyperliquid-specific enriched data)
# ---------------------------------------------------------------------------

@dataclass
class AssetContext:
    """Per-asset context from Hyperliquid (funding, OI, mark price, etc.)."""
    symbol: str
    funding_rate: float
    mark_price: float
    mid_price: Optional[float]
    oracle_price: float
    open_interest: float
    day_notional_volume: float
    premium: float
    prev_day_price: float
    impact_prices: Optional[List[float]] = None
    timestamp: float = field(default_factory=_time.time)


# ---------------------------------------------------------------------------
# Open Interest Models
# ---------------------------------------------------------------------------

@dataclass
class OpenInterest:
    """Open interest observation for a single exchange."""
    symbol: str
    exchange: Exchange
    oi_value: float  # in USD or contracts depending on source
    timestamp: float


@dataclass
class AggregatedOI:
    """Cross-exchange aggregated open interest."""
    symbol: str
    timestamp: float
    by_exchange: Dict[str, float] = field(default_factory=dict)

    @property
    def total_oi(self) -> float:
        return sum(self.by_exchange.values())


# ---------------------------------------------------------------------------
# Liquidation Models
# ---------------------------------------------------------------------------

@dataclass
class Liquidation:
    """Single liquidation event."""
    symbol: str
    exchange: Exchange
    side: Side  # LONG = long liquidated, SHORT = short liquidated
    price: float
    quantity: float
    usd_value: float
    timestamp: float


@dataclass
class LiquidationSnapshot:
    """Aggregated liquidation data over a time window."""
    symbol: str
    timestamp: float
    window_seconds: int
    long_liquidations_usd: float = 0.0
    short_liquidations_usd: float = 0.0
    total_count: int = 0
    by_exchange: Dict[str, float] = field(default_factory=dict)

    @property
    def total_usd(self) -> float:
        return self.long_liquidations_usd + self.short_liquidations_usd

    @property
    def long_short_ratio(self) -> Optional[float]:
        if self.short_liquidations_usd > 0:
            return self.long_liquidations_usd / self.short_liquidations_usd
        return None


# ---------------------------------------------------------------------------
# Basis / Futures Premium Models
# ---------------------------------------------------------------------------

@dataclass
class BasisData:
    """Futures basis (premium/discount) for a symbol."""
    symbol: str
    exchange: Exchange
    spot_price: float
    futures_price: float
    timestamp: float
    expiry: Optional[str] = None  # for dated futures

    @property
    def basis(self) -> float:
        return self.futures_price - self.spot_price

    @property
    def basis_pct(self) -> float:
        if self.spot_price > 0:
            return (self.basis / self.spot_price) * 100.0
        return 0.0

    @property
    def annualized_basis(self) -> float:
        """Annualized basis assuming perpetual (8h funding cycle)."""
        return self.basis_pct * 365.25 * 3  # 3 funding periods per day


@dataclass
class AggregatedBasis:
    """Cross-exchange basis snapshot."""
    symbol: str
    timestamp: float
    by_exchange: Dict[str, BasisData] = field(default_factory=dict)

    @property
    def mean_basis_pct(self) -> float:
        if not self.by_exchange:
            return 0.0
        return sum(b.basis_pct for b in self.by_exchange.values()) / len(self.by_exchange)


# ---------------------------------------------------------------------------
# Alpha Signal (output of feature generators)
# ---------------------------------------------------------------------------

@dataclass
class AlphaSignal:
    """
    Standardized output from any alpha feature generator.

    Every generator must produce AlphaSignal objects with consistent schema
    so downstream consumers (regime enricher, strategy engine) can treat
    them uniformly.
    """
    signal_name: str
    symbol: str
    value: float
    z_score: float
    timestamp: float
    confidence: float  # 0.0 – 1.0
    direction: SignalDirection = SignalDirection.NEUTRAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, self.confidence))


# ---------------------------------------------------------------------------
# Regime State (output of regime enricher)
# ---------------------------------------------------------------------------

@dataclass
class RegimeState:
    """
    Market regime classification result.

    Contains the primary regime label plus confidence scores for each
    possible regime, allowing downstream consumers to blend regimes.
    """
    symbol: str
    regime: MarketRegime
    confidence: float
    timestamp: float
    scores: Dict[str, float] = field(default_factory=dict)  # regime -> score
    contributing_signals: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7


# ---------------------------------------------------------------------------
# Configuration Helpers
# ---------------------------------------------------------------------------

@dataclass
class AlphaGeneratorConfig:
    """Shared configuration for alpha feature generators."""
    lookback_periods: int = 24  # number of observations for rolling stats
    z_score_threshold: float = 2.0
    min_data_points: int = 5
    decay_factor: float = 0.94  # exponential decay for weighting
    extra: Dict[str, Any] = field(default_factory=dict)

"""
CoinScopeAI Market Data — Regime Detector
=============================================
Real-time market regime classification using streaming market data.

Regimes:
  - trending_up: Strong upward momentum with low volatility relative to trend
  - trending_down: Strong downward momentum
  - ranging: Low volatility, mean-reverting price action
  - volatile: High volatility, no clear direction

Uses:
  - Trade-derived price returns and volatility
  - Order book imbalance persistence
  - Funding rate direction
  - Liquidation intensity

Publishes RegimeState events to the EventBus.
"""

import logging
import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..event_bus import Event, EventBus
from ..types import (
    AlphaSignal,
    FundingRate,
    Liquidation,
    OrderBookSnapshot,
    RegimeState,
    Trade,
    regime_topic,
)

logger = logging.getLogger("coinscopeai.market_data.regime")


@dataclass
class RegimeConfig:
    """Configuration for regime detection."""
    # Price return windows (in number of trades)
    short_window: int = 100         # ~1-5 minutes of trades
    medium_window: int = 500        # ~15-30 minutes
    long_window: int = 2000         # ~1-4 hours

    # Volatility thresholds (annualized)
    low_vol_threshold: float = 0.30     # 30% annualized
    high_vol_threshold: float = 0.80    # 80% annualized

    # Trend strength thresholds
    trend_threshold: float = 0.3        # ADX-like threshold
    strong_trend_threshold: float = 0.6

    # Update frequency
    update_interval: float = 60.0       # Publish regime update every 60 seconds
    min_trades_for_regime: int = 200     # Need at least 200 trades before classifying


class RegimeDetector:
    """
    Real-time regime detector for each symbol.
    Subscribes to trades, orderbook, and funding data.
    Publishes RegimeState events.
    """

    def __init__(
        self,
        event_bus: EventBus,
        symbols: List[str],
        config: Optional[RegimeConfig] = None,
    ):
        self._bus = event_bus
        self._symbols = symbols
        self._config = config or RegimeConfig()
        self._lock = threading.Lock()

        # Per-symbol state
        self._trade_prices: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self._config.long_window * 2)
        )
        self._trade_timestamps: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self._config.long_window * 2)
        )
        self._ob_imbalances: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=200)
        )
        self._funding_rates: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=50)
        )
        self._liq_intensity: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=200)
        )

        # Current regime state per symbol
        self._current_regime: Dict[str, RegimeState] = {}
        self._last_update: Dict[str, float] = {}

        # Subscribe to data feeds
        self._bus.subscribe("regime_trades", "trade.*.*", self._on_trade)
        self._bus.subscribe("regime_ob", "orderbook.*.*", self._on_orderbook)
        self._bus.subscribe("regime_funding", "funding.*.*", self._on_funding)
        self._bus.subscribe("regime_liq", "liquidation.*.*", self._on_liquidation)

    def _on_trade(self, event: Event):
        trade: Trade = event.data
        if trade.symbol not in self._symbols:
            return

        with self._lock:
            self._trade_prices[trade.symbol].append(trade.price)
            self._trade_timestamps[trade.symbol].append(trade.timestamp)

        self._maybe_update(trade.symbol)

    def _on_orderbook(self, event: Event):
        ob: OrderBookSnapshot = event.data
        if ob.symbol not in self._symbols:
            return

        with self._lock:
            self._ob_imbalances[ob.symbol].append(ob.imbalance)

    def _on_funding(self, event: Event):
        fr: FundingRate = event.data
        if fr.symbol not in self._symbols:
            return

        with self._lock:
            self._funding_rates[fr.symbol].append(fr.rate)

    def _on_liquidation(self, event: Event):
        liq: Liquidation = event.data
        if liq.symbol not in self._symbols:
            return

        with self._lock:
            # Track liquidation intensity as signed notional
            sign = 1.0 if liq.side == "buy" else -1.0
            self._liq_intensity[liq.symbol].append(sign * liq.notional)

    def _maybe_update(self, symbol: str):
        """Check if we should update the regime classification."""
        now = time.time()
        last = self._last_update.get(symbol, 0)
        if now - last < self._config.update_interval:
            return

        with self._lock:
            prices = list(self._trade_prices.get(symbol, []))
            timestamps = list(self._trade_timestamps.get(symbol, []))
            ob_imbs = list(self._ob_imbalances.get(symbol, []))
            funding = list(self._funding_rates.get(symbol, []))
            liqs = list(self._liq_intensity.get(symbol, []))

        if len(prices) < self._config.min_trades_for_regime:
            return

        self._last_update[symbol] = now

        # Calculate regime features
        regime = self._classify(symbol, prices, timestamps, ob_imbs, funding, liqs)

        with self._lock:
            self._current_regime[symbol] = regime

        # Publish
        self._bus.publish(Event(
            topic=regime.topic,
            data=regime,
            source="regime_detector",
        ))

    def _classify(
        self,
        symbol: str,
        prices: List[float],
        timestamps: List[float],
        ob_imbs: List[float],
        funding: List[float],
        liqs: List[float],
    ) -> RegimeState:
        """Classify the current market regime."""

        # ── Price-based features ──
        short_prices = prices[-self._config.short_window:]
        medium_prices = prices[-self._config.medium_window:]
        long_prices = prices[-self._config.long_window:]

        # Returns
        short_return = (short_prices[-1] / short_prices[0] - 1) if len(short_prices) > 1 else 0
        medium_return = (medium_prices[-1] / medium_prices[0] - 1) if len(medium_prices) > 1 else 0

        # Volatility (realized, annualized from trade-to-trade returns)
        if len(short_prices) > 10:
            log_returns = [
                math.log(short_prices[i] / short_prices[i - 1])
                for i in range(1, len(short_prices))
                if short_prices[i - 1] > 0
            ]
            if log_returns:
                vol = (sum(r ** 2 for r in log_returns) / len(log_returns)) ** 0.5
                # Annualize: estimate trades per year
                if len(timestamps) > 1:
                    time_span = timestamps[-1] - timestamps[0]
                    trades_per_sec = len(timestamps) / max(time_span, 1)
                    trades_per_year = trades_per_sec * 86400 * 365
                    annualized_vol = vol * math.sqrt(trades_per_year) if trades_per_year > 0 else 0
                else:
                    annualized_vol = 0
            else:
                annualized_vol = 0
        else:
            annualized_vol = 0

        # Trend strength: ratio of net move to total path length
        if len(medium_prices) > 1:
            net_move = abs(medium_prices[-1] - medium_prices[0])
            path_length = sum(
                abs(medium_prices[i] - medium_prices[i - 1])
                for i in range(1, len(medium_prices))
            )
            trend_strength = net_move / path_length if path_length > 0 else 0
            trend_direction = 1.0 if medium_return > 0 else -1.0
            signed_trend = trend_strength * trend_direction
        else:
            trend_strength = 0
            signed_trend = 0

        # ── Order book imbalance ──
        avg_ob_imb = sum(ob_imbs[-30:]) / max(len(ob_imbs[-30:]), 1) if ob_imbs else 0

        # ── Funding rate ──
        avg_funding = sum(funding[-10:]) / max(len(funding[-10:]), 1) if funding else 0

        # ── Volatility percentile (simple estimate) ──
        vol_percentile = 50.0
        if annualized_vol < self._config.low_vol_threshold:
            vol_percentile = 20.0
        elif annualized_vol > self._config.high_vol_threshold:
            vol_percentile = 90.0
        else:
            # Linear interpolation
            range_vol = self._config.high_vol_threshold - self._config.low_vol_threshold
            vol_percentile = 20 + 70 * (annualized_vol - self._config.low_vol_threshold) / range_vol

        # ── Regime classification ──
        if annualized_vol > self._config.high_vol_threshold:
            regime = "volatile"
            confidence = min(annualized_vol / (self._config.high_vol_threshold * 1.5), 1.0)
        elif trend_strength > self._config.strong_trend_threshold:
            regime = "trending_up" if medium_return > 0 else "trending_down"
            confidence = min(trend_strength / 0.8, 1.0)
        elif trend_strength > self._config.trend_threshold:
            regime = "trending_up" if medium_return > 0 else "trending_down"
            confidence = trend_strength
        elif annualized_vol < self._config.low_vol_threshold:
            regime = "ranging"
            confidence = 1.0 - (annualized_vol / self._config.low_vol_threshold)
        else:
            # Ambiguous — use order book imbalance as tiebreaker
            if abs(avg_ob_imb) > 0.2:
                regime = "trending_up" if avg_ob_imb > 0 else "trending_down"
                confidence = 0.4
            else:
                regime = "ranging"
                confidence = 0.3

        return RegimeState(
            symbol=symbol,
            regime=regime,
            confidence=confidence,
            volatility_percentile=vol_percentile,
            trend_strength=signed_trend,
            metadata={
                "short_return": short_return,
                "medium_return": medium_return,
                "annualized_vol": annualized_vol,
                "trend_efficiency": trend_strength,
                "avg_ob_imbalance": avg_ob_imb,
                "avg_funding": avg_funding,
                "trade_count": len(prices),
            },
        )

    def get_regime(self, symbol: str) -> Optional[RegimeState]:
        """Get the current regime for a symbol."""
        with self._lock:
            return self._current_regime.get(symbol)

    def get_all_regimes(self) -> Dict[str, RegimeState]:
        """Get current regimes for all symbols."""
        with self._lock:
            return dict(self._current_regime)

    def get_stats(self) -> Dict:
        """Get regime detector statistics."""
        with self._lock:
            regimes = dict(self._current_regime)
            trade_counts = {s: len(p) for s, p in self._trade_prices.items()}

        return {
            "symbols_tracked": len(trade_counts),
            "trade_counts": trade_counts,
            "current_regimes": {
                s: {
                    "regime": r.regime,
                    "confidence": r.confidence,
                    "vol_percentile": r.volatility_percentile,
                    "trend_strength": r.trend_strength,
                }
                for s, r in regimes.items()
            },
        }

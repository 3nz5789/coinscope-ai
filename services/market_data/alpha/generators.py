"""
CoinScopeAI Market Data — Alpha Signal Generators
=====================================================
Generates alpha signals from cross-exchange market data:
  1. Funding Rate Extremes — contrarian signal when funding is extreme
  2. Liquidation Cascades — detect cascading liquidations
  3. Cross-Exchange Basis — spot/perp or cross-exchange price divergence
  4. Order Book Imbalance — persistent directional pressure
  5. Volume Spike — abnormal volume detection

Each generator subscribes to EventBus topics and publishes AlphaSignal events.
"""

import logging
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
    Trade,
    alpha_topic,
)

logger = logging.getLogger("coinscopeai.market_data.alpha")


# ── Funding Rate Extreme Generator ───────────────────────────

class FundingExtremeGenerator:
    """
    Detects extreme funding rates across exchanges.

    When funding is extremely positive → longs are overcrowded → SHORT bias
    When funding is extremely negative → shorts are overcrowded → LONG bias

    Aggregates funding across Binance, Bybit, OKX, Deribit for consensus.
    """

    EXTREME_THRESHOLD = 0.0005      # 0.05% per 8h = ~54% annualized
    MODERATE_THRESHOLD = 0.0002     # 0.02% per 8h
    MIN_EXCHANGES = 2               # Need at least 2 exchanges agreeing

    def __init__(self, event_bus: EventBus, symbols: List[str]):
        self._bus = event_bus
        self._symbols = symbols
        self._lock = threading.Lock()

        # Latest funding rate per symbol per exchange
        self._rates: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._last_signal_time: Dict[str, float] = {}
        self._cooldown = 3600  # 1 hour between signals per symbol

        # Subscribe to all funding events
        self._bus.subscribe(
            "alpha_funding",
            "funding.*.*",
            self._on_funding,
        )

    def _on_funding(self, event: Event):
        fr: FundingRate = event.data
        if fr.symbol not in self._symbols:
            return

        with self._lock:
            self._rates[fr.symbol][fr.exchange] = fr.rate

        self._check_signal(fr.symbol)

    def _check_signal(self, symbol: str):
        with self._lock:
            rates = dict(self._rates.get(symbol, {}))

        if len(rates) < self.MIN_EXCHANGES:
            return

        # Check cooldown
        last = self._last_signal_time.get(symbol, 0)
        if time.time() - last < self._cooldown:
            return

        avg_rate = sum(rates.values()) / len(rates)
        extreme_count = sum(1 for r in rates.values() if abs(r) >= self.EXTREME_THRESHOLD)

        direction = "NEUTRAL"
        strength = 0.0

        if avg_rate >= self.EXTREME_THRESHOLD and extreme_count >= self.MIN_EXCHANGES:
            direction = "SHORT"  # Contrarian: extreme positive funding → fade longs
            strength = min(abs(avg_rate) / self.EXTREME_THRESHOLD, 1.0)
        elif avg_rate <= -self.EXTREME_THRESHOLD and extreme_count >= self.MIN_EXCHANGES:
            direction = "LONG"   # Contrarian: extreme negative funding → fade shorts
            strength = min(abs(avg_rate) / self.EXTREME_THRESHOLD, 1.0)
        elif abs(avg_rate) >= self.MODERATE_THRESHOLD:
            direction = "SHORT" if avg_rate > 0 else "LONG"
            strength = min(abs(avg_rate) / self.EXTREME_THRESHOLD, 0.6)

        if direction != "NEUTRAL":
            signal = AlphaSignal(
                signal_type="funding_extreme",
                symbol=symbol,
                direction=direction,
                strength=strength,
                metadata={
                    "avg_rate": avg_rate,
                    "rates": rates,
                    "exchanges_agreeing": extreme_count,
                    "annualized_pct": avg_rate * 3 * 365 * 100,
                },
                ttl_seconds=28800,  # Valid until next funding period (8h)
            )
            self._bus.publish(Event(
                topic=signal.topic,
                data=signal,
                source="alpha_funding",
            ))
            self._last_signal_time[symbol] = time.time()
            logger.info(
                "ALPHA FUNDING: %s %s strength=%.2f avg_rate=%.6f",
                symbol, direction, strength, avg_rate,
            )


# ── Liquidation Cascade Generator ────────────────────────────

class LiquidationCascadeGenerator:
    """
    Detects cascading liquidation events.

    A cascade occurs when large liquidation volume happens in a short window,
    indicating forced selling/buying that can move price significantly.

    Logic:
      - Track liquidation volume in rolling 5-minute windows
      - If total liquidation volume exceeds threshold → signal
      - Direction: opposite to liquidation side (shorts liquidated → price going up → LONG)
    """

    WINDOW_SECONDS = 300            # 5-minute rolling window
    THRESHOLD_USD = 5_000_000       # $5M in liquidations
    CASCADE_THRESHOLD_USD = 10_000_000  # $10M = major cascade

    def __init__(self, event_bus: EventBus, symbols: List[str]):
        self._bus = event_bus
        self._symbols = symbols
        self._lock = threading.Lock()

        # Rolling window of liquidations per symbol
        self._liquidations: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._last_signal_time: Dict[str, float] = {}
        self._cooldown = 600  # 10 minutes between signals

        self._bus.subscribe(
            "alpha_liquidation",
            "liquidation.*.*",
            self._on_liquidation,
        )

    def _on_liquidation(self, event: Event):
        liq: Liquidation = event.data
        if liq.symbol not in self._symbols:
            return

        with self._lock:
            self._liquidations[liq.symbol].append({
                "side": liq.side,
                "notional": liq.notional,
                "timestamp": liq.timestamp,
            })

        self._check_cascade(liq.symbol)

    def _check_cascade(self, symbol: str):
        now = time.time()

        # Check cooldown
        last = self._last_signal_time.get(symbol, 0)
        if now - last < self._cooldown:
            return

        with self._lock:
            recent = [
                l for l in self._liquidations[symbol]
                if now - l["timestamp"] < self.WINDOW_SECONDS
            ]

        if not recent:
            return

        long_liqs = sum(l["notional"] for l in recent if l["side"] == "sell")
        short_liqs = sum(l["notional"] for l in recent if l["side"] == "buy")
        total = long_liqs + short_liqs

        if total < self.THRESHOLD_USD:
            return

        # Determine direction: if shorts are being liquidated, price is going up → LONG
        if short_liqs > long_liqs * 1.5:
            direction = "LONG"
        elif long_liqs > short_liqs * 1.5:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"

        if direction == "NEUTRAL":
            return

        is_major = total >= self.CASCADE_THRESHOLD_USD
        strength = min(total / self.CASCADE_THRESHOLD_USD, 1.0)

        signal = AlphaSignal(
            signal_type="liquidation_cascade",
            symbol=symbol,
            direction=direction,
            strength=strength,
            metadata={
                "total_usd": total,
                "long_liquidated_usd": long_liqs,
                "short_liquidated_usd": short_liqs,
                "event_count": len(recent),
                "window_seconds": self.WINDOW_SECONDS,
                "is_major_cascade": is_major,
            },
            ttl_seconds=1800,  # 30 minutes
        )
        self._bus.publish(Event(
            topic=signal.topic,
            data=signal,
            source="alpha_liquidation",
        ))
        self._last_signal_time[symbol] = now
        logger.info(
            "ALPHA LIQUIDATION: %s %s strength=%.2f total=$%.0f",
            symbol, direction, strength, total,
        )


# ── Cross-Exchange Basis Generator ───────────────────────────

class BasisGenerator:
    """
    Detects cross-exchange price divergence (basis).

    When one exchange's price significantly deviates from others,
    it indicates either:
      - Localized demand/supply imbalance → mean reversion opportunity
      - Leading indicator from a more liquid venue

    Tracks mid-prices from order books across exchanges.
    """

    DIVERGENCE_BPS = 15     # 1.5 bps divergence threshold
    STRONG_BPS = 30         # 3 bps = strong divergence

    def __init__(self, event_bus: EventBus, symbols: List[str]):
        self._bus = event_bus
        self._symbols = symbols
        self._lock = threading.Lock()

        # Latest mid-price per symbol per exchange
        self._prices: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._last_signal_time: Dict[str, float] = {}
        self._cooldown = 300  # 5 minutes

        self._bus.subscribe(
            "alpha_basis",
            "orderbook.*.*",
            self._on_orderbook,
        )

    def _on_orderbook(self, event: Event):
        ob: OrderBookSnapshot = event.data
        if ob.symbol not in self._symbols:
            return
        if ob.mid_price <= 0:
            return

        with self._lock:
            self._prices[ob.symbol][ob.exchange] = ob.mid_price

        self._check_basis(ob.symbol)

    def _check_basis(self, symbol: str):
        now = time.time()
        last = self._last_signal_time.get(symbol, 0)
        if now - last < self._cooldown:
            return

        with self._lock:
            prices = dict(self._prices.get(symbol, {}))

        if len(prices) < 2:
            return

        avg_price = sum(prices.values()) / len(prices)
        if avg_price <= 0:
            return

        # Find max divergence
        max_div_bps = 0
        max_div_exchange = ""
        for exchange, price in prices.items():
            div_bps = abs(price - avg_price) / avg_price * 10_000
            if div_bps > max_div_bps:
                max_div_bps = div_bps
                max_div_exchange = exchange

        if max_div_bps < self.DIVERGENCE_BPS:
            return

        # If one exchange is significantly higher → that exchange has excess demand
        # Mean reversion: expect the outlier to come back to the mean
        outlier_price = prices[max_div_exchange]
        if outlier_price > avg_price:
            direction = "SHORT"  # Outlier is high → expect reversion down
        else:
            direction = "LONG"   # Outlier is low → expect reversion up

        strength = min(max_div_bps / self.STRONG_BPS, 1.0)

        signal = AlphaSignal(
            signal_type="basis_divergence",
            symbol=symbol,
            direction=direction,
            strength=strength,
            metadata={
                "max_divergence_bps": max_div_bps,
                "outlier_exchange": max_div_exchange,
                "prices": prices,
                "avg_price": avg_price,
            },
            ttl_seconds=600,  # 10 minutes
        )
        self._bus.publish(Event(
            topic=signal.topic,
            data=signal,
            source="alpha_basis",
        ))
        self._last_signal_time[symbol] = now
        logger.info(
            "ALPHA BASIS: %s %s strength=%.2f div=%.1f bps (%s)",
            symbol, direction, strength, max_div_bps, max_div_exchange,
        )


# ── Order Book Imbalance Generator ──────────────────────────

class OrderBookImbalanceGenerator:
    """
    Detects persistent order book imbalance.

    Tracks bid/ask depth ratio over a rolling window.
    Persistent imbalance indicates directional pressure.
    """

    WINDOW_SIZE = 60        # Track last 60 snapshots
    IMBALANCE_THRESHOLD = 0.3  # |imbalance| > 0.3 = significant
    PERSISTENCE_RATIO = 0.7    # 70% of window must agree

    def __init__(self, event_bus: EventBus, symbols: List[str]):
        self._bus = event_bus
        self._symbols = symbols
        self._lock = threading.Lock()

        # Rolling imbalance values per symbol
        self._imbalances: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_SIZE)
        )
        self._last_signal_time: Dict[str, float] = {}
        self._cooldown = 600  # 10 minutes

        self._bus.subscribe(
            "alpha_ob_imbalance",
            "orderbook.*.*",
            self._on_orderbook,
        )

    def _on_orderbook(self, event: Event):
        ob: OrderBookSnapshot = event.data
        if ob.symbol not in self._symbols:
            return

        imb = ob.imbalance

        with self._lock:
            self._imbalances[ob.symbol].append(imb)

        self._check_imbalance(ob.symbol)

    def _check_imbalance(self, symbol: str):
        now = time.time()
        last = self._last_signal_time.get(symbol, 0)
        if now - last < self._cooldown:
            return

        with self._lock:
            values = list(self._imbalances.get(symbol, []))

        if len(values) < self.WINDOW_SIZE * 0.5:
            return

        avg_imb = sum(values) / len(values)
        positive_count = sum(1 for v in values if v > self.IMBALANCE_THRESHOLD)
        negative_count = sum(1 for v in values if v < -self.IMBALANCE_THRESHOLD)

        direction = "NEUTRAL"
        strength = 0.0

        if positive_count / len(values) >= self.PERSISTENCE_RATIO:
            direction = "LONG"  # Persistent bid-heavy → buying pressure
            strength = min(abs(avg_imb) / 0.5, 1.0)
        elif negative_count / len(values) >= self.PERSISTENCE_RATIO:
            direction = "SHORT"  # Persistent ask-heavy → selling pressure
            strength = min(abs(avg_imb) / 0.5, 1.0)

        if direction == "NEUTRAL":
            return

        signal = AlphaSignal(
            signal_type="orderbook_imbalance",
            symbol=symbol,
            direction=direction,
            strength=strength,
            metadata={
                "avg_imbalance": avg_imb,
                "positive_ratio": positive_count / len(values),
                "negative_ratio": negative_count / len(values),
                "window_size": len(values),
            },
            ttl_seconds=900,  # 15 minutes
        )
        self._bus.publish(Event(
            topic=signal.topic,
            data=signal,
            source="alpha_ob_imbalance",
        ))
        self._last_signal_time[symbol] = now
        logger.info(
            "ALPHA OB IMBALANCE: %s %s strength=%.2f avg_imb=%.3f",
            symbol, direction, strength, avg_imb,
        )


# ── Alpha Engine (Manager) ──────────────────────────────────

class AlphaEngine:
    """
    Manages all alpha signal generators.
    Provides a single interface to start/stop and query active signals.
    """

    def __init__(self, event_bus: EventBus, symbols: List[str]):
        self._bus = event_bus
        self._symbols = symbols

        # Initialize all generators
        self.funding = FundingExtremeGenerator(event_bus, symbols)
        self.liquidation = LiquidationCascadeGenerator(event_bus, symbols)
        self.basis = BasisGenerator(event_bus, symbols)
        self.ob_imbalance = OrderBookImbalanceGenerator(event_bus, symbols)

        # Track active signals
        self._active_signals: Dict[str, AlphaSignal] = {}
        self._lock = threading.Lock()

        # Subscribe to all alpha signals to track them
        self._bus.subscribe(
            "alpha_tracker",
            "alpha.*.*",
            self._on_alpha_signal,
        )

    def _on_alpha_signal(self, event: Event):
        signal: AlphaSignal = event.data
        key = f"{signal.signal_type}.{signal.symbol}"
        with self._lock:
            self._active_signals[key] = signal

    def get_active_signals(self, symbol: Optional[str] = None) -> List[AlphaSignal]:
        """Get all non-expired alpha signals, optionally filtered by symbol."""
        with self._lock:
            signals = list(self._active_signals.values())

        # Remove expired
        active = [s for s in signals if not s.is_expired]

        if symbol:
            active = [s for s in active if s.symbol == symbol]

        return active

    def get_consensus(self, symbol: str) -> Dict:
        """
        Get consensus direction from all active alpha signals for a symbol.

        Returns:
            {
                "direction": "LONG" | "SHORT" | "NEUTRAL",
                "strength": 0.0-1.0,
                "signals": [...],
                "agreement_ratio": 0.0-1.0,
            }
        """
        signals = self.get_active_signals(symbol)
        if not signals:
            return {
                "direction": "NEUTRAL",
                "strength": 0.0,
                "signals": [],
                "agreement_ratio": 0.0,
            }

        long_strength = sum(s.strength for s in signals if s.direction == "LONG")
        short_strength = sum(s.strength for s in signals if s.direction == "SHORT")
        total = long_strength + short_strength

        if total == 0:
            direction = "NEUTRAL"
            strength = 0.0
            agreement = 0.0
        elif long_strength > short_strength:
            direction = "LONG"
            strength = long_strength / len(signals)
            agreement = sum(1 for s in signals if s.direction == "LONG") / len(signals)
        else:
            direction = "SHORT"
            strength = short_strength / len(signals)
            agreement = sum(1 for s in signals if s.direction == "SHORT") / len(signals)

        return {
            "direction": direction,
            "strength": strength,
            "signals": [
                {
                    "type": s.signal_type,
                    "direction": s.direction,
                    "strength": s.strength,
                    "age_seconds": time.time() - s.timestamp,
                }
                for s in signals
            ],
            "agreement_ratio": agreement,
        }

    def get_stats(self) -> Dict:
        """Get alpha engine statistics."""
        with self._lock:
            active = [s for s in self._active_signals.values() if not s.is_expired]
            expired = len(self._active_signals) - len(active)

        return {
            "active_signals": len(active),
            "expired_signals": expired,
            "signals_by_type": defaultdict(int, {
                s.signal_type: 1 for s in active
            }),
            "symbols_with_signals": list(set(s.symbol for s in active)),
        }

"""
correlation_analyzer.py — Inter-Asset Correlation Risk Analyzer
================================================================
Computes rolling pairwise Pearson correlations between assets being
traded to prevent over-concentration in highly correlated positions.

Why this matters
----------------
If BTCUSDT and ETHUSDT move 0.95 r², opening longs on both is almost
identical to doubling the BTC position.  The correlation analyzer flags
when a new position would increase the portfolio's correlated exposure
beyond a configurable threshold.

Features
--------
* Rolling return-based Pearson correlation (numpy, no pandas dependency)
* Correlation matrix for all active symbols
* "correlated pair" list — pairs with |r| ≥ HIGH_CORR_THRESHOLD
* add_position gate — returns False if new symbol is highly correlated
  with ≥ 1 already-open position in the same direction
* Async price-feed update via update_prices()

Thresholds
----------
  HIGH_CORR_THRESHOLD  = 0.80   (flag as highly correlated)
  LOOKBACK_PERIODS     = 50     (candles / price points)

Usage
-----
    analyzer = CorrelationAnalyzer()
    analyzer.update_prices("BTCUSDT", [65000, 65100, ...])
    analyzer.update_prices("ETHUSDT", [3200, 3215, ...])

    matrix = analyzer.correlation_matrix()
    ok = analyzer.is_safe_to_add("SOLUSDT", SignalDirection.LONG, open_positions)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from scanner.base_scanner import SignalDirection
from utils.helpers import safe_divide
from utils.logger import get_logger

logger = get_logger(__name__)

HIGH_CORR_THRESHOLD = 0.80    # |r| above this = highly correlated
LOOKBACK_PERIODS    = 50      # price history length used for correlation


@dataclass
class CorrelationPair:
    symbol_a:    str
    symbol_b:    str
    correlation: float
    is_high:     bool

    def __repr__(self) -> str:
        return (
            f"<CorrelationPair {self.symbol_a}/{self.symbol_b} "
            f"r={self.correlation:.3f} high={self.is_high}>"
        )


class CorrelationAnalyzer:
    """
    Maintains a rolling price history and computes Pearson correlations.

    Parameters
    ----------
    lookback   : Number of price points used for each correlation calc.
    threshold  : |r| threshold above which a pair is "highly correlated".
    """

    def __init__(
        self,
        lookback:  int   = LOOKBACK_PERIODS,
        threshold: float = HIGH_CORR_THRESHOLD,
    ) -> None:
        self._lookback   = lookback
        self._threshold  = threshold
        self._prices: dict[str, list[float]] = {}

    # ── Price feed ───────────────────────────────────────────────────────

    def update_prices(self, symbol: str, prices: list[float]) -> None:
        """Replace stored price history for a symbol."""
        self._prices[symbol] = list(prices[-self._lookback:])

    def append_price(self, symbol: str, price: float) -> None:
        """Append a single new price point and trim to lookback window."""
        if symbol not in self._prices:
            self._prices[symbol] = []
        self._prices[symbol].append(price)
        if len(self._prices[symbol]) > self._lookback:
            self._prices[symbol].pop(0)

    # ── Correlation computation ──────────────────────────────────────────

    def pearson(self, symbol_a: str, symbol_b: str) -> Optional[float]:
        """
        Compute Pearson correlation between log-returns of two symbols.

        Returns None if insufficient data.
        """
        prices_a = self._prices.get(symbol_a, [])
        prices_b = self._prices.get(symbol_b, [])

        min_len = min(len(prices_a), len(prices_b))
        if min_len < 5:
            return None

        # Align to same length
        returns_a = _log_returns(prices_a[-min_len:])
        returns_b = _log_returns(prices_b[-min_len:])

        if len(returns_a) < 4 or len(returns_b) < 4:
            return None

        return float(np.corrcoef(returns_a, returns_b)[0, 1])

    def correlation_matrix(self) -> dict[str, dict[str, float]]:
        """Return a nested dict: matrix[sym_a][sym_b] = correlation."""
        symbols = list(self._prices.keys())
        matrix: dict[str, dict[str, float]] = {}

        for i, sym_a in enumerate(symbols):
            matrix[sym_a] = {}
            for sym_b in symbols:
                if sym_a == sym_b:
                    matrix[sym_a][sym_b] = 1.0
                    continue
                r = self.pearson(sym_a, sym_b)
                matrix[sym_a][sym_b] = round(r, 4) if r is not None else 0.0

        return matrix

    def high_correlation_pairs(self) -> list[CorrelationPair]:
        """Return all pairs with |r| ≥ threshold."""
        symbols = list(self._prices.keys())
        pairs: list[CorrelationPair] = []
        seen: set[frozenset] = set()

        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i + 1:]:
                key = frozenset({sym_a, sym_b})
                if key in seen:
                    continue
                seen.add(key)
                r = self.pearson(sym_a, sym_b)
                if r is not None:
                    pairs.append(CorrelationPair(
                        symbol_a    = sym_a,
                        symbol_b    = sym_b,
                        correlation = round(r, 4),
                        is_high     = abs(r) >= self._threshold,
                    ))

        return sorted(pairs, key=lambda p: abs(p.correlation), reverse=True)

    # ── Position gate ────────────────────────────────────────────────────

    def is_safe_to_add(
        self,
        new_symbol:   str,
        new_direction: SignalDirection,
        open_positions: dict,   # {symbol: Position}
    ) -> tuple[bool, str]:
        """
        Check whether adding `new_symbol` in `new_direction` is safe given
        currently open positions.

        Returns (True, "") if safe, or (False, reason) if blocked.

        Two positions in the same direction with |r| ≥ threshold are
        considered a concentration risk.
        """
        for sym, pos in open_positions.items():
            if sym == new_symbol:
                continue
            if pos.direction != new_direction:
                continue   # opposite directions hedge, not concentrate

            r = self.pearson(new_symbol, sym)
            if r is None:
                continue   # insufficient data — allow

            if abs(r) >= self._threshold:
                return (
                    False,
                    f"{new_symbol} highly correlated with open {sym} "
                    f"(r={r:.2f} ≥ {self._threshold})"
                )

        return True, ""

    # ── Stats ────────────────────────────────────────────────────────────

    @property
    def tracked_symbols(self) -> list[str]:
        return list(self._prices.keys())

    def price_history_length(self, symbol: str) -> int:
        return len(self._prices.get(symbol, []))

    def __repr__(self) -> str:
        return (
            f"<CorrelationAnalyzer symbols={len(self._prices)} "
            f"lookback={self._lookback} threshold={self._threshold}>"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_returns(prices: list[float]) -> np.ndarray:
    """Convert a price series to log returns."""
    arr = np.array(prices, dtype=float)
    # Avoid log(0)
    arr = np.where(arr <= 0, 1e-10, arr)
    return np.diff(np.log(arr))

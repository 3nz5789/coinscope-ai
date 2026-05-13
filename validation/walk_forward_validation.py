"""
Walk-Forward Validation Harness
================================

Sequential walk-forward over OHLCV data. For each symbol, the bar series
is split into 3 equal-sized folds; each fold uses its first 70% as train
context (for scorer lookback warmup) and tests the scorer on the
remaining 30% out-of-sample.

Methodology: docs/validation/p0-evidence-pack.md §5.
Boundaries: ADR-0005 — read-only, no Notion/Telegram/order calls.

The scorer is causal: each bar's score depends only on past bars, so
running it over the whole fold range produces look-ahead-safe scores.
Trades are taken only on test bars (indices >= train_end).

Pass criteria per fold (per §5):
    Sharpe > 0.8 AND max_drawdown > -25%
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from . import _common


DEFAULT_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
)
DEFAULT_TIMEFRAME = "4h"
DEFAULT_LIMIT = 1080  # ~6 months of 4h bars
N_FOLDS = 3
TRAIN_PCT = 0.70


@dataclass
class WFVResult:
    """Container for a full walk-forward run across symbols."""
    symbols: List[str]
    timeframe: str
    fold_metrics: List[_common.FoldMetrics]
    bars_per_symbol: int

    def summary_stats(self) -> dict:
        """Aggregate statistics for the markdown summary."""
        sharpes = [m.sharpe for m in self.fold_metrics if m.n_trades > 0]
        passed = sum(1 for m in self.fold_metrics if m.passed)
        return {
            "total_folds": len(self.fold_metrics),
            "passed_folds": passed,
            "median_sharpe": float(np.median(sharpes)) if sharpes else 0.0,
            "min_sharpe": float(min(sharpes)) if sharpes else 0.0,
            "max_sharpe": float(max(sharpes)) if sharpes else 0.0,
        }


def fold_indices(n_bars: int, n_folds: int = N_FOLDS, train_pct: float = TRAIN_PCT):
    """
    Yield (fold_label, train_start, train_end, test_start, test_end) tuples
    for sequential walk-forward folds.

    Fold k uses bars [k*fold_size, (k+1)*fold_size); within that, the first
    train_pct is training context and the rest is the test region.
    """
    fold_size = n_bars // n_folds
    for k in range(n_folds):
        fold_start = k * fold_size
        fold_end = fold_start + fold_size if k < n_folds - 1 else n_bars
        train_end = fold_start + int((fold_end - fold_start) * train_pct)
        yield f"fold_{k + 1}", fold_start, train_end, train_end, fold_end


def run_symbol(symbol: str, ohlcv: np.ndarray) -> List[_common.FoldMetrics]:
    """Run WFV for a single symbol and return one FoldMetrics per fold."""
    scores = _common.score_bars(ohlcv)
    closes = ohlcv[:, 4]
    results: List[_common.FoldMetrics] = []
    for label, train_s, train_e, test_s, test_e in fold_indices(len(ohlcv)):
        trades = _common.simulate_trades(scores, closes, test_s, test_e)
        metrics = _common.compute_metrics(
            symbol=symbol, fold_label=label,
            trades=trades,
            train_start=train_s, train_end=train_e,
            test_start=test_s, test_end=test_e,
        )
        results.append(metrics)
    return results


def run(
    symbols=DEFAULT_SYMBOLS,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    ohlcv_provider=None,
) -> WFVResult:
    """
    Run the full WFV across `symbols`.

    `ohlcv_provider` is an optional callable `(symbol) -> ndarray` so tests
    can inject synthetic data without making network calls.
    """
    if ohlcv_provider is None:
        ohlcv_provider = lambda s: _common.fetch_ohlcv(s, timeframe, limit)

    all_metrics: List[_common.FoldMetrics] = []
    bars_per_symbol = 0
    for sym in symbols:
        ohlcv = ohlcv_provider(sym)
        bars_per_symbol = max(bars_per_symbol, len(ohlcv))
        all_metrics.extend(run_symbol(sym, ohlcv))

    return WFVResult(
        symbols=list(symbols),
        timeframe=timeframe,
        fold_metrics=all_metrics,
        bars_per_symbol=bars_per_symbol,
    )

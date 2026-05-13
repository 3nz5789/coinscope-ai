"""
Combinatorial Purged Cross-Validation (CPCV) Harness
=====================================================

For each symbol, the bar series is split into N groups. For each
combination of K test groups out of N (C(N,K) paths), the scorer is
evaluated on the test groups and per-path metrics are computed. The
worst-vs-median Sharpe drop across paths is the headline aggregate.

Methodology: docs/validation/p0-evidence-pack.md §0.4 — the
"CPCV worst-vs-median Sharpe drop ≤ 30%" graduation bar.

Since the scorer has no learnable parameters (it is a deterministic
rubric of indicators), there is no train-time leakage from test bars
into the model. The traditional CPCV "purging" applies to label
overlap in supervised learning; here we still implement a small
boundary buffer (PURGE_BARS) on each side of test groups to avoid the
indicator lookback windows reading into test bars from the immediate
prior train-group context.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import List, Tuple

import numpy as np

from . import _common


DEFAULT_SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
)
DEFAULT_TIMEFRAME = "4h"
DEFAULT_LIMIT = 1080

N_GROUPS = 6
K_TEST_GROUPS = 2
PURGE_BARS = 25  # ~ longer than the longest scorer lookback (EMA21)
# CPCV graduation bar from p0-evidence-pack §0.4
WORST_VS_MEDIAN_SHARPE_BAR = 0.30


@dataclass
class CPCVPathResult:
    """One CPCV path: a specific combination of test groups."""
    symbol: str
    path_label: str
    test_group_indices: Tuple[int, ...]
    metrics: _common.FoldMetrics


@dataclass
class CPCVResult:
    """Container for a full CPCV run across symbols."""
    symbols: List[str]
    timeframe: str
    per_path: List[CPCVPathResult]
    per_symbol_aggregate: dict  # symbol -> {median, min, worst_vs_median_ratio}
    overall_passed: bool

    def summary_stats(self) -> dict:
        ratios = [
            v["worst_vs_median_ratio"] for v in self.per_symbol_aggregate.values()
            if v["worst_vs_median_ratio"] is not None
        ]
        return {
            "n_paths": len(self.per_path),
            "symbols_passing": sum(
                1 for v in self.per_symbol_aggregate.values() if v["passed"]
            ),
            "n_symbols": len(self.symbols),
            "max_worst_vs_median_ratio": max(ratios) if ratios else 0.0,
            "bar": WORST_VS_MEDIAN_SHARPE_BAR,
        }


def group_indices(n_bars: int, n_groups: int = N_GROUPS) -> List[Tuple[int, int]]:
    """Return [(start, end), ...] for n_groups equal-sized groups."""
    size = n_bars // n_groups
    boundaries = [(i * size, (i + 1) * size) for i in range(n_groups - 1)]
    boundaries.append(((n_groups - 1) * size, n_bars))
    return boundaries


def run_symbol(
    symbol: str,
    ohlcv: np.ndarray,
    n_groups: int = N_GROUPS,
    k: int = K_TEST_GROUPS,
) -> List[CPCVPathResult]:
    """Run CPCV for one symbol across all C(n_groups, k) paths."""
    scores = _common.score_bars(ohlcv)
    closes = ohlcv[:, 4]
    groups = group_indices(len(ohlcv), n_groups)
    n_bars = len(ohlcv)
    results: List[CPCVPathResult] = []

    for path_idx, combo in enumerate(combinations(range(n_groups), k), start=1):
        path_label = f"path_{path_idx:02d}"
        all_trades: List[_common.Trade] = []
        total_test_bars = 0

        for gi in combo:
            test_s, test_e = groups[gi]
            # Apply purging: skip bars within PURGE_BARS of the group
            # boundary if they would overlap the indicator lookback from
            # outside data
            purged_s = test_s + (PURGE_BARS if test_s > 0 else 0)
            purged_e = test_e - (PURGE_BARS if test_e < n_bars else 0)
            if purged_s >= purged_e:
                continue
            trades = _common.simulate_trades(scores, closes, purged_s, purged_e)
            all_trades.extend(trades)
            total_test_bars += (purged_e - purged_s)

        # Aggregate fold metric across the K test groups for this path
        # train_start/train_end represent the "context" used: we record
        # the full data range and the aggregated test span.
        metrics = _common.compute_metrics(
            symbol=symbol, fold_label=path_label,
            trades=all_trades,
            train_start=0, train_end=n_bars,
            test_start=combo[0] * (n_bars // n_groups),
            test_end=(combo[-1] + 1) * (n_bars // n_groups),
        )
        # Override n_test_bars with the actual purged count
        metrics.n_test_bars = total_test_bars
        results.append(
            CPCVPathResult(
                symbol=symbol, path_label=path_label,
                test_group_indices=combo, metrics=metrics,
            )
        )

    return results


def _aggregate_symbol(paths: List[CPCVPathResult]) -> dict:
    """
    Per-symbol aggregate: median Sharpe, min Sharpe, and the
    worst-vs-median relative drop.

    Pass condition: relative drop ≤ WORST_VS_MEDIAN_SHARPE_BAR
    (the graduation bar from p0-evidence-pack §0.4).
    """
    sharpes = [p.metrics.sharpe for p in paths if p.metrics.n_trades > 0]
    if not sharpes:
        return {
            "n_paths": len(paths), "median": 0.0, "min": 0.0, "max": 0.0,
            "worst_vs_median_ratio": None, "passed": False,
        }
    median = float(np.median(sharpes))
    worst = float(min(sharpes))
    ratio = None
    passed = False
    # Only meaningful if median is positive (otherwise the strategy is broken)
    if median > 0:
        ratio = (median - worst) / median  # relative drop
        passed = ratio <= WORST_VS_MEDIAN_SHARPE_BAR
    return {
        "n_paths": len(paths),
        "median": median,
        "min": worst,
        "max": float(max(sharpes)),
        "worst_vs_median_ratio": ratio,
        "passed": passed,
    }


def run(
    symbols=DEFAULT_SYMBOLS,
    timeframe: str = DEFAULT_TIMEFRAME,
    limit: int = DEFAULT_LIMIT,
    n_groups: int = N_GROUPS,
    k: int = K_TEST_GROUPS,
    ohlcv_provider=None,
) -> CPCVResult:
    """Run the full CPCV across `symbols`."""
    if ohlcv_provider is None:
        ohlcv_provider = lambda s: _common.fetch_ohlcv(s, timeframe, limit)

    all_paths: List[CPCVPathResult] = []
    per_symbol: dict = {}
    for sym in symbols:
        ohlcv = ohlcv_provider(sym)
        sym_paths = run_symbol(sym, ohlcv, n_groups=n_groups, k=k)
        all_paths.extend(sym_paths)
        per_symbol[sym] = _aggregate_symbol(sym_paths)

    overall_passed = all(v["passed"] for v in per_symbol.values())

    return CPCVResult(
        symbols=list(symbols),
        timeframe=timeframe,
        per_path=all_paths,
        per_symbol_aggregate=per_symbol,
        overall_passed=overall_passed,
    )

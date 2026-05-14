#!/usr/bin/env python3
"""
Validation runner — orchestrates the walk-forward and CPCV harnesses
and writes outputs to docs/validation/runs/<date>/.

Usage:
    python3 scripts/run_validation.py --wfv
    python3 scripts/run_validation.py --cpcv
    python3 scripts/run_validation.py --both
    python3 scripts/run_validation.py --both --symbols BTCUSDT,ETHUSDT  (override)

Outputs:
    docs/validation/runs/YYYY-MM-DD/wfv.csv
    docs/validation/runs/YYYY-MM-DD/wfv.md
    docs/validation/runs/YYYY-MM-DD/cpcv.csv
    docs/validation/runs/YYYY-MM-DD/cpcv.md

Per ADR-0005: this script may use ccxt freely. It must not write to
Notion, Telegram, or place orders.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

# Make the repo root importable so we can `from validation import ...`
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from validation import _common, walk_forward_validation, cpcv_validation


def write_wfv_outputs(result: walk_forward_validation.WFVResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "wfv.csv"
    _common.write_csv(result.fold_metrics, str(csv_path))

    md_path = out_dir / "wfv.md"
    stats = result.summary_stats()
    table = _common.metrics_to_markdown_table(result.fold_metrics)
    md = f"""# Walk-Forward Validation — {dt.date.today().isoformat()}

**Methodology:** sequential walk-forward, 3 folds per symbol, 70% train context / 30% out-of-sample test per fold. Trade simulation is ±1% per signal based on next-bar direction (signal-quality measure, not P&L projection — see `docs/validation/p0-evidence-pack.md` §5).

**Pass criteria (per §5):** Sharpe > 0.8 AND max drawdown > -25% per fold.

**Sharpe annualization:** `sqrt(365 * 4)` per BUG-14 fix.

**Symbols:** {", ".join(result.symbols)}
**Timeframe:** {result.timeframe}
**Bars per symbol:** {result.bars_per_symbol}

## Summary

- Folds run: **{stats['total_folds']}**
- Folds passed: **{stats['passed_folds']} / {stats['total_folds']}**
- Sharpe (min / median / max): **{stats['min_sharpe']:+.3f} / {stats['median_sharpe']:+.3f} / {stats['max_sharpe']:+.3f}**

## Per-fold results

{table}

## Notes

- The scorer is causal: each bar's score uses only past bars, so the
  test-region scores are look-ahead-safe even without explicit
  train/test isolation.
- A "FAIL" row is normal in P0 — at the score >= 8.0 LONG /
  <= 4.0 SHORT thresholds (BUG-2 fix), signal density is low and
  individual folds with few trades can have noisy Sharpe.
- This run replaces the struck-through illustrative table in
  `docs/validation/p0-evidence-pack.md` §5.
"""
    md_path.write_text(md)


def write_cpcv_outputs(result: cpcv_validation.CPCVResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "cpcv.csv"
    _common.write_csv([p.metrics for p in result.per_path], str(csv_path))

    md_path = out_dir / "cpcv.md"
    stats = result.summary_stats()
    max_ratio = stats['max_worst_vs_median_ratio']
    max_ratio_display = "> 1000% (median ≈ 0)" if max_ratio > 10.0 else f"{max_ratio:.2%}"

    # Per-symbol summary table
    rows = ["| symbol | n_paths | min Sharpe | median Sharpe | max Sharpe | worst/median drop | pass |",
            "|---|---|---|---|---|---|---|"]
    for sym, agg in result.per_symbol_aggregate.items():
        ratio = agg['worst_vs_median_ratio']
        if ratio is None:
            ratio_str = "n/a (median ≤ 0)"
        elif ratio > 10.0:  # > 1000% relative drop — median is effectively zero
            ratio_str = f"> 1000% (median ≈ 0)"
        else:
            ratio_str = f"{ratio:.2%}"
        passed_str = "✅ PASS" if agg['passed'] else "❌ FAIL"
        rows.append(
            f"| {sym} | {agg['n_paths']} | {agg['min']:+.3f} | {agg['median']:+.3f} | {agg['max']:+.3f} | {ratio_str} | {passed_str} |"
        )

    per_path_table = _common.metrics_to_markdown_table([p.metrics for p in result.per_path])

    md = f"""# CPCV Validation — {dt.date.today().isoformat()}

**Methodology:** Combinatorial Purged Cross-Validation. For each symbol, the bar series is split into N={cpcv_validation.N_GROUPS} groups; for each combination of K={cpcv_validation.K_TEST_GROUPS} test groups out of N (C({cpcv_validation.N_GROUPS},{cpcv_validation.K_TEST_GROUPS}) = {len(list(__import__('itertools').combinations(range(cpcv_validation.N_GROUPS), cpcv_validation.K_TEST_GROUPS)))} paths per symbol), the scorer is evaluated on the test groups and per-path metrics are computed.

**Purging:** {cpcv_validation.PURGE_BARS} bars on each test-group boundary (≥ longest indicator lookback, EMA21).

**Graduation bar (per p0-evidence-pack §0.4):** worst-vs-median Sharpe drop **≤ {cpcv_validation.WORST_VS_MEDIAN_SHARPE_BAR:.0%}** per symbol.

**Sharpe annualization:** `sqrt(365 * 4)` per BUG-14 fix.

**Symbols:** {", ".join(result.symbols)}
**Timeframe:** {result.timeframe}

## Summary

- Paths run: **{stats['n_paths']}**
- Symbols passing the §0.4 bar: **{stats['symbols_passing']} / {stats['n_symbols']}**
- Max worst-vs-median ratio across symbols: **{max_ratio_display}** (bar is **≤ {stats['bar']:.0%}**)
- **Overall result: {'✅ PASS' if result.overall_passed else '❌ FAIL'}** against the §0.4 graduation bar

## Per-symbol aggregate

{chr(10).join(rows)}

## Per-path detail

{per_path_table}

## Notes

- CPCV's traditional "purging" applies to label leakage in supervised
  learning. Our scorer has no learnable parameters; the purge here is
  a defensive measure to ensure indicator lookback windows don't read
  into test bars from immediate prior groups.
- A FAIL for a symbol on the §0.4 bar usually means one or more paths
  produced an outlier (negative or very low Sharpe) while others were
  healthy. Inspect the per-path detail table for the outlier path.
- This run produces the evidence for the §0.4 hard-gate row in
  `docs/validation/p0-evidence-pack.md`.
"""
    md_path.write_text(md)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CoinScopeAI offline validation harnesses.")
    parser.add_argument("--wfv", action="store_true", help="Run walk-forward validation")
    parser.add_argument("--cpcv", action="store_true", help="Run CPCV validation")
    parser.add_argument("--both", action="store_true", help="Run both harnesses")
    parser.add_argument(
        "--symbols", type=str, default=None,
        help="Comma-separated symbols (default: P0 watchlist)",
    )
    parser.add_argument(
        "--timeframe", type=str, default="4h",
        help="OHLCV timeframe (default: 4h)",
    )
    parser.add_argument(
        "--limit", type=int, default=1080,
        help="Bars per symbol (default: 1080 ≈ 6mo of 4h)",
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override run date (YYYY-MM-DD); default: today",
    )
    args = parser.parse_args()

    if not (args.wfv or args.cpcv or args.both):
        parser.error("Specify --wfv, --cpcv, or --both")

    symbols = (
        tuple(args.symbols.split(",")) if args.symbols
        else walk_forward_validation.DEFAULT_SYMBOLS
    )
    run_date = args.date or dt.date.today().isoformat()
    out_dir = REPO_ROOT / "docs" / "validation" / "runs" / run_date

    if args.wfv or args.both:
        print(f"→ Walk-forward validation: {len(symbols)} symbols, {args.timeframe}, {args.limit} bars each")
        wfv = walk_forward_validation.run(
            symbols=symbols, timeframe=args.timeframe, limit=args.limit,
        )
        write_wfv_outputs(wfv, out_dir)
        stats = wfv.summary_stats()
        print(f"  WFV done: {stats['passed_folds']}/{stats['total_folds']} folds passed, median Sharpe {stats['median_sharpe']:+.3f}")
        print(f"  → {out_dir}/wfv.md")

    if args.cpcv or args.both:
        print(f"→ CPCV validation: {len(symbols)} symbols, N={cpcv_validation.N_GROUPS} groups, K={cpcv_validation.K_TEST_GROUPS}")
        cpcv = cpcv_validation.run(
            symbols=symbols, timeframe=args.timeframe, limit=args.limit,
        )
        write_cpcv_outputs(cpcv, out_dir)
        stats = cpcv.summary_stats()
        max_ratio = stats['max_worst_vs_median_ratio']
        ratio_str = f"> 1000% (median ≈ 0)" if max_ratio > 10.0 else f"{max_ratio:.2%}"
        print(f"  CPCV done: {stats['symbols_passing']}/{stats['n_symbols']} symbols pass §0.4 bar; max ratio {ratio_str}")
        print(f"  → {out_dir}/cpcv.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())

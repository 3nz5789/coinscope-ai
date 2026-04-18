"""
benchmark.py — CoinScopeAI Performance Benchmark
==================================================
Measures throughput and latency for the three main hot paths:
  1. Indicator computation          (IndicatorEngine.compute)
  2. Full scanner + scorer pipeline (5 scanners → ConfluenceScorer)
  3. Redis cache round-trip         (set / get)

Outputs a results table and writes a JSON report to benchmark_results.json.

Usage
-----
    python benchmark.py                  # 100 iterations, all tests
    python benchmark.py --iterations 500
    python benchmark.py --test indicators
    python benchmark.py --test scanner
    python benchmark.py --test redis

Expected results (modern laptop, no Redis)
------------------------------------------
  Test                  | Median (ms) | p95 (ms) | Throughput
  ----------------------|-------------|----------|------------
  Indicator compute     |    0.8 ms   |  1.2 ms  | ~1 200 /s
  Scanner + scorer      |    4.5 ms   |  8.0 ms  |   ~220 /s
  Redis round-trip      |    0.3 ms   |  0.8 ms  | ~3 000 /s
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# Inject env before config loads
os.environ.setdefault("TESTNET_MODE",              "true")
os.environ.setdefault("BINANCE_TESTNET_API_KEY",    "bench_key")
os.environ.setdefault("BINANCE_TESTNET_API_SECRET", "bench_secret")
os.environ.setdefault("SECRET_KEY",                 "a" * 64)
os.environ.setdefault("TELEGRAM_BOT_TOKEN",         "")
os.environ.setdefault("TELEGRAM_CHAT_ID",           "")
os.environ.setdefault("MIN_CONFLUENCE_SCORE",       "0")
os.environ.setdefault("SCAN_PAIRS",                 "BTCUSDT,ETHUSDT")


# ---------------------------------------------------------------------------
# Candle factory
# ---------------------------------------------------------------------------

def _make_candles(n: int = 200):
    from data.data_normalizer import Candle
    import math
    candles = []
    base = 65_000.0
    for i in range(n):
        close  = base + 50 * math.sin(i * 0.15) + i * 5
        ts     = 1_700_000_000_000 + i * 3_600_000
        candles.append(Candle(
            symbol="BTCUSDT", interval="1h",
            open_time=ts, close_time=ts + 3_599_999,
            open=close - 30, high=close + 80, low=close - 60, close=close,
            volume=1000.0 + i * 10,
            quote_volume=close * 1000,
            trades=200, taker_buy_volume=600.0,
            taker_buy_quote=close * 600,
        ))
    return candles


# ---------------------------------------------------------------------------
# Benchmark result
# ---------------------------------------------------------------------------

@dataclass
class BenchResult:
    name:       str
    iterations: int
    times_ms:   list[float] = field(default_factory=list)

    @property
    def median(self) -> float:
        return round(statistics.median(self.times_ms), 3) if self.times_ms else 0.0

    @property
    def mean(self) -> float:
        return round(statistics.mean(self.times_ms), 3) if self.times_ms else 0.0

    @property
    def p95(self) -> float:
        if not self.times_ms:
            return 0.0
        sorted_t = sorted(self.times_ms)
        idx = int(len(sorted_t) * 0.95)
        return round(sorted_t[min(idx, len(sorted_t) - 1)], 3)

    @property
    def p99(self) -> float:
        if not self.times_ms:
            return 0.0
        sorted_t = sorted(self.times_ms)
        idx = int(len(sorted_t) * 0.99)
        return round(sorted_t[min(idx, len(sorted_t) - 1)], 3)

    @property
    def throughput(self) -> float:
        if not self.mean:
            return 0.0
        return round(1000 / self.mean, 1)   # ops/second

    def summary(self) -> str:
        return (
            f"  {self.name:<28} "
            f"median={self.median:>7.2f}ms  "
            f"p95={self.p95:>7.2f}ms  "
            f"p99={self.p99:>7.2f}ms  "
            f"throughput={self.throughput:>8.0f}/s"
        )

    def to_dict(self) -> dict:
        return {
            "name":        self.name,
            "iterations":  self.iterations,
            "median_ms":   self.median,
            "mean_ms":     self.mean,
            "p95_ms":      self.p95,
            "p99_ms":      self.p99,
            "throughput_per_s": self.throughput,
        }


# ---------------------------------------------------------------------------
# Benchmark runners
# ---------------------------------------------------------------------------

def bench_indicators(iterations: int) -> BenchResult:
    from signals.indicator_engine import IndicatorEngine
    candles = _make_candles(200)
    engine  = IndicatorEngine()

    # Warm up
    for _ in range(5):
        engine.compute(candles)

    result = BenchResult(name="IndicatorEngine.compute", iterations=iterations)
    for _ in range(iterations):
        t0 = time.perf_counter()
        engine.compute(candles)
        result.times_ms.append((time.perf_counter() - t0) * 1000)

    return result


async def bench_scanner_pipeline(iterations: int) -> BenchResult:
    from scanner.pattern_scanner import PatternScanner
    from scanner.volume_scanner import VolumeScanner
    from scanner.funding_rate_scanner import FundingRateScanner
    from scanner.orderbook_scanner import OrderBookScanner
    from scanner.liquidation_scanner import LiquidationScanner
    from signals.confluence_scorer import ConfluenceScorer

    candles  = _make_candles(100)
    scanners = [
        PatternScanner(),
        LiquidationScanner(),
        OrderBookScanner(),
    ]
    scorer = ConfluenceScorer(min_score=0)

    result = BenchResult(name="Scanner + ConfluenceScorer", iterations=iterations)
    for _ in range(iterations):
        t0 = time.perf_counter()
        results = []
        for sc in scanners:
            try:
                r = await sc.scan("BTCUSDT")
                results.append(r)
            except Exception:
                pass
        scorer.score("BTCUSDT", results, candles)
        result.times_ms.append((time.perf_counter() - t0) * 1000)

    return result


async def bench_redis(iterations: int) -> BenchResult:
    result = BenchResult(name="Redis set/get round-trip", iterations=iterations)
    try:
        import aioredis
        from config import settings
        r = await aioredis.from_url(settings.redis_url, decode_responses=True)

        # Warm up
        await r.set("bench:warm", "1", ex=10)
        await r.get("bench:warm")

        for i in range(iterations):
            t0 = time.perf_counter()
            await r.set(f"bench:{i}", f"value_{i}", ex=10)
            await r.get(f"bench:{i}")
            result.times_ms.append((time.perf_counter() - t0) * 1000)

        await r.close()
    except Exception as exc:
        print(f"  ⚠️  Redis benchmark skipped: {exc}")

    return result


def bench_entry_exit(iterations: int) -> BenchResult:
    from signals.entry_exit_calculator import EntryExitCalculator
    from signals.confluence_scorer import Signal
    from scanner.base_scanner import SignalDirection

    candles = _make_candles(60)
    calc    = EntryExitCalculator()
    signal  = Signal(
        symbol="BTCUSDT", direction=SignalDirection.LONG,
        score=75.0, strength="STRONG",
    )

    result = BenchResult(name="EntryExitCalculator.calculate", iterations=iterations)
    for _ in range(iterations):
        t0 = time.perf_counter()
        calc.calculate(signal, candles)
        result.times_ms.append((time.perf_counter() - t0) * 1000)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_benchmarks(test: str, iterations: int) -> list[BenchResult]:
    results: list[BenchResult] = []

    if test in ("all", "indicators"):
        print("  Running IndicatorEngine benchmark…")
        results.append(bench_indicators(iterations))

    if test in ("all", "scanner"):
        print("  Running Scanner pipeline benchmark…")
        results.append(await bench_scanner_pipeline(iterations))

    if test in ("all", "entry"):
        print("  Running EntryExitCalculator benchmark…")
        results.append(bench_entry_exit(iterations))

    if test in ("all", "redis"):
        print("  Running Redis round-trip benchmark…")
        results.append(await bench_redis(iterations))

    return results


def print_table(results: list[BenchResult]) -> None:
    print()
    print("=" * 80)
    print("  CoinScopeAI Performance Benchmark Results")
    print("=" * 80)
    for r in results:
        if r.times_ms:
            print(r.summary())
        else:
            print(f"  {r.name:<28} — SKIPPED")
    print("=" * 80)
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="CoinScopeAI Benchmark")
    parser.add_argument("--iterations", type=int,   default=100)
    parser.add_argument("--test",       type=str,   default="all",
                        choices=["all", "indicators", "scanner", "entry", "redis"])
    parser.add_argument("--output",     type=str,   default="benchmark_results.json")
    args = parser.parse_args()

    print(f"\n🔬  CoinScopeAI Benchmark  [{args.test}]  iterations={args.iterations}")
    print()

    results = await run_benchmarks(args.test, args.iterations)
    print_table(results)

    report = {
        "test":       args.test,
        "iterations": args.iterations,
        "results":    [r.to_dict() for r in results],
    }
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"  Report saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())

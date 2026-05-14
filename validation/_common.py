"""
Shared utilities for the walk-forward and CPCV validators.

All functions are pure (no I/O outside the explicit OHLCV fetch).
No Notion, no Telegram, no order placement — see ADR-0005.

Sharpe annualization: sqrt(365 * 4) per the BUG-14 fix recorded in
docs/BUG_FIXES_COMPREHENSIVE.md. This assumes an annualization
calibrated to ~4 trades/day; it is a scaling factor and does not
affect comparative ordering of strategies.

Trade simulation: each signal generates a ±1% per-trade return based
on the direction of the next bar's close relative to the entry bar's
close. This matches docs/validation/p0-evidence-pack.md §5's
"signal direction quality" methodology — it is NOT a P&L projection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

import numpy as np

# Sharpe annualization factor — BUG-14 fix calibrates to ~4 trades/day
SHARPE_ANNUALIZATION = float(np.sqrt(365 * 4))

# Signal thresholds — BUG-2 fix:
# original 5.5/6.5 overlapped; corrected to 8.0 LONG / 4.0 SHORT
SCORE_LONG_THRESHOLD = 8.0
SCORE_SHORT_THRESHOLD = 4.0


# ── OHLCV fetch ─────────────────────────────────────────────────────


def fetch_ohlcv(
    symbol: str,
    timeframe: str = "4h",
    limit: int = 1080,
) -> np.ndarray:
    """
    Fetch OHLCV bars from Binance USDT-M futures via ccxt.

    Returns an array of shape (N, 6): [timestamp_ms, open, high, low, close, volume].

    Public endpoint — no API keys required. Fetched in batches if `limit`
    exceeds ccxt's max single-request limit (typically 1500 for Binance
    USDT-M klines).
    """
    import ccxt  # local import — keeps top-level module light

    exchange = ccxt.binanceusdm({"enableRateLimit": True})
    bars: list = []
    remaining = limit
    until_ms = None

    # ccxt fetches in reverse-chronological batches when `since` is None;
    # we fetch the most recent `limit` bars by paging backward.
    while remaining > 0:
        batch_size = min(remaining, 1500)
        batch = exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, limit=batch_size, params={"until": until_ms}
        )
        if not batch:
            break
        bars = batch + bars  # prepend older bars
        remaining -= len(batch)
        until_ms = batch[0][0] - 1  # next batch ends just before this one
        if len(batch) < batch_size:
            break  # exchange returned fewer than requested — end of history

    arr = np.array(bars, dtype=np.float64)
    if arr.shape[0] == 0:
        raise RuntimeError(f"No OHLCV data returned for {symbol} {timeframe}")
    return arr


def synthetic_ohlcv(n: int = 500, seed: int = 0) -> np.ndarray:
    """
    Generate deterministic synthetic OHLCV for tests / smoke runs.

    Random walk with drift + noise; produces realistic bar structure
    (high >= max(open,close), low <= min(open,close)) so the scorer
    accepts it without OHLC-violation rejections (per BUG-3 fix).
    """
    rng = np.random.default_rng(seed)
    closes = 50000.0 + np.cumsum(rng.normal(0, 200, size=n))
    closes = np.maximum(closes, 1000.0)  # avoid negative prices
    opens = np.concatenate([[closes[0]], closes[:-1]])
    spreads = np.abs(rng.normal(0, 100, size=n))
    highs = np.maximum(opens, closes) + spreads
    lows = np.minimum(opens, closes) - spreads
    lows = np.maximum(lows, 100.0)
    volumes = rng.uniform(50, 500, size=n)
    timestamps = np.arange(n, dtype=np.float64) * 14400000.0  # 4h in ms
    return np.stack([timestamps, opens, highs, lows, closes, volumes], axis=1)


# ── Scorer evaluation ───────────────────────────────────────────────


def score_bars(ohlcv: np.ndarray) -> np.ndarray:
    """
    Run the on-main FixedScorer over the bar array; return per-bar scores
    in the range 0-12.

    The scorer is causal (each bar's score only uses past bars) so the
    output at index i depends only on ohlcv[0:i+1] — no look-ahead.
    """
    # Local import — keeps validation/ package importable without engine deps
    # in environments where only the test infra is available.
    from engine.signals.scoring_fixed import FixedScorer

    scorer = FixedScorer()
    opens = ohlcv[:, 1]
    highs = ohlcv[:, 2]
    lows = ohlcv[:, 3]
    closes = ohlcv[:, 4]
    volumes = ohlcv[:, 5]

    rsi = scorer.calculate_rsi(closes)
    ema_fast = scorer.calculate_ema(closes, scorer.ema_fast)
    ema_slow = scorer.calculate_ema(closes, scorer.ema_slow)
    atr = scorer.calculate_atr(highs, lows, closes)

    # Volume MA — use a 20-bar SMA as the volume baseline (the scorer's
    # public method takes volume_ma as input).
    window = 20
    volume_ma = np.array(
        [volumes[max(0, i - window + 1) : i + 1].mean() for i in range(len(volumes))]
    )

    # Simplified liquidity proxy: high-low spread as a fraction of close.
    # The scorer's score_liquidity expects (bid_ask_spread, close); we
    # substitute (h-l)/close as a public-data approximation since we don't
    # have order-book data offline.
    spread = highs - lows

    s_mom = scorer.score_momentum(rsi)
    s_trend = scorer.score_trend(closes, ema_fast, ema_slow)
    s_vol = scorer.score_volatility(atr, closes)
    s_volm = scorer.score_volume(volumes, volume_ma)
    s_entry = scorer.score_entry(closes, ema_fast, atr)
    s_liq = scorer.score_liquidity(spread, closes)

    total = s_mom + s_trend + s_vol + s_volm + s_entry + s_liq
    return total.astype(np.float64)


def direction_from_score(score: float) -> int:
    """Return +1 (LONG), -1 (SHORT), or 0 (NO TRADE) for a given score."""
    if score >= SCORE_LONG_THRESHOLD:
        return +1
    if score <= SCORE_SHORT_THRESHOLD:
        return -1
    return 0


# ── Trade simulation ────────────────────────────────────────────────


@dataclass
class Trade:
    """A single simulated trade — directional quality only, not P&L."""
    bar_index: int
    direction: int  # +1 long, -1 short
    score: float
    pnl_pct: float  # +0.01 (win) or -0.01 (loss), per §5 methodology


def simulate_trades(
    scores: np.ndarray,
    closes: np.ndarray,
    start: int,
    end: int,
) -> List[Trade]:
    """
    For each bar index t in [start, end), if the score at t crosses the
    LONG or SHORT threshold and a next-bar close exists, simulate a
    ±1% directional outcome.

    +1% if next-bar direction matches the signal, -1% otherwise. This
    is the "signal direction quality" measure per p0-evidence-pack §5,
    not a P&L projection.
    """
    trades: List[Trade] = []
    for t in range(start, min(end, len(closes) - 1)):
        d = direction_from_score(scores[t])
        if d == 0:
            continue
        actual = +1 if closes[t + 1] > closes[t] else -1
        # Win: signal direction matches actual direction
        win = (d == actual)
        pnl = 0.01 if win else -0.01
        trades.append(Trade(bar_index=t, direction=d, score=float(scores[t]), pnl_pct=pnl))
    return trades


# ── Metrics ──────────────────────────────────────────────────────────


@dataclass
class FoldMetrics:
    """Per-fold metrics for one symbol's trades."""
    symbol: str
    fold_label: str         # e.g. "fold_1" or "path_03"
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    n_test_bars: int
    n_trades: int
    n_wins: int
    n_losses: int
    win_rate: float
    avg_return_pct: float
    sharpe: float
    max_drawdown_pct: float
    passed: bool            # Sharpe > 0.8 AND max DD > -25%

    def as_row(self) -> List:
        return [
            self.symbol, self.fold_label,
            self.train_start, self.train_end, self.test_start, self.test_end,
            self.n_test_bars, self.n_trades, self.n_wins, self.n_losses,
            f"{self.win_rate:.3f}",
            f"{self.avg_return_pct:+.4f}",
            f"{self.sharpe:+.3f}",
            f"{self.max_drawdown_pct:+.2%}",
            "PASS" if self.passed else "FAIL",
        ]

    @staticmethod
    def csv_header() -> List[str]:
        return [
            "symbol", "fold",
            "train_start", "train_end", "test_start", "test_end",
            "n_test_bars", "n_trades", "n_wins", "n_losses",
            "win_rate", "avg_return_pct", "sharpe", "max_drawdown_pct",
            "pass",
        ]


def compute_metrics(
    symbol: str,
    fold_label: str,
    trades: Sequence[Trade],
    train_start: int,
    train_end: int,
    test_start: int,
    test_end: int,
) -> FoldMetrics:
    """
    Compute the per-fold metrics from a list of trades.

    Sharpe uses SHARPE_ANNUALIZATION (sqrt(365*4) per BUG-14).
    Max drawdown uses the cumulative trade-return path.
    Pass criteria: Sharpe > 0.8 AND max_dd > -25% per §5.
    """
    n_test_bars = test_end - test_start
    n_trades = len(trades)
    wins = sum(1 for t in trades if t.pnl_pct > 0)
    losses = n_trades - wins
    returns = np.array([t.pnl_pct for t in trades], dtype=np.float64)

    if n_trades == 0:
        # No signals fired — degenerate fold. Mark FAIL.
        return FoldMetrics(
            symbol=symbol, fold_label=fold_label,
            train_start=train_start, train_end=train_end,
            test_start=test_start, test_end=test_end,
            n_test_bars=n_test_bars,
            n_trades=0, n_wins=0, n_losses=0,
            win_rate=0.0, avg_return_pct=0.0,
            sharpe=0.0, max_drawdown_pct=0.0, passed=False,
        )

    avg_return = float(returns.mean())
    std_return = float(returns.std(ddof=1)) if n_trades > 1 else 0.0
    sharpe = (avg_return / std_return) * SHARPE_ANNUALIZATION if std_return > 0 else 0.0

    # Max drawdown over cumulative trade returns
    cumulative = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = cumulative - running_max
    max_dd = float(drawdowns.min()) if len(drawdowns) > 0 else 0.0

    passed = (sharpe > 0.8) and (max_dd > -0.25)

    return FoldMetrics(
        symbol=symbol, fold_label=fold_label,
        train_start=train_start, train_end=train_end,
        test_start=test_start, test_end=test_end,
        n_test_bars=n_test_bars,
        n_trades=n_trades, n_wins=wins, n_losses=losses,
        win_rate=float(wins / n_trades) if n_trades else 0.0,
        avg_return_pct=avg_return,
        sharpe=sharpe,
        max_drawdown_pct=max_dd,
        passed=passed,
    )


# ── Output writers ───────────────────────────────────────────────────


def write_csv(rows: Iterable[FoldMetrics], path: str) -> None:
    """Write fold metrics to a CSV file with the canonical header."""
    import csv
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FoldMetrics.csv_header())
        for r in rows:
            writer.writerow(r.as_row())


def metrics_to_markdown_table(rows: Sequence[FoldMetrics]) -> str:
    """Render fold metrics as a markdown table (sortable in any viewer)."""
    header = FoldMetrics.csv_header()
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r.as_row()) + " |")
    return "\n".join(lines)

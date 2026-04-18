"""
Walk-Forward Validation
=======================
Tests the CoinScope scoring system on out-of-sample windows to
check for overfitting.  Called by the /validate API endpoint.

Usage:
    python validation/walk_forward_validation.py
    curl http://localhost:8001/validate?symbol=BTC/USDT&limit=1000
"""

from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scoring_fixed import FixedScorer


# ── Data Helpers ─────────────────────────────────────────────────────────────

def fetch_data(symbol: str = "BTC/USDT", timeframe: str = "4h",
               limit: int = 1000) -> pd.DataFrame:
    """Fetch OHLCV data from Binance via ccxt."""
    try:
        import ccxt
        exchange = ccxt.binanceusdm({"enableRateLimit": True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
        df.index = pd.to_datetime(df["ts"], unit="ms")
        return df
    except Exception as e:
        print(f"[WFV] fetch_data error: {e}")
        return pd.DataFrame()


# ── Metrics Helpers ──────────────────────────────────────────────────────────

def _sharpe(returns: np.ndarray, trades_per_day: int = 4) -> float:
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    return (returns.mean() / returns.std()) * np.sqrt(365 * trades_per_day)


def _max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min())


# ── Walk-Forward Validator ───────────────────────────────────────────────────

class WalkForwardValidator:
    """
    Splits data into N folds.  Each fold:
      - train  : first 70% of the fold
      - test   : remaining 30% (out-of-sample)
    Reports Sharpe, max-drawdown, and win-rate on the test slice.
    """

    def __init__(self, df: pd.DataFrame, n_folds: int = 3,
                 train_ratio: float = 0.70):
        self.df = df
        self.n_folds = n_folds
        self.train_ratio = train_ratio
        self.scorer = FixedScorer()
        self.results: list = []

    # ── fold runner ──────────────────────────────────────────────────────────

    def _run_fold(self, fold_df: pd.DataFrame, fold_idx: int) -> dict:
        n = len(fold_df)
        split = int(n * self.train_ratio)
        test_df = fold_df.iloc[split:]

        if len(test_df) < 30:
            return {"fold": fold_idx, "passed": False, "reason": "too few bars"}

        c  = test_df["close"].values
        h  = test_df["high"].values
        lo = test_df["low"].values
        v  = test_df["vol"].values
        spread = h - lo

        try:
            signals, _ = self.scorer.generate_signals(c, h, lo, v, spread)
        except Exception as e:
            return {"fold": fold_idx, "passed": False, "reason": str(e)}

        # Simulate returns: +1% on LONG, -1% on SHORT (simplified)
        returns = []
        for i in range(1, len(signals)):
            sig = signals[i - 1]
            if sig == 0:
                continue
            ret = (c[i] - c[i - 1]) / c[i - 1]
            returns.append(ret * sig)   # LONG=+1, SHORT=-1

        if not returns:
            return {"fold": fold_idx, "passed": False, "reason": "no signals generated"}

        rets = np.array(returns)
        equity = np.cumprod(1 + rets) * 10_000
        sharpe = _sharpe(rets)
        mdd = _max_drawdown(equity)
        wins = (rets > 0).sum()
        win_rate = wins / len(rets) if len(rets) else 0.0

        passed = sharpe > 0.8 and mdd > -0.25

        return {
            "fold":      fold_idx,
            "bars":      len(test_df),
            "trades":    len(rets),
            "sharpe":    round(sharpe, 3),
            "max_dd":    round(mdd, 3),
            "win_rate":  round(win_rate, 3),
            "passed":    passed,
        }

    # ── public API ───────────────────────────────────────────────────────────

    def run_all(self) -> bool:
        """Run all folds.  Returns True if every fold passes."""
        if self.df.empty or len(self.df) < 100:
            self.results = [{"fold": 0, "passed": False, "reason": "insufficient data"}]
            return False

        fold_size = len(self.df) // self.n_folds
        all_passed = True

        for i in range(self.n_folds):
            fold_df = self.df.iloc[i * fold_size: (i + 1) * fold_size]
            result  = self._run_fold(fold_df, i + 1)
            self.results.append(result)
            if not result.get("passed"):
                all_passed = False
            print(f"  [WFV] Fold {i+1}: Sharpe={result.get('sharpe','N/A')} "
                  f"MaxDD={result.get('max_dd','N/A')} "
                  f"{'✅ PASS' if result.get('passed') else '❌ FAIL'}")

        return all_passed


# ── CLI Entry-point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    symbol = "BTC/USDT"
    print(f"[WFV] Fetching data for {symbol} ...")
    df = fetch_data(symbol, "4h", 1000)
    if df.empty:
        print("[WFV] No data fetched — aborting.")
    else:
        validator = WalkForwardValidator(df)
        passed    = validator.run_all()
        print(f"\n[WFV] Overall: {'✅ PASSED' if passed else '❌ FAILED'}")
        for r in validator.results:
            print(f"  Fold {r['fold']}: {r}")

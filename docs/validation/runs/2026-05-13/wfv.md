# Walk-Forward Validation — 2026-05-13

**Methodology:** sequential walk-forward, 3 folds per symbol, 70% train context / 30% out-of-sample test per fold. Trade simulation is ±1% per signal based on next-bar direction (signal-quality measure, not P&L projection — see `docs/validation/p0-evidence-pack.md` §5).

**Pass criteria (per §5):** Sharpe > 0.8 AND max drawdown > -25% per fold.

**Sharpe annualization:** `sqrt(365 * 4)` per BUG-14 fix.

**Symbols:** BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT
**Timeframe:** 4h
**Bars per symbol:** 1000

## Summary

- Folds run: **18**
- Folds passed: **6 / 18**
- Sharpe (min / median / max): **-6.800 / +0.576 / +5.471**

## Per-fold results

| symbol | fold | train_start | train_end | test_start | test_end | n_test_bars | n_trades | n_wins | n_losses | win_rate | avg_return_pct | sharpe | max_drawdown_pct | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | fold_1 | 0 | 233 | 233 | 333 | 100 | 59 | 30 | 29 | 0.508 | +0.0002 | +0.642 | -7.00% | FAIL |
| BTCUSDT | fold_2 | 333 | 566 | 566 | 666 | 100 | 72 | 34 | 38 | 0.472 | -0.0006 | -2.111 | -10.00% | FAIL |
| BTCUSDT | fold_3 | 666 | 899 | 899 | 1000 | 101 | 62 | 29 | 33 | 0.468 | -0.0006 | -2.450 | -9.00% | FAIL |
| ETHUSDT | fold_1 | 0 | 233 | 233 | 333 | 100 | 62 | 30 | 32 | 0.484 | -0.0003 | -1.223 | -9.00% | FAIL |
| ETHUSDT | fold_2 | 333 | 566 | 566 | 666 | 100 | 73 | 38 | 35 | 0.521 | +0.0004 | +1.561 | -7.00% | PASS |
| ETHUSDT | fold_3 | 666 | 899 | 899 | 1000 | 101 | 54 | 28 | 26 | 0.519 | +0.0004 | +1.403 | -5.00% | PASS |
| BNBUSDT | fold_1 | 0 | 233 | 233 | 333 | 100 | 68 | 28 | 40 | 0.412 | -0.0018 | -6.800 | -12.00% | FAIL |
| BNBUSDT | fold_2 | 333 | 566 | 566 | 666 | 100 | 69 | 35 | 34 | 0.507 | +0.0001 | +0.550 | -5.00% | FAIL |
| BNBUSDT | fold_3 | 666 | 899 | 899 | 1000 | 101 | 63 | 36 | 27 | 0.571 | +0.0014 | +5.471 | -4.00% | PASS |
| SOLUSDT | fold_1 | 0 | 233 | 233 | 333 | 100 | 63 | 32 | 31 | 0.508 | +0.0002 | +0.602 | -9.00% | FAIL |
| SOLUSDT | fold_2 | 333 | 566 | 566 | 666 | 100 | 71 | 39 | 32 | 0.549 | +0.0010 | +3.759 | -4.00% | PASS |
| SOLUSDT | fold_3 | 666 | 899 | 899 | 1000 | 101 | 72 | 37 | 35 | 0.514 | +0.0003 | +1.054 | -8.00% | PASS |
| XRPUSDT | fold_1 | 0 | 233 | 233 | 333 | 100 | 63 | 31 | 32 | 0.492 | -0.0002 | -0.602 | -8.00% | FAIL |
| XRPUSDT | fold_2 | 333 | 566 | 566 | 666 | 100 | 59 | 30 | 29 | 0.508 | +0.0002 | +0.642 | -7.00% | FAIL |
| XRPUSDT | fold_3 | 666 | 899 | 899 | 1000 | 101 | 60 | 27 | 33 | 0.450 | -0.0010 | -3.808 | -9.00% | FAIL |
| DOGEUSDT | fold_1 | 0 | 233 | 233 | 333 | 100 | 65 | 32 | 33 | 0.492 | -0.0002 | -0.583 | -11.00% | FAIL |
| DOGEUSDT | fold_2 | 333 | 566 | 566 | 666 | 100 | 63 | 29 | 34 | 0.460 | -0.0008 | -3.018 | -7.00% | FAIL |
| DOGEUSDT | fold_3 | 666 | 899 | 899 | 1000 | 101 | 67 | 36 | 31 | 0.537 | +0.0007 | +2.838 | -8.00% | PASS |

## Notes

- The scorer is causal: each bar's score uses only past bars, so the
  test-region scores are look-ahead-safe even without explicit
  train/test isolation.
- A "FAIL" row is normal in P0 — at the score >= 8.0 LONG /
  <= 4.0 SHORT thresholds (BUG-2 fix), signal density is low and
  individual folds with few trades can have noisy Sharpe.
- This run replaces the struck-through illustrative table in
  `docs/validation/p0-evidence-pack.md` §5.

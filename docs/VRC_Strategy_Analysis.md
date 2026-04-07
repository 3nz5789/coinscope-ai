# CoinScopeAI Strategy Analysis: Volume-Regime Composite (VRC)

**Date:** April 6, 2026  
**Author:** CoinScopeAI Core Agent  
**Environment Tier:** Research Idea (Failed to reach Prototype)

## 1. Objective and Methodology

The objective of this research was to implement and validate the first real trading strategy for the CoinScopeAI system. The strategy, named the **Volume-Regime Composite (VRC)**, was designed to mirror the core logic of the production `CoinScopeOrchestrator` pipeline without relying on external dependencies. 

The strategy incorporates:
- **Regime Detection:** EMA slope and volatility clustering (proxy for HMM).
- **Multi-Factor Scoring:** RSI momentum, EMA trend alignment, and volume spikes.
- **Risk Management:** ATR-based stop-loss (capped at 2%), 2:1 reward-to-risk take-profit, and consecutive loss circuit breakers.
- **Position Sizing:** Regime-aware signal strength scaling (proxy for Kelly sizing).

### Validation Methodology
To ensure rigorous validation, the strategy was tested against **110,365 real 1h and 4h candles** from Binance (April 2024 – April 2026) across five major pairs (BTC, ETH, SOL, BNB, XRP). The validation process included:
1. **Full In-Sample Backtest:** Testing the static configuration across all 10 symbol/timeframe combinations.
2. **Walk-Forward Analysis:** A 5-split rolling window analysis (70% train, 30% test) on BTC, ETH, and SOL to detect overfitting and measure true out-of-sample (OOS) robustness.
3. **Realistic Execution:** Modeled with 0.05% taker fees, 0.02% maker fees, and volume-proportional slippage.

## 2. Full Backtest Results (In-Sample)

The initial backtest results were unequivocally negative. Across all 10 configurations, the strategy failed to produce a positive return.

| Symbol | Timeframe | Return (%) | Sharpe Ratio | Max Drawdown (%) | Win Rate (%) | Profit Factor | Total Trades |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| BTCUSDT | 1h | -1.77 | -1.63 | 1.87 | 34.76 | 0.91 | 1122 |
| BTCUSDT | 4h | -0.44 | -0.41 | 0.59 | 34.17 | 0.98 | 477 |
| ETHUSDT | 1h | -3.18 | -2.07 | 3.34 | 32.78 | 0.88 | 1397 |
| ETHUSDT | 4h | -2.69 | -1.88 | 2.83 | 31.25 | 0.85 | 816 |
| SOLUSDT | 1h | -3.60 | -1.85 | 4.07 | 32.99 | 0.91 | 1752 |
| SOLUSDT | 4h | -2.38 | -1.41 | 2.59 | 33.33 | 0.91 | 1101 |
| BNBUSDT | 1h | -2.93 | -2.33 | 2.96 | 32.30 | 0.86 | 1263 |
| BNBUSDT | 4h | -2.31 | -1.86 | 2.38 | 32.28 | 0.82 | 604 |
| XRPUSDT | 1h | -1.23 | -0.65 | 1.33 | 34.81 | 0.99 | 1666 |
| XRPUSDT | 4h | -0.72 | -0.43 | 1.14 | 34.29 | 0.99 | 945 |

**Aggregate Statistics:**
- **Mean Return:** -2.12%
- **Mean Sharpe:** -1.45
- **Mean Win Rate:** 33.30%
- **Profitable Configurations:** 0 / 10

The low win rate (~33%) combined with a profit factor consistently below 1.0 indicates that the 2:1 reward-to-risk ratio is not being achieved frequently enough to overcome the losing trades and execution costs.

## 3. Walk-Forward Analysis (Out-of-Sample)

To confirm that the poor performance was a structural lack of edge rather than just a poor static parameter choice, a walk-forward analysis was conducted.

| Configuration | IS Return (%) | OOS Return (%) | IS Sharpe | OOS Sharpe | OOS Win Rate (%) | Robustness | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| BTCUSDT_1h | -0.29 | -0.06 | -2.19 | -0.65 | 35.41 | 0.69 | STRONG |
| BTCUSDT_4h | -0.08 | -0.05 | -0.64 | -0.91 | 33.33 | 0.35 | MODERATE |
| ETHUSDT_1h | -0.44 | -0.20 | -2.00 | -2.12 | 32.33 | 0.00 | WEAK |
| ETHUSDT_4h | -0.31 | -0.32 | -1.61 | -4.00 | 26.70 | 0.00 | WEAK |
| SOLUSDT_1h | -0.68 | -0.02 | -2.44 | -0.69 | 34.99 | 0.30 | MODERATE |
| SOLUSDT_4h | -0.23 | -0.25 | -1.04 | -2.91 | 30.04 | 0.10 | WEAK |

**Walk-Forward Diagnostics:**
- **Mean IS Return:** -0.34%
- **Mean OOS Return:** -0.15%
- **OOS Profitable:** 0 / 6 configurations

The walk-forward analysis confirms the initial findings: **the strategy possesses no statistical edge.** The out-of-sample performance is consistently negative. Interestingly, the "Robustness" score for BTCUSDT_1h is rated "STRONG" (0.69), but this simply means the strategy is *robustly unprofitable* — it loses money in-sample and continues to lose money out-of-sample at a predictable rate.

## 4. Analysis and Diagnosis

The VRC strategy fails for several structural reasons inherent to the current CoinScopeAI signal logic:

1. **Trend-Following Lag in Mean-Reverting Markets:** The strategy relies heavily on EMA alignment and RSI momentum. In the crypto markets of 2024-2026, which featured extended periods of high-volatility chop, these indicators trigger entries too late. By the time the trend is confirmed and volume spikes, the local move is often exhausted, leading to immediate drawdowns.
2. **Rigid Risk-Reward Mechanics:** The strict 2:1 take-profit vs. ATR-based stop-loss forces the strategy into a low win-rate profile. While a 33% win rate can be profitable if winners are allowed to run, the hard take-profit truncates the right tail of the return distribution. The strategy takes small, frequent losses but caps its winners, resulting in a negative expected value.
3. **Execution Drag:** With over 1,000 trades per pair on the 1h timeframe, the strategy is highly sensitive to execution costs. The modeled 0.05% taker fee and slippage create a significant drag that the weak alpha cannot overcome.

## 5. Conclusion and Next Steps

**Verdict:** The Volume-Regime Composite strategy does not possess a tradable edge. It should **not** be advanced to the Prototype or Staging tiers.

This is a successful validation exercise. The backtesting engine and walk-forward framework functioned exactly as intended, preventing a flawed conceptual model from reaching live execution.

**Recommended Next Steps for Quant Research:**
1. **Abandon static indicator scoring:** The `FixedScorer` approach (assigning points for RSI/EMA alignment) is too rigid. Research should pivot toward statistical arbitrage or machine-learning-based predictive models.
2. **Dynamic Exits:** Replace the hard 2:1 take-profit with trailing stops or time-based exits to capture the fat tails of crypto momentum.
3. **Reduce Trade Frequency:** The 1h timeframe generates too much noise and fee drag. Future research should focus on the 4h or Daily timeframes, aiming for higher-conviction setups.

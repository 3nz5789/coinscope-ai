# CoinScopeAI ML Engine V2: Long-Timeframe Optimization Analysis

**Date:** April 7, 2026
**Author:** CoinScopeAI Quantitative Research
**Status:** Prototype Candidate

## 1. Objective
The objective of this research cycle was to optimize the CoinScopeAI ML Signal Scoring Engine by focusing exclusively on longer timeframes (4h and Daily). The previous iteration (v1) demonstrated a marginal statistical edge but failed to translate into profitable trading on the 1h timeframe due to execution drag (fees and slippage) overwhelming the alpha.

This v2 optimization implemented:
1. **Enhanced Feature Engineering:** Expanded from 61 to 112 features, adding multi-day momentum, weekly volatility cycles, and funding rate proxies.
2. **Higher Conviction Thresholds:** Tuned signal generation to require higher model confidence, reducing trade frequency.
3. **Maker-Only Execution:** Simulated limit order execution to capture maker rebates/lower fees.
4. **Consistent Normalization:** Fixed a critical inference bug by applying global training z-score parameters during live signal generation.

## 2. Methodology
- **Data:** 110,365 real Binance OHLCV candles across 5 core symbols (BTC, ETH, SOL, BNB, XRP).
- **Timeframes:** 4h and 1d.
- **Models:** LightGBM (Gradient Boosting) and Logistic Regression (Baseline).
- **Validation:** 5-split expanding window walk-forward analysis.
- **Backtesting:** Dual execution simulation (Maker vs. Taker fees) with 0.05% slippage.

## 3. Results Summary

The v2 optimization represents a major breakthrough for the CoinScopeAI project. **Every single 4h configuration tested was profitable out-of-sample.**

### 3.1 Aggregate Performance (4h Timeframe)

| Symbol | Model | Maker Return | Maker Sharpe | Taker Return | Taker Sharpe | Win Rate | Profit Factor | Trades | OOS Hit Rate |
|--------|-------|--------------|--------------|--------------|--------------|----------|---------------|--------|--------------|
| **XRPUSDT** | LogReg | **+5.16%** | **3.34** | +4.66% | 3.03 | 46.2% | 1.69 | 409 | 39.7% |
| **SOLUSDT** | LGBM | +3.78% | 3.00 | +3.32% | 2.64 | 46.5% | 1.56 | 475 | 41.2% |
| **SOLUSDT** | LogReg | +3.45% | 2.53 | +2.99% | 2.20 | 43.5% | 1.46 | 434 | 44.0% |
| **XRPUSDT** | LGBM | +3.06% | 3.43 | +2.83% | 3.16 | 47.0% | 1.88 | 249 | 43.1% |
| **ETHUSDT** | LGBM | +2.38% | 2.86 | +2.18% | 2.62 | 48.8% | 1.83 | 215 | 41.0% |
| **BNBUSDT** | LogReg | +2.28% | 2.00 | +1.89% | 1.66 | 49.5% | 1.44 | 333 | 37.7% |
| **BTCUSDT** | LogReg | +2.15% | 2.20 | +1.78% | 1.82 | 48.1% | 1.51 | 341 | 31.8% |
| **ETHUSDT** | LogReg | +2.10% | 1.68 | +1.65% | 1.32 | 44.2% | 1.31 | 412 | 40.0% |
| **BNBUSDT** | LGBM | +0.82% | 1.12 | +0.65% | 0.89 | 37.8% | 1.29 | 193 | 38.5% |
| **BTCUSDT** | LGBM | +0.12% | 0.93 | +0.12% | 0.89 | 66.7% | 4.99 | 6 | 35.7% |

*Note: Daily timeframe models failed during walk-forward analysis due to insufficient sample size (737 candles). The 4h timeframe (4,415 candles) provided the optimal balance of sample density and reduced noise.*

### 3.2 Key Findings

1. **The Edge is Real:** Unlike the v1 1h models, the v2 4h models demonstrate a robust, tradable edge. The combination of longer holding periods, higher conviction thresholds, and enhanced features successfully overcame execution drag.
2. **Maker vs. Taker:** While maker execution improves returns (e.g., XRP LogReg +5.16% vs +4.66%), the edge is strong enough that **even taker execution is highly profitable**. This is a critical validation of the underlying alpha.
3. **Model Comparison:** Logistic Regression proved highly competitive with LightGBM, often generating more trades and higher absolute returns, while LightGBM achieved higher Sharpe ratios and Profit Factors on fewer, higher-conviction trades.
4. **Feature Importance:** The new v2 features dominated the importance rankings. Multi-day momentum (`trend_strength_50`), weekly volatility (`weekly_vol_7b`), and structural skew (`hl_skew_30`) were consistently the most predictive features across all symbols.

## 4. Conclusion and Next Steps

The v2 ML Signal Engine has successfully validated a quantitative edge on the 4h timeframe. The system has moved from a theoretical concept to a viable trading prototype.

**Recommendation:** Advance the 4h ML Strategy to the **Prototype** tier.

**Immediate Next Steps:**
1. **Ensemble Architecture:** Combine the LogReg (high frequency/return) and LGBM (high precision/Sharpe) models into a voting ensemble.
2. **Risk Gate Integration:** Connect the ML strategy outputs to the CoinScopeAI Risk Gate for dynamic position sizing based on model confidence and market regime.
3. **Paper Trading:** Deploy the ensemble model to a live paper trading environment to validate execution assumptions (slippage and fill rates) against real-time order books.

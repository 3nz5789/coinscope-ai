# CoinScopeAI — Week 1 Integration Report

**Date:** April 8, 2026  
**Author:** Mohammed Abuanza / CoinScopeAI Engineering  
**Status:** 30-Day Testnet Validation Phase Begun  

This document serves as the comprehensive changelog and decision record for Week 1 of the CoinScopeAI quant crypto futures trading system integration. It covers the transition from the V2 ML Engine to the V3 Alpha Feature Engine, the deployment of the production frontend dashboard, the establishment of the multi-exchange data infrastructure, and the commencement of the 30-day paper trading validation phase.

---

## 1. V3 ML Engine Upgrade

The core signal generation engine has been upgraded from V2 to V3, introducing a significantly expanded feature set and resolving distribution shift issues that impacted live trading.

### Feature Engineering Expansion
The V3 Feature Engine now processes **162 features**, up from 112 in V2. The 50 new features are alpha proxies synthesized from 4h OHLCV data, designed to capture market microstructure and cross-exchange dynamics:
- **Funding Proxies (9):** Cross-exchange divergence, mean reversion, and predicted extremes.
- **Liquidation Proxies (10):** Cascade detection, cluster analysis, and long/short ratio proxies.
- **Open Interest Proxies (7):** Expansion/contraction rates and OI vs. price divergence.
- **Basis Proxies (10):** Premium/discount extremes, convergence/divergence, and z-scores.
- **OrderBook Proxies (14):** Book imbalance, depth-weighted mid, and liquidity cliff detection.

### Walk-Forward Validation Results
Out-of-sample (OOS) walk-forward validation on the 4h timeframe demonstrates a clear edge for the V3 LightGBM model over its V2 predecessor:

| Model Version | Accuracy | F1 Score | Hit Rate | Profit Factor |
|---------------|----------|----------|----------|---------------|
| **V3 LGBM** | 0.387 | 0.377 | 0.402 | **1.035** (+5.8%) |
| **V2 LGBM** | 0.382 | 0.375 | 0.399 | 0.978 |
| **V3 LogReg** | 0.369 | 0.362 | 0.382 | 0.804 |

*Note: The Logistic Regression model underperformed in pure ML metrics but remains valuable for its robustness against unnormalized features, avoiding the extreme confidence scores caused by distribution shifts in z-score normalization.*

**Top Predictive Alpha Features:** `oi_price_div_20`, `oi_vol_autocorr_20`, `funding_price_div`, `funding_mean_rev`, `ob_spread_5/10`, `oi_expansion_10/20`, and `funding_cumul_48`.

---

## 2. Critical Bug Fixes

During the initial Testnet deployment (Integration V2), the engine ran for 5.3 hours but generated zero signals. Root cause analysis identified four critical bugs blocking the signal pipeline, all of which have been resolved in the V3 release (Linear COI-37).

1. **API Mismatch:** The signal engine incorrectly called `feature_engine.compute(df)`, a method that did not exist. This has been corrected to `extract(df)`.
2. **Import Error:** The `FeatureEngineV2` import failed silently, causing the system to fall back to the V1 engine. This was fixed by correctly importing `LongTFFeatureEngine`.
3. **WebSocket Disconnect at Candle Close:** The WebSocket disconnected at 16:02:50 UTC, missing the 16:00 UTC 4h candle close event during the 1-second reconnect window. Because the ML engine requires a complete candle close to trigger inference, no signals were generated. **Fix:** Implemented a REST polling fallback after reconnection and a candle close watchdog to inject missed candles correctly.
4. **Normalization Distribution Shift:** Z-score normalization caused distribution shifts in live data, resulting in extreme confidence scores or all signals defaulting to neutral. The V3 Logistic Regression model now handles unnormalized raw features robustly.

---

## 3. Paper Trading Engine Live

The paper trading pipeline (Linear COI-28) is now fully operational and connected to the Binance Futures Testnet. The engine orchestrates signal polling, order execution, position tracking, and P&L reporting.

### Live Signal Verification
Upon restarting the engine with the V3 models, the system successfully generated actionable signals on its first run:

| Symbol | Direction | Confidence | Actionable |
|--------|-----------|------------|------------|
| **BTCUSDT** | SHORT | 0.876 | Yes |
| **XRPUSDT** | LONG | 0.942 | Yes |
| **BNBUSDT** | LONG | 0.612 | Yes |
| **SOLUSDT** | SHORT | 0.476 | Yes |
| **ETHUSDT** | NEUTRAL | (below threshold) | No |

The live engine is currently running, with WebSockets connected to all 5 streams. It executes strictly at 4h candle closes.

### Safety Constraints (Non-Bypassable)
The engine enforces a strict 4-layer safety gate hardcoded at the configuration level:
- **Testnet-only:** Mainnet URLs are blocked; attempting to use them raises a `RuntimeError`.
- **Max Daily Loss:** 5% absolute ceiling.
- **Max Drawdown:** 15% absolute ceiling (kill-switch at -20%).
- **Max Position Size:** 10% of equity per position.
- **Max Leverage:** 5x.
- **Max Concurrent Positions:** 5.

---

## 4. Multi-Exchange Data Infrastructure & Recording Daemon

Phase 1 and Phase 2 of the data infrastructure (Linear COI-32, COI-33, COI-34) have established a robust, zero-cost real-time data pipeline across Binance, Bybit, OKX, and Hyperliquid.

### Unified Streams
All exchange data is normalized into common schemas (MarkPrice, OrderBook, Trade, FundingRate, OpenInterest) and published to a thread-safe, async `EventBus`.
- **Tick Trades:** Unified WebSocket stream across all 4 exchanges.
- **L2 Order Book:** Unified L2 book with crossed-book detection and auto re-snapshot.
- **Funding Rates & Liquidations:** WebSocket where available, REST polling fallback.

### Recording Daemon
The `StreamRecorder` daemon captures market events 24/7, writing to compressed `JSONL.gz` files partitioned by event type and date. It currently captures approximately **133 events/sec** across the connected exchanges. A `ReplayEngine` allows for controlled-speed playback of historical tick data for backtesting.

---

## 5. Production Dashboard

The frontend trading terminal (Linear COI-36) is complete and deployed. Built with React 19, TypeScript, Vite 7, and Tailwind CSS 4, it features a military-grade HUD aesthetic (deep navy `#0a0e17`, emerald accents `#10b981`, JetBrains Mono typography).

### Dashboard Features
The application consists of 10 auto-refreshing pages:
1. **Overview:** At-a-glance summary (3–30s refresh).
2. **Live Scanner:** Signals with LONG/SHORT bias, confidence, and regime (3s refresh).
3. **Positions:** Open positions with live P&L (5s refresh).
4. **Equity Curve:** 7D/30D/90D range selector (30s refresh).
5. **Performance Metrics:** Sharpe ratio, win rate, P&L distribution (15s refresh).
6. **Alpha Signals:** 5 generators with strength meters (5s refresh).
7. **Regime State:** Market regime per symbol (10s refresh).
8. **Trade Journal:** Entry/exit, P&L, signal source (15s refresh).
9. **Risk Gate:** Daily loss, drawdown, kill switch status (5s refresh).
10. **Recording Daemon:** Events/sec, exchange connections (3s refresh).

The dashboard connects to the live engine at `localhost:8001` via the `VITE_API_BASE` environment variable, with a graceful mock data fallback (`USE_MOCK=true`) for development. A StatusBar displays an `ENGINE LIVE` or `MOCK DATA` badge.

---

## 6. Daily Telegram Reporting

System monitoring and observability are handled via the `@ScoopyAI_bot` Telegram integration. Automated status checks are scheduled daily at 08:00 UTC+3.

The daily report includes:
- Engine health and endpoint status (`/scan`, `/performance`, `/journal`, `/risk-gate`).
- Binance Testnet wallet balance and unrealized P&L.
- Recent signals and executed trades.
- Risk gate status (drawdown limits, daily loss).
- Recording daemon metrics (events/sec).

---

## 7. Workspace Sync & Project Management

The project maintains a fully synchronized workspace across multiple platforms:
- **GitHub:** Repository `3nz5789/coinscope-ai`. Over 10 PRs merged this week (PRs #4 through #10 covering paper trading, data streams, alpha generators, and the V3 engine).
- **Linear:** Issue tracking under the `COI` team. Key deliverables (COI-28, COI-32, COI-33, COI-34, COI-35, COI-36, COI-37) have been marked as Done.
- **Notion:** The CoinScopeAI OS Hub serves as the central knowledge base, housing the Executive Dashboard, Quant Research Lab, and Engineering Architecture documentation.
- **Google Drive:** Hosts detailed integration reports, ML upgrade analysis, and workflow documentation.

---

## 8. Current Status & Next Steps

The system has officially entered the **30-day Testnet validation phase**. 

### Validation Requirements
- A minimum of **7 clean days** of uninterrupted operation is required before the system can be considered for the Staging candidate tier.
- **Strict Code Freeze:** No engine code changes are permitted during the validation phase to ensure data integrity and accurate performance measurement.

### Upcoming Priorities (Post-Validation)
1. **Maker-Only Execution Optimization (Linear COI-29):** Implement dynamic limit order placement logic to target maker fills, maximizing the fee advantage identified in backtesting (e.g., XRP LogReg +5.16% maker vs +4.66% taker).
2. **Ensemble Meta-Learner (Linear COI-31):** Combine the Logistic Regression (higher absolute returns, more trades) and LightGBM (higher Sharpe, fewer trades) models into a voting ensemble for improved signal quality.
3. **Order Book Features (Linear COI-30):** Integrate funding rate, open interest, and bid/ask imbalance directly into the core feature set.

---
*End of Report*

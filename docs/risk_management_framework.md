# CoinScopeAI Risk Management Framework

**Author:** Manus AI
**Date:** April 6, 2026

This document details the comprehensive risk management framework implemented within the CoinScopeAI Crypto Futures Trading Agent. The system is designed to protect capital and ensure long-term profitability by enforcing strict risk controls at every level of the trading process.

## 1. Core Philosophy

The primary objective of CoinScopeAI is capital preservation. The system operates on the principle that avoiding catastrophic losses is more important than maximizing short-term gains. Risk management is not an afterthought; it is integrated directly into the core trading engine and AI models.

The framework is built upon three pillars:
1.  **Pre-Trade Risk Assessment:** Evaluating the market environment and portfolio exposure before any trade is executed.
2.  **Dynamic Position Sizing:** Calculating the optimal trade size based on current account equity and the specific risk of the signal.
3.  **Active Trade Management:** Monitoring open positions and adjusting stop-loss levels to protect profits and limit downside.

## 2. The Risk Gate System

The Risk Gate is a centralized component that acts as a final checkpoint before any order is sent to the exchange. It evaluates multiple criteria to determine if trading is currently permissible.

### 2.1 Drawdown Limits

The system continuously monitors the account's equity curve to prevent excessive losses during unfavorable market conditions.

| Metric | Threshold | Action if Breached |
| :--- | :--- | :--- |
| **Daily Drawdown** | -5.0% | Halts all new trading activity for the remainder of the trading day. |
| **Weekly Drawdown** | -10.0% | Halts all new trading activity until the start of the next trading week. |
| **Maximum Drawdown** | -20.0% | Triggers an emergency stop, closing all open positions and requiring manual intervention to restart the engine. |

### 2.2 Portfolio Heat and Exposure

To prevent over-concentration in a single asset or direction, the Risk Gate monitors the total portfolio exposure.

*   **Maximum Open Positions:** The system limits the total number of concurrent open trades (e.g., maximum 5 positions) to manage cognitive load and margin requirements.
*   **Correlation Limits:** The engine analyzes the correlation between active positions. If multiple highly correlated assets (e.g., BTC and ETH) are signaling in the same direction, the Risk Gate may block subsequent trades to avoid compounded risk.
*   **Directional Bias:** The system tracks the net long/short exposure. If the portfolio is heavily skewed (e.g., 80% long), the Risk Gate may require higher confidence scores for new long signals or prioritize short signals to balance the portfolio.

### 2.3 Market Regime Filters

The AI-driven Regime Detector continuously analyzes market volatility and trend strength. The Risk Gate adjusts its parameters based on the detected regime.

*   **High Volatility Regime:** During periods of extreme market turbulence (e.g., news events, flash crashes), the Risk Gate may temporarily suspend trading or require significantly wider stop-loss distances.
*   **Choppy/Ranging Regime:** When the market lacks a clear trend, the system may reduce position sizes or avoid breakout strategies entirely, favoring mean-reversion approaches.

## 3. Position Sizing Methodology

CoinScopeAI employs dynamic position sizing to ensure that each trade risks a consistent percentage of the total account equity, regardless of the asset's price or volatility.

### 3.1 Fixed Fractional Sizing

The primary method used is fixed fractional sizing. The user defines a maximum risk percentage per trade (e.g., 1.0% of the account balance).

**Calculation:**
1.  Determine the Account Balance (e.g., $10,000).
2.  Calculate the Risk Amount (e.g., 1.0% of $10,000 = $100).
3.  Determine the Stop-Loss Distance based on technical analysis (e.g., 2.0% from entry price).
4.  Calculate the Position Size: `Risk Amount / Stop-Loss Distance` (e.g., $100 / 0.02 = $5,000 position value).

### 3.2 Kelly Criterion Integration

For advanced users, the system can incorporate the Kelly Criterion to optimize capital growth based on the historical win rate and profit factor of the specific trading strategy.

*   **Half-Kelly Approach:** To mitigate the aggressive nature of the full Kelly formula, CoinScopeAI defaults to a "Half-Kelly" or "Quarter-Kelly" fraction, providing a more conservative growth curve while still capitalizing on high-probability setups.

## 4. Active Trade Management

Once a position is open, the Order Manager actively monitors it to protect capital and secure profits.

### 4.1 Hard Stop-Losses

Every trade executed by CoinScopeAI must have a hard stop-loss order placed simultaneously at the exchange level. This ensures protection even in the event of a system failure or loss of connectivity.

### 4.2 Trailing Stops

As a trade moves into profit, the system employs dynamic trailing stops to lock in gains.

*   **Volatility-Based Trailing:** The trailing stop distance is often based on the Average True Range (ATR), allowing the position to breathe during normal market fluctuations while protecting against sudden reversals.
*   **Structure-Based Trailing:** The stop-loss may be trailed behind key market structures, such as recent swing lows (for long positions) or moving averages.

### 4.3 Time-Based Exits

If a trade fails to reach its profit target or stop-loss within a predefined timeframe (e.g., 48 hours for a short-term swing trade), the system may automatically close the position to free up capital for better opportunities.

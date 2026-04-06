# CoinScopeAI Trading Engine API Exploration Report

**Author:** Manus AI
**Date:** April 5, 2026

This document provides a comprehensive overview of the CoinScopeAI Trading Engine API, running locally at `http://localhost:8001`. The API is built using FastAPI and serves as an AI-powered cryptocurrency trading signal engine with risk management, market regime detection, and performance analytics.

## 1. Overview and Root Endpoints

The CoinScopeAI Trading Engine exposes several endpoints for retrieving trading signals, performance metrics, trade journals, risk assessments, position sizing, and market regime analysis. No authentication is required to access these endpoints.

### 1.1 Root Endpoint (`GET /`)

The root endpoint provides basic service information and a list of available endpoints.

**Response Structure:**
```json
{
    "service": "CoinScopeAI Trading Engine",
    "version": "1.0.0",
    "status": "operational",
    "timestamp": "2026-04-05T22:22:00.787644Z",
    "endpoints": [
        "GET /scan",
        "GET /performance",
        "GET /journal",
        "GET /risk-gate",
        "GET /position-size",
        "GET /regime/{symbol}",
        "GET /docs",
        "GET /openapi.json"
    ]
}
```

### 1.2 Health Check (`GET /health`)

A minimal health-check endpoint for monitoring the service status.

**Response Structure:**
```json
{
    "status": "healthy",
    "timestamp": "2026-04-05T22:22:21.396936Z",
    "uptime_seconds": 3600,
    "version": "1.0.0"
}
```

### 1.3 Tracked Symbols (`GET /symbols`)

Lists all cryptocurrency symbols tracked by the engine, along with their active status, exchange, and category.

**Response Structure:**
```json
{
    "total": 20,
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "active": true,
            "exchange": "Binance",
            "category": "major"
        },
        ...
    ],
    "last_updated": "2026-04-05T22:22:21.428243Z"
}
```

## 2. Core Trading Endpoints

### 2.1 Market Signals (`GET /scan`)

Scans the market for trading signals across all tracked symbols. It returns a ranked list of signal opportunities with scores, direction, and metadata.

**Query Parameters:**
*   `min_score` (optional, float): Minimum score required for a signal to be included.
*   `limit` (optional, integer, default: 20): Maximum number of signals to return.

**Response Structure:**
```json
{
    "scan_timestamp": "2026-04-05T22:22:21.140715Z",
    "total_symbols_scanned": 20,
    "signals_found": 20,
    "filters_applied": {
        "min_score": null,
        "limit": 20
    },
    "signals": [
        {
            "symbol": "DOGEUSDT",
            "score": 96.71,
            "direction": "SHORT",
            "confidence": 0.583,
            "price": 64095.4162,
            "volume_spike_x": 7.58,
            "indicators": {
                "rsi": 38.7,
                "macd_signal": "bullish_cross",
                "bb_position": "above_upper",
                "ema_trend": "bearish"
            },
            "timeframe": "4h",
            "signal_type": "breakout",
            "generated_at": "2026-04-05T22:22:21.140447Z"
        },
        ...
    ]
}
```

### 2.2 Performance Metrics (`GET /performance`)

Retrieves overall trading engine performance metrics, including win rate, profit factor, Sharpe ratio, drawdown, and equity curve summary.

**Response Structure:**
```json
{
    "report_generated_at": "2026-04-05T22:22:21.173939Z",
    "period": {
        "start": "2024-01-01T00:00:00Z",
        "end": "2026-04-05T22:22:21.173951Z",
        "trading_days": 461
    },
    "summary": {
        "total_trades": 1247,
        "winning_trades": 798,
        "losing_trades": 449,
        "win_rate_pct": 63.99,
        "avg_win_pct": 3.42,
        "avg_loss_pct": -1.87,
        "profit_factor": 2.31,
        "expectancy_pct": 1.51
    },
    "returns": {
        "total_return_pct": 284.7,
        "annualized_return_pct": 112.4,
        "best_trade_pct": 47.3,
        "worst_trade_pct": -12.8,
        "avg_trade_duration_hours": 6.4
    },
    "risk_metrics": {
        "sharpe_ratio": 2.87,
        "sortino_ratio": 4.12,
        "calmar_ratio": 3.54,
        "max_drawdown_pct": -18.6,
        "max_drawdown_duration_days": 23,
        "current_drawdown_pct": -3.2,
        "volatility_annualized_pct": 38.9,
        "var_95_daily_pct": -2.4
    },
    "monthly_returns_pct": { ... },
    "by_signal_type": { ... },
    "by_timeframe": { ... }
}
```

### 2.3 Trade Journal (`GET /journal`)

Retrieves the trade journal with detailed entry/exit records for all executed trades.

**Query Parameters:**
*   `limit` (optional, integer, default: 50): Maximum number of trades to return.
*   `symbol` (optional, string): Filter trades by a specific symbol.
*   `status` (optional, string): Filter trades by status (e.g., "open", "closed", "cancelled").

**Response Structure:**
```json
{
    "journal_generated_at": "2026-04-05T22:22:21.232634Z",
    "total_trades_in_db": 1247,
    "filters": {
        "symbol": null,
        "status": null,
        "limit": 10
    },
    "returned_count": 10,
    "trades": [
        {
            "trade_id": "CSA-10100",
            "symbol": "BNBUSDT",
            "direction": "SHORT",
            "status": "closed",
            "entry_price": 61119.9023,
            "exit_price": 64870.8307,
            "quantity": 1.0095,
            "leverage": 5,
            "pnl_pct": 6.137,
            "pnl_usdt": 954.54,
            "entry_time": "2025-03-18T12:00:00Z",
            "exit_time": "2025-03-18T23:12:00Z",
            "duration_hours": 11.2,
            "signal_score": 72.9,
            "signal_type": "breakout",
            "timeframe": "4h",
            "stop_loss_pct": 3.57,
            "take_profit_pct": 9.45,
            "tags": [
                "risk_managed"
            ]
        },
        ...
    ]
}
```

## 3. Risk and Sizing Endpoints

### 3.1 Risk Gate Status (`GET /risk-gate`)

Checks the current risk gate status, which controls whether new trades can be opened based on drawdown limits, volatility thresholds, and market conditions.

**Response Structure:**
```json
{
    "checked_at": "2026-04-05T22:22:21.264030Z",
    "gate_status": "OPEN",
    "trading_allowed": true,
    "gate_version": "v2.4.1",
    "checks": {
        "daily_drawdown": {
            "status": "PASS",
            "current_pct": -1.2,
            "limit_pct": -5.0,
            "message": "Daily drawdown within acceptable range."
        },
        "weekly_drawdown": {
            "status": "PASS",
            "current_pct": -3.1,
            "limit_pct": -10.0,
            "message": "Weekly drawdown within acceptable range."
        },
        "max_open_positions": { ... },
        "portfolio_heat": { ... },
        "volatility_regime": { ... },
        "consecutive_losses": { ... },
        "news_blackout": { ... },
        "exchange_connectivity": { ... }
    },
    "active_restrictions": [],
    "risk_score": 18,
    "risk_level": "LOW",
    "recommended_position_size_multiplier": 1.0,
    "notes": "All risk checks passed. Normal trading operations permitted."
}
```

### 3.2 Position Sizing (`GET /position-size`)

Calculates optimal position size based on account balance, risk tolerance, stop-loss distance, and leverage. It provides both fixed-fractional and Kelly Criterion estimates.

**Query Parameters:**
*   `symbol` (optional, string, default: "BTCUSDT"): The trading symbol.
*   `account_balance_usdt` (optional, float, default: 10000.0): Total account balance in USDT.
*   `risk_pct` (optional, float, default: 1.0): Percentage of account balance to risk per trade.
*   `stop_loss_pct` (optional, float, default: 2.0): Stop-loss distance as a percentage.
*   `leverage` (optional, integer, default: 1): Leverage multiplier.

**Response Structure:**
```json
{
    "calculated_at": "2026-04-05T22:22:21.296863Z",
    "inputs": {
        "symbol": "BTCUSDT",
        "account_balance_usdt": 10000.0,
        "risk_pct": 1.0,
        "stop_loss_pct": 2.0,
        "leverage": 1
    },
    "market_data": {
        "current_price_usdt": 4681.2668,
        "symbol": "BTCUSDT"
    },
    "position_sizing": {
        "method": "fixed_fractional",
        "risk_amount_usdt": 100.0,
        "position_value_usdt": 5000.0,
        "position_value_with_leverage_usdt": 5000.0,
        "quantity": 1.068087,
        "max_position_pct_of_account": 50.0
    },
    "kelly_criterion": {
        "full_kelly_pct": 44.32,
        "half_kelly_pct": 22.16,
        "recommended_fraction": "half_kelly",
        "half_kelly_position_usdt": 2216.0
    },
    "risk_checks": {
        "within_max_position_limit": false,
        "within_portfolio_heat_limit": true,
        "leverage_approved": true
    },
    "recommendation": {
        "approved": true,
        "suggested_quantity": 1.068087,
        "suggested_position_usdt": 5000.0,
        "notes": "Position sizing approved. Risk per trade: $100.00 USDT (1.0% of account)."
    }
}
```

## 4. Market Analysis Endpoints

### 4.1 Market Regime (`GET /regime/{symbol}`)

Detects the current market regime for a given symbol, returning regime classification, trend direction, strength metrics, and recommended strategy adjustments.

**Path Parameters:**
*   `symbol` (required, string): The trading symbol (e.g., "BTCUSDT").

**Response Structure (Example for BTCUSDT):**
```json
{
    "analyzed_at": "2026-04-05T22:22:21.330789Z",
    "symbol": "BTCUSDT",
    "regime": "TRENDING_UP",
    "regime_confidence": 0.633,
    "regime_duration_hours": 65.8,
    "indicators": {
        "adx": 53.5,
        "adx_interpretation": "strong_trend",
        "atr_pct": 1.09,
        "trend_strength": 0.725,
        "price_vs_200ma_pct": -5.8,
        "price_vs_50ma_pct": -8.8,
        "bb_width_pct": 2.07,
        "bb_squeeze": true,
        "volume_trend": "neutral",
        "current_price_usdt": 4702.6396
    },
    "strategy_guidance": {
        "preferred_strategies": [
            "momentum",
            "breakout",
            "trend_following"
        ],
        "avoid": [
            "mean_reversion",
            "counter_trend"
        ],
        "direction_bias": "LONG",
        "position_size_multiplier": 1.2
    },
    "risk_adjustment": {
        "recommended_stop_loss_multiplier": 1.11,
        "max_leverage_recommended": 10,
        "reduce_position_size": false
    },
    "notes": "Regime detected as TRENDING_UP for BTCUSDT. Strategy guidance updated accordingly."
}
```

## Conclusion

The CoinScopeAI Trading Engine provides a robust set of endpoints for automated trading systems. It covers the entire lifecycle from signal generation (`/scan`) and market context analysis (`/regime/{symbol}`) to risk management (`/risk-gate`, `/position-size`) and performance tracking (`/performance`, `/journal`). The API is well-structured, returning comprehensive JSON responses with detailed metadata and actionable recommendations.

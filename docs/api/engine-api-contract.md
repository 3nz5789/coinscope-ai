# CoinScopeAI Engine API — Contract Reference

**Version:** 2.0.0
**Status:** current — P0 validation phase
**Base URL:** `https://api.coinscope.ai` (prod) · `http://localhost:8001` (local)
**Auth:** none (private VPS, not public-facing during P0)
**Content-Type:** `application/json` on all POST bodies and all responses

---

## Conventions

### Versioning

The API is at `version: "2.0.0"` (declared in FastAPI app metadata).
No URL-path versioning (`/v1/`, `/v2/`) is used today — the version is
surfaced in `GET /health` as `"version": "2.0.0"`. Breaking changes will
increment the minor version and be logged in `CHANGELOG.md` with a
`api-contract` label.

### Error schema

Every error response follows this shape — no exceptions:

```json
{
  "detail": "<human-readable message>"
}
```

HTTP status codes used:

| Code | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request — invalid parameters, Binance rejected the order |
| `403` | Forbidden — `TESTNET_MODE=false` or other safety refusal |
| `404` | Not found — symbol unknown, job ID not found, no open position |
| `422` | Unprocessable entity — FastAPI request body validation failed |
| `423` | Locked — circuit breaker is open; reset it before retrying |
| `500` | Internal server error — engine-side exception (detail contains type + message) |

### Timestamps

All `timestamp` fields are Unix epoch seconds (float). All `opened_at` /
`closed_at` / `entry_time` / `exit_time` fields are ISO 8601 UTC strings.

### Testnet guard

Endpoints that place or cancel orders enforce `TESTNET_MODE=true` at the
application layer. If the env var is `false`, the endpoint returns:

```json
{
  "detail": "Refusing to place orders: TESTNET_MODE=false. Live trading requires an explicit ALLOW_LIVE_TRADING flag."
}
```
HTTP `403`.

---

## Tag Groups

| Tag | Purpose |
|---|---|
| System | Liveness, config |
| Account | Live Binance Futures account state |
| Orders | Order placement, cancellation, brackets |
| Autotrade | Autonomous scan → trade loop |
| Signals | Scanner output, on-demand scan |
| Risk | Positions, exposure, circuit breaker, sizing |
| Intelligence | Regime, sentiment, anomaly, correlation |
| Journal | Trade log, performance stats, equity curve |
| Backtest | Async backtest jobs |
| Decisions | Gate decision audit log |
| Historical | 90-day local kline store |
| Scale | Scale-up profile management |
| Validation | Walk-forward validation |

---

## System

### `GET /health`

Liveness probe. Returns 200 if the process is alive.

**Response 200**
```json
{
  "status": "ok",
  "version": "2.0.0",
  "testnet": true,
  "timestamp": 1747079400.123
}
```

**Error responses:** none — if the process is dead there is no response.

---

### `GET /config`

Safe (non-secret) runtime configuration.

**Response 200**
```json
{
  "testnet_mode": true,
  "environment": "development",
  "scan_pairs": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "TAOUSDT"],
  "scan_interval_s": 60,
  "min_confluence_score": 55.0,
  "risk_per_trade_pct": 1.0,
  "max_leverage": 10,
  "max_open_positions": 5,
  "max_position_size_pct": 5.0,
  "max_total_exposure_pct": 80.0,
  "max_daily_loss_pct": 5.0
}
```

**Invariant:** `max_leverage` must always be `10`, `max_open_positions` must
always be `5`, `max_total_exposure_pct` must always be `80.0`,
`max_daily_loss_pct` must always be `5.0` during P0.
If any of these differ, COI-68 (VPS .env patch) has not been applied.

---

## Account

### `GET /account`

Live Binance Futures Demo account summary (refreshed every 10s).

**Response 200**
```json
{
  "updated_at": 1747079390.5,
  "age_s": 9.6,
  "error": null,
  "can_trade": true,
  "fee_tier": 0,
  "total_wallet_balance": 9842.17,
  "total_margin_balance": 9901.34,
  "available_balance": 9401.34,
  "total_unrealized_pnl": 59.17,
  "total_position_notional": 500.0,
  "total_maint_margin": 2.5,
  "position_count": 1
}
```

**Error shape when sync fails:**
```json
{
  "updated_at": 1747079300.0,
  "age_s": 90.0,
  "error": "BinanceRESTError: -1021 Timestamp outside recvWindow",
  "can_trade": false,
  ...
}
```

---

### `GET /account/positions`

Open positions (non-zero `positionAmt` only).

**Response 200**
```json
{
  "updated_at": 1747079390.5,
  "error": null,
  "count": 1,
  "positions": [
    {
      "symbol": "BTCUSDT",
      "position_side": "BOTH",
      "position_amt": 0.01,
      "side": "LONG",
      "entry_price": 62500.0,
      "mark_price": 63100.0,
      "liquidation_price": 56250.0,
      "leverage": 5,
      "margin_type": "cross",
      "isolated_margin": 0.0,
      "unrealized_pnl": 6.0,
      "notional": 631.0,
      "update_time": 1747079380000
    }
  ]
}
```

---

### `POST /account/sync`

Force an immediate account refresh (normally every 10s).

**Response 200**
```json
{
  "updated_at": 1747079410.2,
  "error": null,
  "positions": 1
}
```

---

## Orders

### `POST /orders`

Place a MARKET or LIMIT order on Binance Futures Demo.

**Request body**
```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "type": "MARKET",
  "qty": 0.01,
  "price": null,
  "tif": "GTC",
  "reduce_only": false,
  "leverage": 5,
  "client_id": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `symbol` | string | yes | Binance Futures format: `BTCUSDT` |
| `side` | string | yes | `"BUY"` or `"SELL"` |
| `type` | string | yes | `"MARKET"` or `"LIMIT"` |
| `qty` | float | yes | Base-asset quantity (rounded to stepSize) |
| `price` | float | LIMIT only | Required if `type="LIMIT"` |
| `tif` | string | no | `"GTC"` (default) / `"IOC"` / `"FOK"` — LIMIT only |
| `reduce_only` | bool | no | Default `false` |
| `leverage` | int | no | 1–10; changes leverage before order if set |
| `client_id` | string | no | Idempotency token; auto-generated if omitted |

**Response 200 (MARKET)**
```json
{
  "order": {
    "orderId": 4611686018427439000,
    "symbol": "BTCUSDT",
    "status": "FILLED",
    "side": "BUY",
    "type": "MARKET",
    "avgPrice": "62510.50",
    "origQty": "0.010",
    "executedQty": "0.010",
    "updateTime": 1747079412345
  },
  "client_id": "cs-3a7f2c1b9d4e",
  "leverage_change": {
    "symbol": "BTCUSDT",
    "leverage": 5,
    "maxNotionalValue": "1000000"
  },
  "bracket": null,
  "source": "manual",
  "journal_id": "jrn-a1b2c3d4",
  "slippage_bps": 2.1
}
```

**Error responses**

| Code | Condition | `detail` example |
|---|---|---|
| `400` | `type` not MARKET or LIMIT | `"type must be MARKET or LIMIT, got 'STOP'"` |
| `400` | `qty` ≤ 0 | `"qty must be > 0, got 0"` |
| `400` | LIMIT missing price | `"LIMIT order requires a price"` |
| `400` | leverage out of range | `"leverage 15 out of [1..10]"` |
| `400` | Binance rejected | `"Binance rejected order: -2019 Margin is insufficient."` |
| `403` | `TESTNET_MODE=false` | `"Refusing to place orders: TESTNET_MODE=false..."` |
| `423` | Circuit breaker open | `"Circuit breaker is OPEN. Reset it first."` |

---

### `POST /orders/close`

Market-close an open position (reduceOnly).

**Request body**
```json
{
  "symbol": "BTCUSDT",
  "qty": null
}
```

`qty` is optional — omit to close the full position.

**Response 200**
```json
{
  "order": {
    "orderId": 4611686018427440000,
    "symbol": "BTCUSDT",
    "status": "FILLED",
    "side": "SELL",
    "avgPrice": "63100.0"
  },
  "client_id": "close-9e1f3b2c7a8d",
  "closed_qty": 0.01,
  "was_side": "LONG"
}
```

**Error responses**

| Code | Condition |
|---|---|
| `404` | No open position on symbol |
| `400` | Binance rejected |
| `403` | `TESTNET_MODE=false` |
| `423` | Circuit breaker open |

---

### `POST /orders/bracket`

Attach SL and/or TP to an existing position via Binance Algo Order API.

**Request body**
```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "stop_price": 61000.0,
  "tp_price": 65000.0,
  "qty": null
}
```

`qty` null → `closePosition=true` (full position). Set to a float to specify
partial quantity.

**Response 200**
```json
{
  "stop_loss": {
    "algoId": 12345678,
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "STOP_MARKET",
    "triggerPrice": "61000.00",
    "status": "WORKING"
  },
  "take_profit": {
    "algoId": 12345679,
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "TAKE_PROFIT_MARKET",
    "triggerPrice": "65000.00",
    "status": "WORKING"
  }
}
```

**Error within bracket field** (not HTTP error — the other leg may have succeeded):
```json
{
  "stop_loss": {"error": "BinanceRESTError: -2021 Order would immediately trigger."},
  "take_profit": {"algoId": 12345679, ...}
}
```

---

### `GET /orders/open`

Open regular orders, optionally filtered by symbol.

**Query params:** `symbol` (optional)

**Response 200**
```json
{
  "orders": [...],
  "count": 2
}
```

---

### `DELETE /orders/{order_id}`

Cancel a single order. `symbol` is required as a query param.

**Response 200:** Binance cancel response (raw).

**Error:** `400` if Binance rejects.

---

### `DELETE /orders`

Cancel all open orders on a symbol.

**Query params:** `symbol` (required)

---

## Signals

### `GET /signals`

Most recently cached signals from the background scan loop.

**Response 200**
```json
{
  "signals": [
    {
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "score": 72.5,
      "strength": "STRONG",
      "scanners": ["volume", "pattern", "funding_rate"],
      "reasons": ["RSI oversold recovery", "OI increasing", "Funding negative"],
      "actionable": true,
      "setup": {
        "entry": 62500.0,
        "stop_loss": 61250.0,
        "tp1": 63750.0,
        "tp2": 65000.0,
        "tp3": 66250.0,
        "rr_ratio": 2.0,
        "valid": true,
        "reason": null
      },
      "regime": "trending",
      "htf_trend": "bull",
      "htf_agrees": true,
      "anomaly": {
        "detected": false,
        "severity": "none",
        "types": []
      },
      "indicators": {
        "rsi": 42.1,
        "adx": 28.5,
        "trend": "bullish",
        "momentum": "positive",
        "volatility": "normal"
      },
      "scanned_at": 1747079380.1
    }
  ],
  "count": 6,
  "actionable": 2,
  "last_scan_at": 1747079380.1,
  "age_s": 20.5,
  "loop": {
    "running": true,
    "scans_total": 142,
    "scans_failed": 0,
    "last_scan_at": 1747079380.1,
    "next_scan_at": 1747079440.1,
    "seconds_to_next": 39.6,
    "last_duration_ms": 4820,
    "last_signals": 6,
    "last_actionable": 2,
    "last_error": null,
    "interval_s": 60
  }
}
```

**Signal `score` range:** 0–100. Actionable threshold: `min_confluence_score`
(default 55.0, visible in `/config`).

---

### `POST /scan`

Trigger an immediate scan of specified pairs.

**Request body**
```json
{
  "pairs": ["BTCUSDT", "ETHUSDT"],
  "timeframe": "1h",
  "limit": 100
}
```

**Response 200**
```json
{
  "scanned": 2,
  "actionable": 1,
  "signals": [...],
  "timestamp": 1747079420.3
}
```

---

## Risk

### `GET /circuit-breaker`

Current circuit breaker state.

**Response 200**
```json
{
  "state": "CLOSED",
  "trip_count": 2,
  "last_trip": "<TripEvent reason='Daily loss -5.1%' at='14:22:33'>",
  "max_daily_loss_pct": 5.0,
  "max_drawdown_pct": 10.0,
  "max_consec_losses": 5,
  "timestamp": 1747079420.0
}
```

`state` is one of: `"CLOSED"` (trading allowed) · `"OPEN"` (halted) · `"COOLDOWN"`.

---

### `POST /circuit-breaker/trip`

Manually halt trading. Also cancels all working orders and SL/TP brackets.

**Request body**
```json
{
  "reason": "Operator kill switch — unusual market conditions"
}
```

**Response 200**
```json
{
  "message": "Circuit breaker tripped.",
  "reason": "Operator kill switch — unusual market conditions",
  "state": "OPEN",
  "cancellations": {
    "regular": [{"symbol": "BTCUSDT", "result": {...}}],
    "algo": [{"symbol": "BTCUSDT", "algoId": 12345678}],
    "errors": []
  }
}
```

---

### `POST /circuit-breaker/reset`

Reset a tripped breaker. Read `/journal` and verify a real breach
caused the trip before calling this.

**Response 200**
```json
{
  "message": "Circuit breaker reset.",
  "state": "CLOSED"
}
```

If already closed:
```json
{
  "message": "Circuit breaker is already closed.",
  "state": "CLOSED"
}
```

---

### `GET /exposure`

Portfolio exposure summary.

**Response 200**
```json
{
  "balance": 9842.17,
  "position_count": 1,
  "total_notional": 631.0,
  "total_exposure_pct": 6.41,
  "unrealised_pnl": 6.0,
  "realised_pnl": 42.0,
  "daily_pnl": 42.0,
  "daily_loss_pct": -0.0043,
  "is_over_exposed": false,
  "max_total_exposure_pct": 80.0
}
```

**Invariant:** `total_exposure_pct` must never exceed `max_total_exposure_pct`
(80.0). If it does, `ExposureHigh` alert fires and no new positions should
be opened.

---

### `GET /position-size`

Kelly-fractional position sizing for a given setup.

**Query params:**
- `symbol` (default `BTCUSDT`)
- `entry` (default `65000.0`) — proposed entry price
- `stop_loss` (default `64000.0`)
- `account_balance` (default `10000.0`)
- `win_rate` (optional, 0–1) — enables Kelly criterion
- `avg_rr` (optional, > 0) — enables Kelly criterion

**Response 200**
```json
{
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "qty": 0.016,
  "notional": 1000.0,
  "risk_usdt": 16.0,
  "margin_usdt": 100.0,
  "risk_pct": 0.1627,
  "leverage": 5,
  "method": "FIXED",
  "valid": true,
  "reason": null,
  "timestamp": 1747079420.0
}
```

**Response 200 (invalid — non-actionable)**
```json
{
  "symbol": "BTCUSDT",
  "direction": "LONG",
  "qty": 0,
  "notional": 0,
  "risk_usdt": 0,
  "margin_usdt": 0,
  "risk_pct": 0,
  "leverage": 0,
  "method": "FIXED",
  "valid": false,
  "reason": "SL distance is zero",
  "timestamp": 1747079420.0
}
```

---

## Intelligence

### `GET /regime`

Market regime for a symbol (v3 ML ensemble, HMM fallback).

**Query params:** `symbol`, `timeframe`, `limit`

**Response 200 (v3 ML)**
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "regime": "Trending",
  "confidence": 0.87,
  "probabilities": {
    "Trending": 0.87,
    "Mean-Reverting": 0.08,
    "Volatile": 0.03,
    "Quiet": 0.02
  },
  "model": "v3_ensemble_rf_xgb",
  "candles_used": 150,
  "timestamp": 1747079420.0
}
```

**Response 200 (HMM fallback)**
```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "regime": "bull",
  "confidence": 0.72,
  "state_probs": [0.72, 0.18, 0.10],
  "model": "hmm_fallback",
  "candles_used": 150,
  "timestamp": 1747079420.0
}
```

`regime` values (v3): `"Trending"` · `"Mean-Reverting"` · `"Volatile"` · `"Quiet"`
`regime` values (HMM): `"bull"` · `"bear"` · `"chop"`

**Error:** `500` with `detail` containing the exception type and message.

---

### `GET /sentiment`

Composite sentiment score for a symbol.

**Response 200**
```json
{
  "symbol": "BTCUSDT",
  "score": 62.5,
  "label": "bullish",
  "components": {
    "funding": 0.3,
    "oi_change": 0.0
  },
  "funding_rate": -0.0012,
  "timestamp": 1747079420.0
}
```

---

### `GET /correlation`

Pairwise Pearson correlation matrix for a comma-separated symbol list.

**Query params:** `symbols` (default `BTCUSDT,ETHUSDT,SOLUSDT`), `timeframe`, `limit`

**Response 200**
```json
{
  "matrix": {
    "BTCUSDT": {"BTCUSDT": 1.0, "ETHUSDT": 0.91, "SOLUSDT": 0.84},
    "ETHUSDT": {"BTCUSDT": 0.91, "ETHUSDT": 1.0, "SOLUSDT": 0.88},
    "SOLUSDT": {"BTCUSDT": 0.84, "ETHUSDT": 0.88, "SOLUSDT": 1.0}
  },
  "high_correlation_pairs": [
    {"a": "BTCUSDT", "b": "ETHUSDT", "r": 0.91},
    {"a": "ETHUSDT", "b": "SOLUSDT", "r": 0.88}
  ],
  "threshold": 0.8,
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "timestamp": 1747079420.0
}
```

---

## Journal

### `GET /journal`

Trade log entries, newest first.

**Query params:** `days` (1–365, default 30), `include_open` (bool, default true)

**Response 200**
```json
{
  "entries": [
    {
      "id": "jrn-a1b2c3d4",
      "symbol": "BTCUSDT",
      "side": "LONG",
      "entry_price": 62510.5,
      "exit_price": 63100.0,
      "qty": 0.01,
      "leverage": 5,
      "pnl": 5.895,
      "pnl_pct": 0.9431,
      "entry_time": "2026-05-12T14:30:00",
      "exit_time": "2026-05-12T16:45:00",
      "duration_hours": 2.25,
      "strategy": "auto",
      "regime": "Trending",
      "reasons": ["RSI oversold recovery", "OI increasing"],
      "status": "CLOSED",
      "signal_score": 72.5,
      "kelly_usd": 625.1,
      "strength": "STRONG",
      "htf_trend": "bull",
      "entry_order_id": 4611686018427439000,
      "slippage_bps": 2.1,
      "sl_price": 61250.0,
      "tp_price": 65000.0,
      "exit_trigger": "tp_hit",
      "closed_by": "reconcile_loop"
    }
  ],
  "count": 1,
  "closed": 1,
  "open": 0,
  "days": 30,
  "timestamp": 1747079420.0
}
```

---

### `GET /journal/{entry_id}/trace`

Full provenance trace for one trade: entry details + surrounding gate
decisions + live algo orders.

**Response 200**
```json
{
  "entry": {
    "id": "jrn-a1b2c3d4",
    "symbol": "BTCUSDT",
    "side": "BUY",
    "regime": "Trending",
    "entry_price": 62510.5,
    "quantity": 0.01,
    "signal_score": 72.5,
    "scanner_hits": [{"name": "volume"}, {"name": "pattern"}],
    "indicators_at_entry": {"rsi": 42.1, "adx": 28.5},
    "entry_client_id": "auto-3a7f2c1b9d4e",
    "entry_order_id": 4611686018427439000,
    "entry_submit_ms": 1747069800000,
    "entry_fill_ms":   1747069800412,
    "slippage_bps": 2.1,
    "sl_price": 61250.0,
    "tp_price": 65000.0,
    "sl_algo_id": 12345678,
    "tp_algo_id": 12345679,
    "exit_trigger": "tp_hit",
    "status": "CLOSED"
  },
  "decisions": [
    {"ts": 1747069795.0, "symbol": "BTCUSDT", "action": "signal", "signal_score": 72.5},
    {"ts": 1747069800.0, "symbol": "BTCUSDT", "action": "open", "side": "BUY", "entry": 62510.5}
  ],
  "algo_orders": [],
  "window": {
    "lo_ts": 1747069500.0,
    "hi_ts": 1747076700.0,
    "span_s": 7200.0
  }
}
```

**Error:** `404` if `entry_id` not found.

---

### `GET /performance`

Aggregate P&L stats.

**Response 200**
```json
{
  "total_trades": 14,
  "win_rate": 0.643,
  "profit_factor": 1.87,
  "total_pnl_usdt": 127.42,
  "max_drawdown_pct": 3.1,
  "sharpe_ratio": 1.22,
  "avg_win_pct": 1.41,
  "avg_loss_pct": -0.75,
  "equity_curve": [
    {"ts": "2026-05-01T00:00:00", "equity": 10000.0},
    {"ts": "2026-05-12T16:00:00", "equity": 10127.42}
  ],
  "scale_profile": {
    "current": "S0_SEED",
    "account_usd": 10000.0,
    "position_pct": 1.0,
    "next_profile": "S1_STARTER",
    "next_requires": {"trades": 100, "sharpe": 0.85}
  },
  "timestamp": 1747079420.0
}
```

---

## Decisions (Gate Audit Log)

### `GET /decisions`

Recent gate verdicts (accepts, rejects, skips), newest first.

**Query params:** `symbol` (optional), `action` (optional), `limit` (default 100)

**Response 200**
```json
{
  "decisions": [
    {
      "ts": 1747079380.0,
      "symbol": "BTCUSDT",
      "direction": "LONG",
      "action": "open",
      "reason": "scan tick",
      "signal_score": 72.5,
      "order_id": 4611686018427439000
    },
    {
      "ts": 1747079320.0,
      "symbol": "ETHUSDT",
      "direction": "SHORT",
      "action": "reject",
      "reason": "MTF: SHORT blocked — 4h is bull",
      "signal_score": 61.0
    }
  ],
  "count": 100
}
```

`action` values: `"signal"` · `"open"` · `"reject"` · `"skip"` · `"close"` ·
`"enabled"` · `"disabled"` · `"breaker_trip"` · `"config"` · `"unpause"`

---

## Backtest

### `POST /backtest/run`

Kick off an async backtest. Returns a `job_id` immediately.

**Request body (all fields optional — defaults shown)**
```json
{
  "pairs": ["BTCUSDT", "ETHUSDT"],
  "timeframe": "1h",
  "lookback_days": 30,
  "initial_balance": 10000.0,
  "risk_per_trade_pct": 1.0,
  "min_confluence_score": 60.0,
  "commission_pct": 0.04,
  "slippage_pct": 0.01,
  "atr_sl_mult": 1.5,
  "atr_tp1_mult": 1.5,
  "atr_tp2_mult": 3.0,
  "atr_tp3_mult": 4.5,
  "allowed_directions": "BOTH",
  "mtf_filter_enabled": false
}
```

**Response 200**
```json
{
  "job_id": "bt-4f8e1a2b3c",
  "status": "queued"
}
```

---

### `GET /backtest/jobs/{job_id}`

Poll for backtest results.

**Response 200 (running)**
```json
{
  "job_id": "bt-4f8e1a2b3c",
  "status": "running",
  "created_at": 1747079400.0,
  "started_at": 1747079401.0,
  "finished_at": null,
  "results": null,
  "error": null
}
```

**Response 200 (done)**
```json
{
  "job_id": "bt-4f8e1a2b3c",
  "status": "done",
  "results": {
    "summary": {
      "total_trades": 47,
      "win_rate": 0.617,
      "profit_factor": 1.72,
      "total_pnl_usdt": 214.50,
      "final_balance": 10214.50,
      "total_return_pct": 2.145,
      "max_drawdown_pct": 4.2,
      "sharpe_ratio": 1.14
    },
    "equity_curve": [...],
    "trades": [...]
  },
  "error": null
}
```

**Response 200 (error)**
```json
{
  "job_id": "bt-4f8e1a2b3c",
  "status": "error",
  "error": "ValueError: insufficient candle data for TAOUSDT",
  "results": null
}
```

**Error:** `404` if `job_id` not found.

---

## Prices

### `GET /prices`

Live mark prices from the Binance Futures WS feed.

**Response 200**
```json
{
  "feed": {
    "connected": true,
    "reconnects": 0,
    "last_msg_at": 1747079419.8,
    "last_msg_age_s": 0.2,
    "error": null
  },
  "prices": [
    {
      "symbol": "BTCUSDT",
      "mark_price": 63100.0,
      "index_price": 63095.0,
      "funding_rate": -0.0012,
      "next_funding_ts": 1747094400000,
      "ts": 1747079419.8,
      "age_s": 0.2
    }
  ],
  "count": 6
}
```

**Stale data signal:** if `feed.connected` is `false` or `last_msg_age_s` > 60,
prices are stale and should not be used for sizing decisions.

---

## Known Contract Gaps (P1 items)

| Gap | Impact | When |
|---|---|---|
| No `X-Request-ID` header for tracing | Hard to correlate engine logs with API calls | P1 |
| No rate limiting on public endpoints | Could be hammered by dashboard polling | P1 |
| `GET /regime` returns different `regime` label format for v3 vs HMM | Dashboard must handle both | P1 — normalise to v3 labels |
| Bracket errors embedded in response body (not HTTP error codes) | Clients must inspect `stop_loss.error` | P1 |
| `/performance` equity_curve can be empty list on fresh install | Dashboard must handle empty array | P1 |
| No pagination on `GET /journal` | Large histories will slow response | P2 |
| `GET /decisions` returns raw internal dict shape | Not a stable contract | P2 |

---

*Last updated: 2026-05-12 | Version: 2.0.0 | Applies to: P0 validation phase*

# Backend Endpoints

**Status:** current
**Audience:** developers and dashboard integrators
**Related:** [`api-overview.md`](api-overview.md), [`../backend/backend-overview.md`](../backend/backend-overview.md), [`../ops/stripe-billing.md`](../ops/stripe-billing.md)

Every endpoint the engine serves. Conventions (base URL, auth, error envelope) are defined in [`api-overview.md`](api-overview.md) — this doc is the per-endpoint reference.

All endpoints require the bearer token (`Authorization: Bearer <API_AUTH_TOKEN>`) unless explicitly marked **open** or **Stripe-signed**. Endpoints marked **entitled** additionally require an active billing entitlement.

## Health and readiness

### `GET /health` — **open**

Liveness probe. Always returns `200` if the process is running.

**Response:**

```json
{ "status": "ok", "version": "0.y.z", "build": "<git-sha>" }
```

### `GET /ready` — **open**

Readiness probe. Returns `200` when Redis, the journal, and the Binance adapter are all healthy. Returns `503` with `engine_degraded` otherwise.

**Response (ready):**

```json
{
  "status": "ready",
  "checks": {
    "redis": "ok",
    "journal": "ok",
    "binance": "ok"
  }
}
```

## Scanning and signal

### `GET /scan`

Current ranked list of candidates from the most recent scan cycle.

**Query parameters:**

| Name | Type | Default | Purpose |
| --- | --- | --- | --- |
| `limit` | int | `20` | Max candidates returned. |
| `min_score` | int | `0` | Filter below this confluence score. |
| `side` | string | `any` | `long`, `short`, or `any`. |

**Response:**

```json
{
  "as_of": "2026-04-18T12:34:56Z",
  "regime": { "hmm": "chop", "v3": "Mean-Reverting" },
  "candidates": [
    {
      "symbol": "BTCUSDT",
      "side": "long",
      "score": 10,
      "factors": { "rsi": 2, "ema": 2, "atr": 1, "volume": 2, "cvd": 1, "timing": 2 }
    }
  ]
}
```

### `GET /regime/{symbol}`

Current regime labels for a specific symbol, from both detectors.

**Path parameters:**

- `symbol` — a supported USDT-M perpetual symbol (e.g., `BTCUSDT`).

**Response:**

```json
{
  "symbol": "BTCUSDT",
  "hmm": { "label": "chop", "confidence": 0.71, "as_of": "2026-04-18T12:30:00Z" },
  "v3":  { "label": "Mean-Reverting", "confidence": 0.63, "as_of": "2026-04-18T12:30:00Z" }
}
```

## Risk and sizing

### `GET /risk-gate`

Snapshot of the current risk-gate state and the last N decisions.

**Query parameters:**

| Name | Type | Default | Purpose |
| --- | --- | --- | --- |
| `limit` | int | `50` | Recent decisions to include. |

**Response:**

```json
{
  "breaker": { "state": "ok", "tripped_at": null, "resets_at": null },
  "kill_switch": { "engaged": false, "engaged_at": null },
  "heat_pct": 42.1,
  "open_positions": 2,
  "daily_pnl_pct": -1.3,
  "recent_decisions": [
    {
      "at": "2026-04-18T12:34:20Z",
      "symbol": "ETHUSDT",
      "outcome": "rejected",
      "reason": "heat_cap_exceeded",
      "details": { "heat_pct_after": 82.4 }
    }
  ]
}
```

### `GET /position-size`

Preview Kelly sizing for a hypothetical candidate. Does not place any order.

**Query parameters:**

| Name | Type | Required | Purpose |
| --- | --- | --- | --- |
| `symbol` | string | yes | USDT-M perpetual symbol. |
| `side` | string | yes | `long` or `short`. |
| `expected_edge_pct` | float | yes | Estimated edge in percent. |
| `volatility_pct` | float | yes | Estimated volatility in percent. |

**Response:**

```json
{
  "symbol": "BTCUSDT",
  "side": "long",
  "kelly_full": 0.12,
  "kelly_fractional": 0.03,
  "size_after_cap_pct": 0.02,
  "regime_multiplier": 0.5,
  "final_size_pct": 0.01,
  "final_size_base": 0.001
}
```

## Performance and journal

### `GET /performance`

Rolling performance summary. Used by the dashboard's KPI cards.

**Query parameters:**

| Name | Type | Default | Purpose |
| --- | --- | --- | --- |
| `window` | string | `7d` | One of `24h`, `7d`, `30d`, `all`. |

**Response:**

```json
{
  "window": "7d",
  "trades": 41,
  "wins": 22,
  "losses": 19,
  "win_rate_pct": 53.7,
  "pnl_pct": 2.9,
  "max_drawdown_pct": 3.1,
  "best_trade_pct": 1.4,
  "worst_trade_pct": -1.1,
  "avg_trade_pct": 0.07
}
```

### `GET /performance/daily`

Day-by-day P&L for charting.

**Query parameters:**

| Name | Type | Default | Purpose |
| --- | --- | --- | --- |
| `days` | int | `30` | Days to include. |

**Response:**

```json
{
  "days": [
    { "date": "2026-04-11", "pnl_pct": 0.41, "trades": 6 },
    { "date": "2026-04-12", "pnl_pct": -0.23, "trades": 4 }
  ]
}
```

### `GET /journal`

Recent journal events, newest first. Filterable.

**Query parameters:**

| Name | Type | Default | Purpose |
| --- | --- | --- | --- |
| `limit` | int | `100` | Max events. |
| `since` | ISO-8601 timestamp | none | Events at or after this time. |
| `event_type` | string | any | `gate_decision`, `sized`, `submitted`, `filled`, `cancelled`, `pnl_update`, `regime_flip`, `breaker_trip`, `kill_switch`, `billing`. |
| `symbol` | string | any | Filter by symbol. |

**Response:**

```json
{
  "events": [
    {
      "at": "2026-04-18T12:34:56.789123Z",
      "event_type": "filled",
      "symbol": "BTCUSDT",
      "payload": { "qty": 0.001, "price": 64250.1, "side": "long", "client_order_id": "cs-..." }
    }
  ]
}
```

## Position management

### `GET /positions`

Currently open positions as reflected in the journal, reconciled against Binance.

**Response:**

```json
{
  "positions": [
    {
      "symbol": "BTCUSDT",
      "side": "long",
      "entry_price": 64100.2,
      "qty": 0.001,
      "unrealized_pnl_pct": 0.23,
      "stop": 63800.0,
      "take_profit": 64700.0,
      "opened_at": "2026-04-18T11:05:00Z"
    }
  ]
}
```

### `GET /orders`

Working orders (not yet filled or cancelled).

## Operator controls

### `POST /kill-switch` — **operator only**

Toggle the manual kill switch. Engaging it rejects all new entries and cancels working orders. Existing positions are **not** unwound automatically.

**Request:**

```json
{ "engage": true, "reason": "pre-release smoke test" }
```

**Response:**

```json
{ "engaged": true, "engaged_at": "2026-04-18T12:34:56Z" }
```

### `POST /circuit-breaker/reset` — **operator only**

Manually reset a tripped circuit breaker without waiting for the timed reset.

**Request:**

```json
{ "reason": "false trip, spurious market data gap" }
```

## Market scanner utilities

### `GET /symbols`

The current scanner universe.

**Response:**

```json
{
  "universe": "top-50-by-volume",
  "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "..."]
}
```

### `GET /depth/{symbol}` — **entitled**

Current depth snapshot for a symbol. Useful for dashboard tooltips and debugging slippage estimates.

## Billing — Stripe

### `POST /billing/webhook` — **Stripe-signed**

Stripe webhook consumer. Validates the `Stripe-Signature` header; the bearer token is not used.

**Request:** Stripe event JSON (passed through to the handler).

**Response:**

```json
{ "received": true }
```

Event types handled: `customer.created`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`. See [`../ops/stripe-billing.md`](../ops/stripe-billing.md).

### `GET /billing/me` — bearer token

Current caller's subscription and entitlement state.

**Response:**

```json
{
  "customer_id": "cus_...",
  "status": "active",
  "tier": "pro",
  "entitlements": ["dashboard", "depth", "premium_scan"],
  "current_period_end": "2026-05-12T00:00:00Z"
}
```

### `POST /billing/portal` — bearer token

Creates a Stripe Billing Portal session for the caller.

**Response:**

```json
{ "url": "https://billing.stripe.com/p/session/..." }
```

## Observability

### `GET /metrics` — **open** (optionally token-gated)

Prometheus metrics in the text exposition format. If `METRICS_AUTH_TOKEN` is set, requests must include it as a bearer token.

---

**21 endpoints total** as of 2026-04-18. When adding or removing endpoints, update this doc in the same PR. That's a CI-adjacent expectation from [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

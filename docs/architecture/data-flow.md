# Data Flow

**Status:** current
**Audience:** developers tracing a candle from the exchange to a journal entry
**Related:** [`system-overview.md`](system-overview.md), [`component-map.md`](component-map.md), [`../risk/risk-framework.md`](../risk/risk-framework.md)

How a single tick becomes, at worst, a gate rejection and, at best, an order on Binance testnet. Each step names the component that owns it and what the step actually does.

## The happy path, end to end

```
Binance WS
   │  raw kline / depth / funding / OI message
   ▼
Adapter (binance_*.py)
   │  normalize, timestamp, attach symbol, signal freshness
   ▼
Market data cache (data/)
   │  merge into the per-symbol rolling window
   ▼
Regime detectors (intelligence/)
   │  HMM → {bull, bear, chop}
   │  v3  → {Trending, Mean-Reverting, Volatile, Quiet}
   ▼
Scanner (scanner/ or scanners/)
   │  for each symbol in the universe, request a score
   ▼
Scorer (scorer.py / intelligence/scorer.py)
   │  confluence score 0–12 + factor breakdown + side (long/short)
   ▼
Risk gate (risk_gate.py)
   │  check regime alignment, heat, correlation, daily loss,
   │  circuit breaker, kill switch
   │  if rejected → journal reason, stop
   ▼
Kelly sizer (kelly_position_sizer.py)
   │  compute Kelly fraction → 25% fractional → 2% cap
   │  multiply by regime multiplier (bull 1.0 / chop 0.5 / bear 0.3)
   ▼
Executor (execution/)
   │  pre-trade slippage estimate
   │  submit order(s) to Binance testnet
   │  attach stop + TP (2:1 RR, ATR-based)
   ▼
Fills → Journal (SQLite / Postgres)
   │  every decision, every fill, every P&L update
   ▼
Prometheus metrics + /journal API
   │  the dashboard reads here
   ▼
React dashboard at https://coinscope.ai/ (separate repo)
```

## Step-by-step

### 1. Ingest — Binance → Adapter

**Owner:** `coinscope_trading_engine/binance_*.py`.

Binance pushes messages over WebSocket. The adapter:

- Receives the raw payload.
- Validates the stream name and event type.
- Normalizes numeric fields to `Decimal` or `float` per schema.
- Attaches the local monotonic timestamp.
- Hands the message off to the data cache.

The adapter is also where reconnect-with-backoff lives. Any gap in the stream is journaled as a gap, not silently bridged — downstream components decide whether they can tolerate the gap.

### 2. Cache — Adapter → Data layer

**Owner:** `coinscope_trading_engine/data/`.

Normalized messages are merged into per-symbol rolling windows (klines, depth, funding, OI). The cache enforces that:

- Candle boundaries are exact.
- Missing candles open a gap window that regime detectors and scorers can detect and refuse to act on.
- The oldest data beyond the retention window is evicted deterministically.

Scorer and regime consumers read from the cache, never from the adapter directly.

### 3. Regime — Cache → Detectors

**Owners:** `intelligence/` (HMM) and `intelligence/regime_classifier_v3.py` (v3).

Both detectors run on a cadence (typically every few minutes, configurable via `REGIME_REFRESH_*` env vars). They read the cache, run inference against their saved artifacts, and publish a current label to shared state.

**Why two systems:** the HMM feeds the Kelly regime multiplier and legacy gate checks. The v3 classifier feeds newer strategy components. Both are authoritative for different consumers. See [`../ml/regime-detection.md`](../ml/regime-detection.md).

### 4. Score — Cache + Regime → Scorer

**Owner:** `scorer.py` (or `intelligence/scorer.py`).

For each symbol the scanner passes in, the scorer computes factor values (RSI, EMA alignment, ATR, volume profile, CVD, entry timing, regime alignment), weights them, and emits:

- A 0–12 integer confluence score.
- A side (long or short).
- A factor breakdown for the journal.

Symbols below the scoring floor are dropped. Surviving symbols become candidates.

### 5. Gate — Candidate → Risk Gate

**Owner:** `risk_gate.py`.

For each candidate, the gate checks:

- **Regime alignment.** Long in bear? Short in bull? Reject unless override.
- **Portfolio heat.** Would this trade push total open risk past `POSITION_HEAT_CAP_PCT` (80%)? Reject.
- **Correlation cap.** Too many correlated longs already? Reject.
- **Daily loss budget.** Have we spent the day's loss budget (`MAX_DAILY_LOSS_PCT`, 5%)? Reject.
- **Max open positions.** At 5 already? Reject.
- **Leverage cap.** Would the sized trade exceed `MAX_LEVERAGE` (10x)? Reject.
- **Circuit breaker state.** Tripped? Reject everything until reset.
- **Kill switch.** Engaged? Reject everything.

Every rejection is journaled with the exact reason. The `/risk-gate` endpoint exposes this for the dashboard.

### 6. Size — Gate pass → Kelly

**Owner:** `kelly_position_sizer.py`.

For a candidate that cleared the gate:

1. Compute the full Kelly fraction from expected edge and volatility.
2. Take 25% of it (fractional Kelly).
3. Cap at 2% of equity.
4. Multiply by the regime multiplier from the HMM (bull 1.0, chop 0.5, bear 0.3).
5. Translate into base-currency quantity at current price.

The four constants in the sizing pipeline are **locked during validation**. Changing them is out of scope for any PR between 2026-04-10 and 2026-04-30.

### 7. Execute — Size → Orders

**Owner:** `execution/`.

The executor:

1. Estimates pre-trade slippage against current depth. If expected slippage would consume too much of the edge, it re-checks with the gate and may self-reject.
2. Submits the entry order.
3. On fill, submits the ATR-based stop and 2:1 RR take-profit.
4. Tracks the working-order lifecycle until both legs resolve (filled or cancelled).
5. Journals every state change.

All submissions carry client order IDs that are prefixed deterministically so the journal and exchange history can be reconciled.

### 8. Journal — Everything → Journal

**Owner:** the journal writer (shared utility).

Every layer writes events to the journal with:

- Timestamp (UTC, ISO-8601, microsecond).
- Symbol (if applicable).
- Event type (gate decision, sized, submitted, filled, cancelled, pnl update, regime flip, breaker trip, kill switch toggle, billing event).
- Structured payload.

SQLite by default; Postgres when `DATABASE_URL` points there. The journal is the source of truth for reconstruction and for the `/journal` endpoint.

### 9. Expose — Journal + state → API

**Owner:** `api/`.

The FastAPI app reads journal and in-memory state and serves:

- `/health` — liveness.
- `/scan` — current candidate list.
- `/performance` — rolling P&L and win rate.
- `/journal` — recent events, filterable.
- `/risk-gate` — current gate state and most recent decisions.
- `/position-size` — what Kelly would size a candidate at.
- `/regime/{symbol}` — current regime labels from both detectors.
- Billing endpoints (see [`../api/backend-endpoints.md`](../api/backend-endpoints.md)).

### 10. Display — API → Dashboard

The React dashboard at https://coinscope.ai/ polls the API. When the API and the UI disagree, the API (and therefore the journal) is authoritative. The dashboard is in a separate repository; changes there do not belong in this repo.

## The unhappy paths, briefly

- **Adapter loses the stream.** Reconnects with backoff. While disconnected, the cache ages and downstream consumers refuse to score. The gate rejects everything that needs fresh data. Nothing executes.
- **Regime artifact missing.** Engine fails loudly at boot. This is by design — guessing a regime is worse than refusing to trade.
- **Scorer returns a confident score on stale data.** The gate's freshness check rejects. Every stale rejection is journaled; repeated rejections against the same symbol should raise an incident.
- **Gate evaluates to "trip breaker."** Executor receives no candidates. The breaker resets at the configured window (`CIRCUIT_BREAKER_RESET_*`).
- **Order submitted, fill never arrives.** Executor cancels on a timeout and journals a reconciliation task. Humans close manually on the exchange if the cancel fails.
- **Kill switch engaged.** Gate short-circuits everything. Existing positions are not automatically unwound — that is a separate operator decision documented in [`../runbooks/daily-ops.md`](../runbooks/daily-ops.md).

## Timing budget

Rough, not SLO-grade:

| Step | Typical latency |
| --- | --- |
| WS message → cache | < 10 ms |
| Cache → score | 20–100 ms per symbol |
| Regime inference (HMM) | 50–200 ms per refresh |
| Regime inference (v3) | 100–500 ms per refresh |
| Gate | < 20 ms |
| Sizer | < 5 ms |
| Executor submit | 50–200 ms to ack |

Nothing in the engine is HFT. Our latency target is "fast enough to act within a candle," not "fast enough to beat a colocated market maker."

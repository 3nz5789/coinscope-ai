---
name: scanner-engine-optimizer
description: Optimize CoinScopeAI's real-time scanning engine for latency, rate-limit safety, CPU/RAM, and coverage — covering OHLCV, open interest, funding, liquidation, and CVD ingestion. Reviews data-fetch patterns, batching, caching, and streaming choices against Binance USDT-M weight limits during P0/P1. Use when a scan loop is slow or stale, when rate-limit hits appear in logs, when adding a new symbol or feature would change weight cost, or when designing the data layer for any future endpoint. Triggers on "engine is slow", "scan latency", "rate limit", "weight limit", "stale data", "batch the requests", "cache the OHLCV", "WebSocket vs REST", "optimize the scanner".
---

# Scanner Engine Optimizer

The engine is **frozen during the 30-day validation phase**. This skill produces analysis and proposals — implementation is gated on cohort close. Treat output as design-ready PRs, not merge-ready ones.

## When to use

- A scan cycle is taking longer than its budget (5m-bar default → must finish in <60s).
- Binance rate-limit (request weight) warnings appear in logs.
- Adding a new symbol or feature would change weight cost meaningfully.
- Designing the data layer for any future endpoint or vendor (CoinGlass, Tradefeeds at P1).
- Reviewing whether REST polling, WebSocket streams, or hybrid is the right pattern for a given feed.

## When NOT to use

- Engine code changes during P0/P1 — produce the proposal, do not merge.
- Signal logic changes — those route to `signal-design-and-backtest`.
- Cap or risk changes — those route to `coinscopeai-trading-rules`.

## Optimization axes (rank in this order)

| Rank | Axis | Why first |
|---|---|---|
| 1 | Correctness under rate limits | A throttled scan that returns stale data is worse than a slow one |
| 2 | Stale-data detection | Better to skip a bar than act on dead data |
| 3 | Latency budget | 5m bars → 60s budget; 1m bars → 12s |
| 4 | CPU / RAM | Only after correctness and latency are clean |
| 5 | Code cleanliness | Last; never trade correctness for elegance |

## Binance USDT-M weight reference (P0/P1)

| Endpoint | Weight | Notes |
|---|---|---|
| `/fapi/v1/klines` | 1-10 (limit-dependent) | Use limit ≤ 500 to keep weight low |
| `/fapi/v1/openInterest` | 1 | Cheap; safe to poll per-symbol |
| `/fapi/v1/fundingRate` | 1 | 8h cycle — cache aggressively |
| `/fapi/v1/premiumIndex` | 1 | For basis |
| WebSocket (mark, kline, forceOrder) | 0 | Always preferred when available |

Account-wide weight cap: ~2400/min on Binance USDT-M (verify in their docs at design time, do not hardcode). Stay below 60% steady-state to leave headroom for retries and probes.

## Process

### Step 1 — Capture the budget

Before optimizing: state the bar interval, the symbol count, and the per-cycle latency budget. Default for `market-scanner`: 5m bars, top-N USDT perpetuals, 60s budget.

### Step 2 — Inventory the calls

For each per-cycle call: endpoint, weight cost, frequency, and which feature consumes it. If two features hit the same endpoint, that's a dedup candidate.

### Step 3 — Apply the optimization ladder

1. **Replace REST poll with WebSocket** wherever a stream exists (klines, mark, forceOrder).
2. **Batch** what's left (multi-symbol endpoints, parallel async with bounded concurrency).
3. **Cache** quasi-static data (funding cycles, exchange info) with explicit TTL ≤ refresh interval.
4. **Tier symbols** — top-N hot symbols at full cadence, long tail at reduced cadence.
5. **Backpressure** — if weight usage > 70%, degrade gracefully (skip optional features) rather than throttle the whole cycle.

### Step 4 — Stale-data detection

Every consumer must check timestamp freshness against the bar interval. A cached funding rate from 8h ago is fine; a kline from 30m ago in a 5m loop is stale. Stale → skip the symbol for that cycle, never substitute mock values silently.

### Step 5 — Output the proposal

Produce a memo, not a PR:
- `Current state` — measured latency, weight usage, identified bottleneck.
- `Proposed changes` — ordered by rank above.
- `Expected impact` — latency delta, weight delta.
- `Risk` — what could break (correctness, edge cases, vendor differences).
- `Validation plan` — which contract tests / replays from `test-and-simulation-lab` would catch a regression.
- `Phase` — when to merge: post-cohort-close (engine thaw) or earlier if non-engine.

## Anti-patterns

- Optimizing CPU before fixing correctness or rate-limit overruns.
- Polling a feed that has a WebSocket stream available.
- Hardcoding rate limits — they change; read the venue's docs at design time.
- Silently substituting mock data when a feed is stale — must be visible to the alert layer.
- Touching engine code during validation phase without a documented incident and decision-log entry.

## Cross-references

- Engine endpoints + mock fallback: `skills/coinscopeai-engine-api`
- Risk caps (latency budget rationale): `skills/coinscopeai-trading-rules`
- Binance integration: `skills/binance-futures-api`
- Contract tests + replays: `skills_src/test-and-simulation-lab`
- Scan logic: `skills/market-scanner`
- Phase map: `business-plan/14-launch-roadmap.md`
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)

# System Overview

**Status:** current
**Audience:** anyone reading, reviewing, or extending the engine
**Related:** [`component-map.md`](component-map.md), [`data-flow.md`](data-flow.md), [`future-state-roadmap.md`](future-state-roadmap.md), [`../risk/risk-framework.md`](../risk/risk-framework.md)

One-page view of what CoinScopeAI is, how it is shaped, and where the responsibility boundaries are. This page is stable — implementation details live in [`component-map.md`](component-map.md).

## What the system does

CoinScopeAI is a single-operator autonomous trading engine for Binance USDT-M perpetual futures. It:

1. Ingests market data (klines, order book, funding, open interest, liquidations) from Binance.
2. Scores symbols with a multi-factor confluence model.
3. Classifies the current market regime with two models in parallel (HMM + v3 classifier).
4. Gates candidate trades against risk policy (heat, correlation, daily loss, circuit breakers).
5. Sizes surviving trades with Kelly-fractional sizing and regime multipliers.
6. Submits orders to Binance Testnet during validation (2026-04-10 to 2026-04-30).
7. Journals every decision, fill, and P&L update.
8. Exposes state over a FastAPI HTTP surface for the separate React dashboard at https://coinscope.ai/.

The product goal, stated in the engine's own root prompt, is **capital preservation first, profit generation second**. That ordering drives most design choices in this document.

## Shape of the system

```
            ┌─────────────────────┐
            │   Binance Futures   │ (testnet today; mainnet planned)
            │  REST + WebSocket   │
            └──────────┬──────────┘
                       │
                ┌──────┴──────┐
                │  Adapter    │  normalizes, reconnects, signs
                └──────┬──────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
     ┌────────┐   ┌────────┐   ┌────────────┐
     │Scanner │   │Regime  │   │Market data │
     │        │   │(HMM+v3)│   │cache       │
     └───┬────┘   └───┬────┘   └─────┬──────┘
         │            │              │
         └─────┬──────┘              │
               ▼                     │
          ┌────────┐                 │
          │Scorer  │◀────────────────┘
          └───┬────┘
              │  confluence score + factors
              ▼
        ┌───────────┐
        │ Risk Gate │  regime alignment, heat, correlation,
        └─────┬─────┘  daily loss, circuit breaker
              │  sized, acceptable trade
              ▼
        ┌───────────┐
        │ Executor  │  places orders on Binance testnet
        └─────┬─────┘
              │
              ▼
         ┌─────────┐           ┌─────────────┐
         │ Journal │◀─────────▶│  FastAPI    │  /scan /performance /journal /risk-gate
         └─────────┘           │  (read-only │  /position-size /regime/{symbol}
                               │   for the   │
                               │  dashboard) │
                               └──────┬──────┘
                                      │
                                      ▼
                         ┌────────────────────────┐
                         │ React dashboard        │  separate repo
                         │ https://coinscope.ai/  │
                         └────────────────────────┘

          ┌────────────────────────┐
          │ Celery workers + Redis │  periodic scans, journal flush,
          │                        │  regime refresh
          └────────────────────────┘

          ┌────────────────────────┐
          │ Stripe webhook         │  billing_server.py +
          │ + entitlements DB      │  billing/ (coexisting — see audit)
          └────────────────────────┘
```

## Responsibility boundaries

Each layer has one job. Crossing a layer's boundary is a code smell during validation and an explicit decision during design.

### Market data layer (`coinscope_trading_engine/binance_*`, `data/`)

- **Owns:** exchange connectivity, signing, WebSocket reconnects, rate-limit bookkeeping, normalized candle/depth/funding/OI feeds.
- **Does not:** make trading decisions, size orders, or decide whether to trade.

### Signal layer (scanner + scorer + regime)

- **Owns:** turning normalized market data into a list of scored candidates and a current regime label.
- **Does not:** size, gate, or place orders. Produces candidates, nothing more.
- **Has two regime systems:** HMM (bull/bear/chop) and v3 classifier (Trending/Mean-Reverting/Volatile/Quiet). They coexist by design; see [`../ml/regime-detection.md`](../ml/regime-detection.md).

### Risk layer (`risk_gate.py`, `kelly_position_sizer.py`, `risk/`)

- **Owns:** deciding whether a candidate is tradable, and if so, at what size.
- **Does not:** originate signals or place orders.
- **First-class concern:** every rejection is journaled with the reason.

### Execution layer (`execution/`)

- **Owns:** turning a sized decision into exchange calls, handling fills, managing working orders, enforcing pre-trade slippage estimates.
- **Does not:** decide whether to trade.

### API layer (FastAPI app)

- **Owns:** exposing read views of engine state for the dashboard and operator.
- **Does not:** drive the trading loop. The loop runs independently; the API reads from the same journal and shared state.
- **Read-only by default.** Any state-modifying endpoint is explicitly called out in [`../api/backend-endpoints.md`](../api/backend-endpoints.md).

### Worker layer (Celery + Redis)

- **Owns:** periodic background work — scheduled scans, regime refresh, journal flushes to Postgres, stale-position sweeps.
- **Does not:** place orders directly. Workers produce work; the executor enforces discipline.

### Billing layer (`billing_server.py`, `billing/`)

- **Owns:** Stripe webhook handling and entitlements enforcement on premium endpoints.
- **Does not:** affect trading behavior. Billing failure never degrades execution.

## Where the LLM sits

Nowhere on the hot path. The engine never asks a model to decide whether to enter or exit. The LLM is used, if at all, for offline analysis and operator tooling. See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).

## What is out of scope today

These are deliberate exclusions, not oversights:

- **Mainnet execution.** Not before validation completes.
- **Multi-exchange.** Only Binance is implemented. Bybit, OKX, Hyperliquid are planned.
- **Internal engine reorganization.** Frozen until 2026-04-30.
- **Mobile app.** The dashboard is web-only.
- **Kubernetes.** Deployment is Docker Compose on a VPS.
- **User-facing ML training UI.** Training is offline in `ml/`.

## The single most important invariant

**If the risk gate, executor, or adapter is in an uncertain state, the engine should halt, not guess.** Every circuit breaker, kill switch, and rejection path exists to honor this invariant. When in doubt in a review, ask: "does this change widen the surface where the engine would guess instead of halt?" If yes, the PR needs a reviewer who has touched risk or execution before.

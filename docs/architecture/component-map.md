# Component Map

**Status:** current
**Audience:** developers reading or modifying engine internals
**Related:** [`system-overview.md`](system-overview.md), [`data-flow.md`](data-flow.md), [`../repository-map.md`](../repository-map.md)

A module-by-module inventory of `coinscope_trading_engine/`. For each component: what it owns, who calls it, and what to watch for when changing it. Internal layout is **frozen during validation (2026-04-10 to 2026-04-30)** — this doc reflects reality, not an aspirational structure. The queued reorg is listed at the bottom.

## How this map is organized

Components are grouped by responsibility layer, matching [`system-overview.md`](system-overview.md):

1. Market data
2. Signal (scanner + scorer + regime)
3. Risk
4. Execution
5. API
6. Workers
7. Journal and metrics
8. Billing (at repo root, not inside the engine package)

## 1. Market data

### `binance_*.py` (engine root)

A set of modules at `coinscope_trading_engine/binance_*.py` that wrap the Binance Futures REST and WebSocket surface.

- **Owns:** HMAC signing, request pacing, reconnect with backoff, subscription fan-in, normalization of raw messages to internal shapes.
- **Called by:** scanner, regime detectors, data cache, executor.
- **Watch for:**
  - The 2026-04-23 stream path migration (/public, /market, /private). Incident write-up at [`../runbooks/incident-binance-ws-disconnect-2026-04-18.md`](../runbooks/incident-binance-ws-disconnect-2026-04-18.md).
  - Rate-limit weight accounting. Touching request shapes without updating weight bookkeeping will eventually 429.
  - `BINANCE_TESTNET` must be true in all validation-era configs. The adapter prints its base URL at boot — always check logs.

### `data/`

In-memory cache and normalization for klines, order book depth, funding rate, open interest, liquidation feeds.

- **Owns:** the canonical candle shape the scorer consumes.
- **Called by:** scanner and regime detectors.
- **Watch for:** changing the candle dataclass is engine-adjacent. It ripples into every downstream consumer.

## 2. Signal

### `scanner/` and `scanners/`

Two directories exist today. Both run universe iteration + per-symbol scoring loops. They overlap. Consolidation is queued for post-validation.

- **Owns:** iterating the symbol universe, calling the scorer, publishing ranked candidates.
- **Called by:** Celery beat (periodic scans) and the `/scan` API handler (ad-hoc).
- **Watch for:**
  - When editing, pick one directory and stick with it. Do not "helpfully" merge them during the freeze.
  - The symbol universe is config-driven (`SCANNER_UNIVERSE_*` env vars) — adding a symbol should not require a code change.

### `scorer.py` (or `intelligence/scorer.py`, depending on import path)

The multi-factor confluence model that emits a 0–12 score per symbol.

- **Owns:** factor weights, scoring floor, factor computation (RSI, EMA alignment, ATR, volume, CVD, entry timing, regime alignment).
- **Called by:** scanner.
- **Watch for:** factor additions must be accompanied by a test that pins the score on a fixed fixture. Silent score drift is the nastiest class of regression.

### `intelligence/` — HMM regime detector

Hidden Markov Model over log-returns. Emits `bull` / `bear` / `chop`.

- **Owns:** a 3-state HMM loaded from a saved artifact. Inference only — training happens in `/ml`.
- **Called by:** scorer (as a factor) and risk gate (for multiplier lookup).
- **Watch for:** the artifact path is an env var. If it points nowhere, the engine must fail loudly at boot, not silently default to "chop."

### `intelligence/regime_classifier_v3.py` — v3 classifier

Supervised 4-class model (Trending, Mean-Reverting, Volatile, Quiet) built on scikit-learn + xgboost.

- **Owns:** feature extraction + inference for the v3 label set.
- **Called by:** downstream strategy components that expect the 4-label taxonomy.
- **Watch for:** the feature contract. The saved model expects a specific tuple order.
- **Why two systems coexist:** the HMM is used for multiplier lookups (Kelly sizing) and legacy gate checks; v3 is used by newer strategy components. Both are documented in [`../ml/regime-detection.md`](../ml/regime-detection.md).

## 3. Risk

### `risk_gate.py`

The single entry point for "can we trade this?" Every candidate passes through here.

- **Owns:** regime alignment check, portfolio heat check, correlation cap, daily-loss budget lookup, circuit-breaker state check, kill-switch check.
- **Called by:** executor (before any order placement), `/risk-gate` API endpoint.
- **Watch for:** **two reviewers required** for any change. Adding a new check is safer than weakening an existing one. Every rejection is journaled with a human-readable reason.

### `kelly_position_sizer.py`

Computes size in base currency given equity, expected edge, volatility, and regime.

- **Owns:** Kelly fraction computation, the 25% fractional factor, the 2% hard cap, and the regime multiplier table (`bull=1.0`, `chop=0.5`, `bear=0.3`).
- **Called by:** risk gate.
- **Watch for:** during validation, the four numbers above are **locked**. Changing them requires sign-off outside the usual PR flow.

### `risk/`

Supporting policy code: heat accounting, correlation matrix maintenance, circuit breaker state machine, kill-switch storage.

- **Owns:** everything the gate reads from.
- **Called by:** risk gate and diagnostic endpoints.
- **Watch for:** state that lives longer than one scan cycle (heat, correlation, breaker state) must be journaled on every change.

## 4. Execution

### `execution/`

Turns a sized decision into exchange calls, handles fills, manages working orders.

- **Owns:** pre-trade slippage estimation, order submission, fill handling, working-order lifecycle, post-fill journaling.
- **Called by:** the trading loop, not by the API.
- **Watch for:** any path that calls Binance must be auditable in the journal. Silent order placement is a bug, not a feature.

## 5. API

### `api/` (FastAPI app)

The HTTP surface the dashboard and operator read from. Full reference: [`../api/backend-endpoints.md`](../api/backend-endpoints.md).

- **Owns:** `/health`, `/scan`, `/performance`, `/journal`, `/risk-gate`, `/position-size`, `/regime/{symbol}`, billing/entitlement endpoints.
- **Called by:** the dashboard at https://coinscope.ai/, operator `curl`, health checks.
- **Watch for:** read-only by default. Every state-modifying endpoint is explicitly flagged in the API doc.

## 6. Workers

### `worker/` (Celery app)

Background tasks driven by Celery Beat.

- **Owns:** periodic scan schedules, regime refresh cadence, journal flush from SQLite/memory to Postgres, stale-position sweeps, health probes.
- **Backed by:** Redis.
- **Watch for:** long-running tasks block the worker. Keep task bodies to seconds, chunk long work.

## 7. Journal and metrics

### Journal

Append-only log of every engine decision. SQLite by default; Postgres optional via `DATABASE_URL`.

- **Owns:** being the source of truth for "what did the engine do, when, and why."
- **Called by:** every layer writes to it; the API and dashboard read from it.
- **Watch for:** schema migrations during validation are allowed but need a migration script, not an ad-hoc ALTER.

### Prometheus metrics

The engine exposes `/metrics`; `prometheus.yml` scrapes it locally. Production Prometheus runs separately.

- **Owns:** request counts, gate decision counts, order-lifecycle latencies, circuit-breaker trip counts.
- **Watch for:** adding a metric is cheap; deleting one breaks dashboards. Deprecate before removing.

## 8. Billing (lives at repo root)

### `billing_server.py` + `billing/`

Two coexisting entry points (see [`../repository-map.md`](../repository-map.md)). `billing_server.py` is the live HTTP server; `billing/` is where the package code drifted. Consolidation is a post-validation TODO.

- **Owns:** Stripe webhook verification, subscription state, entitlement lookup for premium endpoints.
- **Watch for:** billing failure must never degrade trading. The engine treats entitlements as advisory on core endpoints and enforcing only on premium ones.

## Queued post-validation work

These are already noted in [`../product/implementation-backlog.md`](../product/implementation-backlog.md) and are **off-limits until after 2026-04-30**:

- Merge `scanner/` and `scanners/` into a single subpackage with a clear surface.
- Collapse `core/` vs. root duplication (two paths to the same modules).
- Flatten or subpackage the loose top-level `.py` files under `coinscope_trading_engine/`.
- Decide between `billing_server.py` and `billing/` as the single source of truth.
- Split the ML artifact loader so that v3 vs. HMM regime paths are less tangled.

None of these are blocking. They are housekeeping that pays off when we start the post-validation feature work.

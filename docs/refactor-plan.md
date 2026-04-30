# CoinScopeAI Refactor Plan

**Date:** 2026-04-30
**Companion:** `repo-audit.md` (architecture map), `defect-map.md` (severity-ranked issues).

## Guiding constraints

1. **Do not break working behaviour.** Paper-trading on testnet must stay live throughout.
2. **No large file moves yet.** This plan introduces new modules and rewires imports; it does not relocate existing trees.
3. **Preserve the testnet-only invariant.** Every change must keep `services/paper_trading/config.py:HARDCODED_TESTNET_ONLY = True` honoured and add new enforcement, never remove it.
4. **Distinguish implemented vs planned.** Each phase below labels new work as `NEW` (build) or `WIRE` (connect existing pieces).

## Sequencing principle

Phases are ordered so that **every phase can ship independently** and **each phase reduces the risk surface for the next**. The first phase is purely defensive. The second introduces the abstractions that subsequent phases depend on. Later phases are bigger but safer because of the scaffolding laid in 1–3.

---

## Phase 0 — Quick safety hardening (1–2 days, P0 only)

Target the four real-money / open-internet risks from `defect-map.md`.

| Step | Action | Touchpoint |
|---|---|---|
| 0.1 | Restrict `memory/api.py` CORS to dashboard origin; refuse `0.0.0.0` bind unless `MEMORY_API_PUBLIC=1`. | `memory/api.py:252-256` |
| 0.2 | Add `Depends(require_api_key)` to every `POST` and to `/memory/*` reads; key from env. | `memory/api.py`, `memory/scoopy_api.py`, `engine/api.py` |
| 0.3 | Remove `testnet: bool = True` parameter from `BinanceRestTestnetClient`; hard-code testnet URL; rename if a mainnet client is later needed. | `engine/exchange/binance_rest_testnet_client.py:26-35` |
| 0.4 | Introduce `risk_management/real_capital_gate.py` (`assert_testnet_only()`) and call it inside every exchange-client constructor (orchestrator, paper-trading, integrations). | `engine/core/master_orchestrator.py:33-45`, others |
| 0.5 | Add `tests/safety/test_testnet_only.py` that constructs each exchange client with adversarial flags and asserts the gate raises. | new file |
| 0.6 | Read `engine/api.py` allowed origins from `CORS_ORIGINS` env var with a localhost-only default. | `engine/api.py:30-35` |
| 0.7 | Pin top-level `requirements.txt` and `services/trading-engine/requirements.txt` via `pip-compile` (lockfile per service). | `requirements.txt`, `services/trading-engine/requirements.txt` |

Exit criteria: `pytest tests/safety` is green and contains tests that fail loudly if any future change re-opens P0-1…P0-3.

---

## Phase 1 — Provider abstraction (3–5 days)

Goal: one interface for execution, one for market data, with adapters for what we already have.

```
risk_management/real_capital_gate.py        ← from Phase 0
services/providers/
    __init__.py
    base.py                                 NEW   IExecutionProvider, IMarketDataProvider
    binance_testnet.py                      NEW   wraps engine/exchange/binance_*_testnet_client.py
    ccxt_adapter.py                         NEW   wraps the orchestrator's ccxt.binanceusdm path
    market_data_binance.py                  NEW   wraps services/market_data/binance/client.py
    market_data_bybit.py                    NEW   wraps services/market_data/bybit/...
```

Concrete steps:

1. Define `IExecutionProvider` (`place_order`, `cancel_order`, `get_position`, `get_balance`, `get_open_orders`) and `IMarketDataProvider` (`subscribe`, `fetch_ohlcv`, `fetch_funding`, `fetch_orderbook`).
2. Each adapter calls `RealCapitalGate.assert_testnet_only()` in `__init__`.
3. Migrate `engine/core/master_orchestrator.py:40` to take an injected `IExecutionProvider` instead of constructing `ccxt.binanceusdm` directly. Default the constructor to `BinanceTestnetExecutionProvider()` for backwards compatibility.
4. Migrate `services/paper_trading/exchange_client.py` and `services/paper_trading/order_manager.py` to depend on `IExecutionProvider` rather than the raw `BinanceFuturesTestnetClient`.
5. **Do not** delete the old clients yet. They are now wrapped, not moved.

Exit criteria: a single grep for `ccxt.binanceusdm(` returns one hit (in `ccxt_adapter.py`). All other call sites depend on the interface.

---

## Phase 2 — Sanity / fallback gate (2 days)

Goal: factor the per-pipeline checks into one shared component.

```
risk_management/sanity_gate.py             NEW
    class SignalSanityGate:
        def check(signal, market_state) -> SanityVerdict
            - reject stale ticks (last_tick_age > N seconds)
            - cap notional vs. account
            - require regime detector fitted
            - require risk_gate.is_open()
            - fallback to flat if any required input is missing
```

Then:

- Wire `SignalSanityGate.check()` into `engine/core/master_orchestrator.run_scan()` *before* it ever calls the execution provider.
- Wire the same gate into `services/paper_trading/engine_v2.py` immediately before `order_manager.submit()`.
- Mirror its verdict to the dashboard via a new `/health/gate` endpoint (Phase 4).

Exit criteria: identical signal input produces identical sanity verdict in both pipelines. Captured by a parametrised test.

---

## Phase 3 — Single canonical signal pipeline (5–7 days)

Goal: collapse the two parallel pipelines onto the safer paper-trading path.

1. Pick `services/paper_trading/engine_v2.py` as canonical. Reasons:
   - Hard testnet gate already in place.
   - Circuit breaker already wraps the executor.
   - Long-running loop fits a future Redis-backed bus better than the per-request orchestrator.
2. Move `engine/core/master_orchestrator.CoinScopeOrchestrator` behind a façade that calls into the canonical pipeline. Public method names stay (`run_scan`, etc.) so `engine/api.py` does not break.
3. Migrate `engine/signals/scoring_fixed.FixedScorer` and the orchestrator's MTF/whale/sentiment filters into `services/paper_trading/signal_engine.py` (or a sibling `signal_pipeline.py`) so there's one place that produces signals.
4. Delete the old orchestrator file last, after at least one full week of green production traffic.

Exit criteria: only one code path constructs an `IExecutionProvider`. Dashboards still receive identical data.

---

## Phase 4 — Storage layer (4–6 days)

Goal: introduce PostgreSQL + Redis without breaking the in-process bus.

1. **NEW** `app/db/` (or reuse the existing `services/trading-engine/migrations/` after we land an `app/` for it):
   - SQLAlchemy 2.0 + async sessions.
   - Alembic migrations for: `orders`, `fills`, `positions`, `daily_pnl`, `regime_state`, `model_runs`, `audit_log`.
2. **NEW** `app/storage/repository.py` per aggregate. Repositories are the only thing the canonical pipeline knows about.
3. **WIRE** paper-trading state to repository on every state transition; replay on startup.
4. **WIRE** Notion sync as a downstream subscriber to the event bus, not an inline call inside the loop. (Today `engine/integrations/portfolio_sync.py` couples Notion to the trade path.)
5. **NEW** Redis client at `app/storage/redis_client.py` (factory only — used in Phase 5).

Exit criteria: kill `-9` the paper_trading process; restart; see open positions, daily P&L, kill-switch state restored before the loop resumes.

---

## Phase 5 — Distributed event bus (3–5 days)

Goal: keep the in-process bus for local dev; add a Redis-backed bus for prod.

1. Extract the `EventBus` API from `services/market_data/event_bus.py` into a `Protocol` (`IEventBus`).
2. Keep the current implementation as `InProcessEventBus`.
3. **NEW** `RedisStreamsEventBus(IEventBus)` using the Redis client from Phase 4.
4. Selection at startup via env: `EVENT_BUS_BACKEND={inprocess|redis}` defaulting to inprocess.
5. The scanner, signal pipeline, executor, and Notion-sync subscriber all bind to `IEventBus`, not the concrete class.

Exit criteria: scanner can run in one container, executor in another, both seeing the same events.

---

## Phase 6 — FastAPI consolidation (3 days)

Goal: one API gateway, three routers.

1. Stand up `services/trading-engine/app/main.py` (currently empty) as the single FastAPI process.
2. Mount routers:
   - `/scan`, `/journal`, `/regime`, `/scale/check` ← move from `engine/api.py`.
   - `/memory/*` ← move from `memory/api.py` (behind auth).
   - `/health/*` ← new.
3. Inject the canonical pipeline (Phase 3) and repositories (Phase 4) via FastAPI `Depends`.
4. Add JWT-based auth tied to whatever the existing OAuth portal at `VITE_OAUTH_PORTAL_URL` returns; keep an API-key fallback for backend-to-backend.
5. Keep `engine/api.py` and `memory/api.py` running in parallel for a deprecation window; have them proxy to the new app.

Exit criteria: dashboard reads from one host:port; old hosts return `308` redirects.

---

## Phase 7 — ML engine interface (3 days)

Goal: model swaps don't touch the signal pipeline.

1. **NEW** `app/ml/base.py` — `IModel.predict(features) -> ScoreVector`, with explicit `model_version` metadata.
2. **NEW** `app/ml/registry.py` — loads `ml_models/trained/<version>/<pair>_*.json` and instantiates the right adapter (LightGBM vs. LogReg).
3. **WIRE** `engine/signals/scoring_fixed.py` and `services/paper_trading/signal_engine.py` to call `IModel`, not joblib directly.
4. **PLAN** (do not build yet) the LSTM / GAN / RL adapters mentioned in the blueprint. Capture the gap in `docs/feature_roadmap.md`.

Exit criteria: a new model can be added by writing one adapter class and dropping artefacts into `ml_models/trained/<new-version>/`.

---

## Phase 8 — Frontend / dashboard cleanup (2 days)

Goal: remove the stale tree and the third-party API leak.

1. Delete `frontend/dist` and `frontend/node_modules` after confirming nothing in CI references them.
2. Move the `frontend-forge` API call (`apps/dashboard/src/components/Map.tsx:89`) to a server-side proxy under the new FastAPI gateway. Drop `VITE_FRONTEND_FORGE_API_KEY` from the frontend bundle.
3. Centralise polling cadence (`useApiData.ts`); consider SSE/WebSocket for the live scanner page.
4. Wire the OAuth portal flow end-to-end so an unauthenticated dashboard render shows a login screen instead of broken fetches.

Exit criteria: `git grep VITE_.*API_KEY apps/dashboard` returns no matches.

---

## Phase 9 — Observability (3 days)

Goal: turn the existing Prometheus exporter into a real observability layer.

1. Make every Phase-3 pipeline stage emit a metric (`signal_emitted_total`, `signal_rejected_total{reason=}`, `order_submitted_total`, `order_failed_total{reason=}`, `daily_pnl`, `kill_switch_state`).
2. Structured logging via `structlog`; one JSON line per pipeline event.
3. Liveness/readiness endpoints under `/health/{live,ready,gate}` (the gate one exposes the sanity-gate verdict).
4. Add Grafana dashboard JSON to `infra/grafana/`.

Exit criteria: a single Grafana view shows scanner throughput, signal-rejection breakdown, executor latency, and capital-preservation gate state.

---

## Phase 10 — Cleanup (1 day, gated on Phases 0–9)

Only after the new path is stable for at least a week:

- Delete `frontend/`, `backend/` top-level dirs.
- Delete `services/paper_trading/engine.py` (v1) once unreferenced.
- Decide canonical Telegram location: keep `bot/telegram_alerts.py` and remove `services/telegram-bot/` empty subtrees, or migrate.
- Delete the old `engine/api.py` and `memory/api.py` once Phase 6 redirects have been live for two weeks.

---

## Out of scope for this plan

- Building Stripe / billing. Captured separately; not on the critical path.
- LSTM / GAN / RL training. Phase 7 makes them addable; building them is a research stream.
- Multi-exchange execution (Bybit/OKX live). Phase 1's `IExecutionProvider` makes it possible; doing it is a market decision.

---

## Tracking

Each phase corresponds to a single PR (or PR train) on a feature branch off the `CoinScopeAI_v2` integration branch. Use the defect-map IDs (P0-1, P1-2, etc.) as PR labels so the audit trail back to this document is preserved.

Suggested initial PR labels:
- `audit/P0-1-memory-cors`
- `audit/P0-2-rest-client-rename`
- `audit/P0-3-real-capital-gate`
- `audit/P0-4-auth`
- `audit/P0-5-paper-state-persistence`
- `audit/P1-1-pipeline-collapse`
- `audit/P1-2-provider-abstraction`
- …

When all P0 items have an open PR, move them to `in-review`. When all P0 items are merged, the repo is ready to start Phase 1.

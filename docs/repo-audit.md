# CoinScopeAI Repository Audit

**Date:** 2026-04-30
**Audited tree:** `/Users/mac/Projects/coinscope-ai` (branch `chore/design-system-and-frontend-improvements`)
**Public app:** https://app.coinscope.ai/
**Scope:** Map current code to target architecture domains. Distinguish implemented vs planned. No code moves.

> Companion docs: `defect-map.md` (issues with severity), `refactor-plan.md` (sequenced remediation).

---

## 1. Repository topology

```
coinscope-ai/
├── apps/dashboard/          ← React + Vite + Tailwind (ACTIVE frontend)
├── frontend/                ← STALE: only dist/ and node_modules/, no source
├── backend/                 ← STALE: only .pytest_cache/ and logs/
├── engine/                  ← Python orchestrator + signals + exchange clients (ACTIVE)
│   ├── api.py               ← FastAPI bridge (uvicorn :8001)
│   ├── core/                ← master_orchestrator, scale_up_manager, retrain_scheduler
│   ├── signals/             ← scoring_fixed, multi-timeframe, whale, funding, alpha-decay
│   ├── exchange/            ← Binance testnet REST/WS/Futures clients
│   ├── integrations/        ← Notion sync, trade journal
│   └── monitoring/          ← metrics_exporter, realtime_dashboard
├── services/
│   ├── market_data/         ← Multi-exchange ingestion, event bus, scanners (ACTIVE)
│   ├── paper_trading/       ← Testnet-locked execution loop (ACTIVE)
│   ├── trading-engine/      ← SKELETON: empty app/, only requirements + migrations dirs
│   └── telegram-bot/        ← SKELETON: empty handlers/, services/, templates/
├── bot/telegram_alerts.py   ← Active Telegram alert sender (polling-style POSTs)
├── ml_models/               ← Trained joblib artifacts (lgbm + logreg per pair)
│   └── training/            ← Feature engine v3 + train script
├── risk_management/         ← risk_gate, kelly_position_sizer, hmm_regime_detector
├── strategies/              ← Backtest configs, research notebooks
├── memory/                  ← Internal "Scoopy/MemPalace" KB API (FastAPI :8002)
├── infra/                   ← docker, systemd
├── deploy/                  ← systemd unit files
├── data/                    ← features/, pipelines/, processed/, raw/
├── docs/                    ← project docs (this file lives here)
└── archive/                 ← previous-iteration docs
```

**Two empty skeletons** (`services/trading-engine/app/` has 0 .py files; `services/telegram-bot/` subdirs are empty) and **two stale roots** (`backend/`, `frontend/`) inflate the apparent scope. Real implementation lives in `engine/`, `services/market_data/`, `services/paper_trading/`, `risk_management/`, `apps/dashboard/`, `bot/`, `memory/`, and `ml_models/`.

---

## 2. Mapping to target domains

Legend: ✅ implemented · 🟡 partial · 🔴 absent · ⚠️ drift from target

| Target domain | Status | Where it lives | Notes |
|---|---|---|---|
| **Auth** | 🔴 absent | — | No JWT/OAuth/API-key middleware on any FastAPI app. Dashboard imports `VITE_OAUTH_PORTAL_URL` (`apps/dashboard/src/const.ts:5`) but the corresponding server-side handler is not in this repo. |
| **Billing** | 🔴 absent | — | Zero Stripe / payments code. Mentioned only as an example fact-type in `memory/config.py`. |
| **Dashboard (web)** | ✅ | `apps/dashboard/src/{pages,components,hooks}` | 12 pages incl. AlphaSignals, EquityCurve, LiveScanner, RiskGate, TradeJournal. Generic refetch hook at `useApiData.ts`. |
| **Dashboard (legacy)** | ⚠️ stale | `frontend/dist`, `frontend/node_modules` | No source — should be removed. |
| **Scanner** | ✅ | `services/market_data/scanner/`, `services/market_data/coinglass/`, `services/market_data/alpha/` | OI, funding, liquidity, spread scanners publishing to event bus. |
| **Market data** | ✅ | `services/market_data/{binance,bybit,okx,hyperliquid,streams,event_bus.py}` | Topic-based event bus (`event_bus.py`) with bounded queues + overflow policy. Public REST hits **mainnet** (`fapi.binance.com`) — read-only, by design. |
| **Signals** | ✅ | `engine/signals/`, `engine/core/master_orchestrator.py`, `services/paper_trading/signal_engine.py` | **Two parallel signal pipelines** — see drift §3.1. |
| **ML engine** | 🟡 | `ml_models/trained/v3/` (lgbm + logreg per pair), `ml_models/training/features/engine_v3.py`, `engine/signals/scoring_fixed.py` | Inference is **inlined** in scorers; no `IModel` interface. No LSTM/GAN/RL despite blueprint targets — those exist only in the legacy flat-layout download. |
| **Risk / capital preservation** | ✅ | `risk_management/{risk_gate,kelly_position_sizer,hmm_regime_detector}.py`, `services/paper_trading/safety.py`, `services/paper_trading/exchange_client.py` (circuit breaker) | Wired into both orchestrator and paper-trading executor. |
| **Execution** | 🟡 testnet | `engine/exchange/binance_*_testnet_client.py`, `services/paper_trading/order_manager.py`, `services/paper_trading/exchange_client.py` | Mostly safe — paper_trading hard-locks via `HARDCODED_TESTNET_ONLY = True`. Orchestrator's `ccxt.binanceusdm` accepts `testnet=False` from caller — see defect-map. |
| **Integrations** | 🟡 | `engine/integrations/{notion_*,trade_journal,trade_logger,portfolio_sync}.py`, `bot/telegram_alerts.py` | Notion + Telegram active; no Stripe / Slack / Email. |
| **Storage** | 🟡 | `memory/stores/`, SQLite at `backend/logs/klines.sqlite`, Notion via REST | **No PostgreSQL/Redis wired into the live path.** `services/trading-engine/app/` was meant to host SQLAlchemy + asyncpg + redis — empty. paper_trading state is in-memory, lost on restart. |
| **Observability** | 🟡 | `engine/monitoring/metrics_exporter.py`, `engine/monitoring/realtime_dashboard.py`, `infra/` | Prometheus exporter exists; no centralised log aggregation, no tracing, no alerting hookup beyond Telegram. |
| **Backtest pipeline** | ✅ | `strategies/backtests/`, references to `ml_models/training/training/train_v3.py` | Reports under `ml_models/training/reports/v3/`. |
| **Real-capital gate (testnet only)** | 🟡 | `services/paper_trading/config.py:25` | Hard gate exists for **paper-trading path** only; orchestrator path is convention-gated. |

---

## 3. Architectural drift vs. target blueprint

### 3.1 Two parallel pipelines (the biggest drift)

Two independent signal→execution loops live side-by-side and rarely share types:

| Concern | Path A — `engine/core/master_orchestrator.py` | Path B — `services/paper_trading/engine_v2.py` |
|---|---|---|
| Trigger | `engine/api.py /scan` endpoint | `services/paper_trading/__main__.py` long-running loop |
| Exchange client | `ccxt.binanceusdm` (constructed inline at L40) | `BinanceFuturesTestnetClient` from `engine/exchange/` |
| Scoring | `FixedScorer` + MTF + whale + sentiment | `signal_engine.py` (different scoring rubric) |
| Risk | `RiskGate` + `KellyRiskController` + `EnsembleRegimeDetector` | `safety.py` + circuit breaker in `exchange_client.py` |
| Testnet enforcement | `set_sandbox_mode(True)` only when caller passes `testnet=True` | `HARDCODED_TESTNET_ONLY = True`, mainnet URL blocklist |
| Persistence | Notion via `TradeJournal` | In-memory only |

→ **Drift:** Blueprint expects ONE signal pipeline behind a provider abstraction. We have two with diverging risk policies, scorers, and capital-preservation guarantees.

### 3.2 Provider abstraction is missing

Blueprint calls for a single `IExchange`/`IDataProvider` interface. Reality:

- `engine/core/master_orchestrator.py:40` constructs `ccxt.binanceusdm(...)` directly.
- `engine/exchange/binance_*_testnet_client.py` is a hand-rolled REST/WS/Futures triplet.
- `services/market_data/binance/client.py` is a third REST client (mainnet, public-only).
- `services/paper_trading/exchange_client.py` wraps the futures-testnet client with a circuit breaker.

No common base class. Adding Bybit/OKX *for execution* would require copy-paste because Bybit/OKX clients exist only on the data side (`services/market_data/{bybit,okx}/`).

### 3.3 Two FastAPI apps, no gateway

- `engine/api.py` — uvicorn :8001, CORS allow-list = localhost:5173/3000, no auth.
- `memory/api.py` — uvicorn :8002, CORS `allow_origins=["*"]`, no auth.
- `services/trading-engine/app/` — empty skeleton intended as the "real" FastAPI service.

Dashboard must therefore know two host:port pairs, and Memory API is world-callable.

### 3.4 Event bus is local, not distributed

`services/market_data/event_bus.py` is an in-process pub/sub (queue.Queue + threads). The blueprint hints at Redis-backed messaging. Today, scanner and trading-engine cannot run in different processes without losing the bus — so paper_trading is launched as a long-running monolith.

### 3.5 ML engine is shallower than the blueprint

Blueprint mentions LSTM, GAN, RL. Repo has only LightGBM + LogReg per pair (`ml_models/trained/v3/`). The richer models referenced in the legacy flat layout (`accuracy_measurement.py`, RL agents, GAN backtests) did not migrate into this repo.

### 3.6 Storage layer is ad-hoc

- `backend/logs/klines.sqlite` — undocumented SQLite cache used by some streamers.
- `memory/stores/` — file-based KB.
- Notion is the trade journal of record (`engine/integrations/trade_journal.py`).
- `services/trading-engine/migrations/` exists but its parent `app/` is empty — migrations have nothing to migrate.

No single source of truth for trade history, positions, account balance, or audit log.

### 3.7 UI ↔ provider coupling

The dashboard does not (yet) call providers directly, but:
- `apps/dashboard/src/components/Map.tsx:89` reads `VITE_FRONTEND_FORGE_API_KEY` and calls a third-party API directly from the browser.
- All dashboard data flows through a single uvicorn :8001 process, and that process *is* the orchestrator (`engine/core/master_orchestrator.CoinScopeOrchestrator`), so a long-running scan ties up the API thread.

→ **Drift:** UI, API layer, and provider logic are colocated in `engine/api.py`. Blueprint separates them.

### 3.8 Duplicated / variant files

| File | Variant of | Status |
|---|---|---|
| `services/paper_trading/engine.py` | `services/paper_trading/engine_v2.py` | v2 active; v1 imported by older tests |
| `engine/signals/scoring_fixed.py` | `…/scoring*.py` (legacy flat layout) | only `_fixed` survived migration |
| `ml_models/training/features/engine_v3.py` | engine v1/v2 (legacy) | v3 is the active feature builder |
| `frontend/` | `apps/dashboard/` | `frontend/` stale (dist+node_modules only) |
| `backend/` | engine + services | `backend/` stale (logs+pytest cache only) |
| `services/trading-engine/app/` | engine/api.py | empty placeholder |
| `services/telegram-bot/` | `bot/telegram_alerts.py` | empty placeholder |

`VARIANTS.md` (in the legacy flat-layout download) tracked many more duplicates; most were dropped during the 2026-04-19 restructure.

---

## 4. Implemented vs planned (quick reference)

**Implemented and live:**
- Multi-exchange market-data ingestion → in-process event bus
- Scanner (OI, funding, liquidity, spread)
- Two signal pipelines (orchestrator path + paper-trading path)
- Risk gate, Kelly sizer, HMM regime detector
- LightGBM + LogReg inference for 6 pairs (4h)
- Testnet-only execution via paper_trading
- Telegram alerting (one-way, polling-POST)
- Notion-backed trade journal and portfolio sync
- React dashboard with 12 pages
- Prometheus metrics exporter
- Backtest pipeline (v3)

**Planned / scaffolded but not implemented:**
- `services/trading-engine/app/` FastAPI service (SQLAlchemy + asyncpg + redis)
- `services/telegram-bot/` (handlers/services/templates folders empty)
- Auth (OAuth portal referenced but server-side not in this repo)
- Billing / Stripe
- Distributed event bus (Redis Streams)
- LSTM / GAN / RL models referenced in blueprint
- Centralised observability (logs + tracing)

**Stale / removable:**
- `frontend/` (replaced by `apps/dashboard/`)
- `backend/` (only logs + pytest cache)
- Empty subtrees inside `services/trading-engine/app/` and `services/telegram-bot/*`

---

## 5. Risk surface at a glance

See `defect-map.md` for the full list. Top concerns:

1. **`memory/api.py` CORS `*` with no auth** — exposes KB read+write endpoints publicly if ever bound off-localhost.
2. **`engine/exchange/binance_rest_testnet_client.py` accepts `testnet: bool = True` parameter** — the *file is named* "testnet" but switches to `https://api.binance.com` if the caller passes `False`. Misleading API.
3. **`engine/core/master_orchestrator.CoinScopeOrchestrator(testnet: bool = True)`** — soft default; nothing prevents `testnet=False` from a future caller.
4. **No persistence** — paper_trading state is lost on every restart; orchestrator depends on Notion availability for trade history.
5. **Floating dependency versions** in both `requirements.txt` files — supply-chain drift.

---

## 6. Inventory of FastAPI surfaces

| File | Port | CORS | Auth | Purpose |
|---|---|---|---|---|
| `engine/api.py` | 8001 | `localhost:5173`, `localhost:3000` | none | `/scan`, `/journal`, `/regime`, `/scale/check`, `/health` |
| `memory/api.py` | 8002 | `*` (wildcard) | none | `/memory/{search,add,wake-up,status,kg/*}` |
| `memory/scoopy_api.py` | 8003 (default) | n/a | none | Internal Scoopy KB endpoints |
| `services/trading-engine/app/` | (planned 8000) | n/a | n/a | Empty — never instantiated |

---

## 7. What this audit deliberately does NOT do

- No file moves, no renames, no deletes (per constraint).
- No behaviour changes — read-only inspection.
- No attempt to enumerate the legacy flat-layout download (`~/Downloads/Review and Analyze the Dashboard System (5)/`); that tree is documented in user memory and is **not** the git repo.
- No Granola/Confluence/Notion content discovery — this is a code-only audit.

Continue to `defect-map.md` for severity-ranked issues, then `refactor-plan.md` for the sequenced fix path.

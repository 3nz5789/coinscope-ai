# CoinScopeAI Defect & Risk Map

**Date:** 2026-04-30
**Companion:** `repo-audit.md` (architectural map), `refactor-plan.md` (remediation order).

Severity legend
- **P0** — Real-money risk, data loss, or open-internet exposure of state-mutating endpoints.
- **P1** — Architectural drift that already costs us shipping speed or correctness.
- **P2** — Maintainability / hygiene that will bite within a quarter.
- **P3** — Cleanup / cosmetic.

Each row cites at least one file:line. Some lines are approximate (file may have shifted by a few lines since inspection).

---

## P0 — Capital, security, exposure

### P0-1 · `memory/api.py` exposes wildcard CORS with no auth on state-mutating endpoints
- **Where:** `memory/api.py:252-256` (`allow_origins=["*"]`), `memory/api.py:81-241` (POST `/add`, POST `/wake-up`, GET `/search`, etc.)
- **Why it matters:** If this process is ever reachable off-localhost (a dev tunnel, a docker-compose with a published port, a misconfigured ingress) any browser on the internet can read **and write** the memory KB.
- **Fix:** restrict origins to the dashboard host; require an API key or session token for all `POST` routes; block `0.0.0.0` binding by default.

### P0-2 · `BinanceRestTestnetClient` silently switches to mainnet
- **Where:** `engine/exchange/binance_rest_testnet_client.py:26-35`
  ```python
  def __init__(self, api_key, api_secret, testnet: bool = True):
      ...
      if testnet:
          self.base_url = "https://testnet.binance.vision/api"
      else:
          self.base_url = "https://api.binance.com/api"
  ```
- **Why it matters:** The class name (`…TestnetClient`) and module name (`…_testnet_client.py`) imply testnet-only. A future caller seeing the class name will not realise that passing `testnet=False` flips to live mainnet trading.
- **Fix:** remove the `testnet` parameter, hard-code the testnet URL, and rename the class to `BinanceSpotTestnetClient`. Move any "real" client into a separately named module behind an explicit feature flag.

### P0-3 · `CoinScopeOrchestrator(testnet=True)` is convention-gated, not enforced
- **Where:** `engine/core/master_orchestrator.py:33-45`
  ```python
  def __init__(self, testnet: bool = True, pairs: list = None):
      self.exchange = ccxt.binanceusdm({"enableRateLimit": True})
      if testnet:
          self.exchange.set_sandbox_mode(True)
  ```
- **Why it matters:** The blueprint says real-capital is **locked** to testnet. Today, only `services/paper_trading/config.py:25` (`HARDCODED_TESTNET_ONLY = True`) enforces this. The orchestrator path that `engine/api.py /scan` triggers will execute on mainnet if a caller passes `testnet=False`.
- **Fix:** add a single global `RealCapitalGate.assert_testnet_only()` called at every place that constructs an exchange client. Make the gate read an env-controlled flag that defaults to `False` (i.e. testnet) and refuse to flip without an explicit allow-list signed by ops.

### P0-4 · No authentication on any FastAPI endpoint
- **Where:** `engine/api.py:42-146`, `memory/api.py:81-241`, `memory/scoopy_api.py:33-72`
- **Why it matters:** `POST /memory/add`, `POST /engine/scale/check`, `GET /scan` all execute privileged work. Trivially abused if the process binds to a public interface.
- **Fix:** add an API-key dependency (`Depends(require_api_key)`) on every router; for the dashboard, route through an OAuth/JWT middleware tied to `VITE_OAUTH_PORTAL_URL`. Until then, refuse to start uvicorn unless `--host 127.0.0.1`.

### P0-5 · No persistence for paper-trading state
- **Where:** `services/paper_trading/engine_v2.py`, `services/paper_trading/order_manager.py` — state held in module-level dicts.
- **Why it matters:** A crash/restart loses open positions, fill history, daily P&L, and the kill-switch latched state. The Kelly sizer relies on rolling stats it cannot rebuild.
- **Fix:** persist orders, fills, positions, and daily P&L to PostgreSQL (or at minimum SQLite) at every state transition. Replay on startup before resuming the loop.

---

## P1 — Architectural drift / correctness

### P1-1 · Two parallel signal→execution pipelines
- **Where:** `engine/core/master_orchestrator.py` vs. `services/paper_trading/engine_v2.py` + `services/paper_trading/signal_engine.py`
- **Why it matters:** The two pipelines have different scoring rubrics, different risk gates (`risk_management/risk_gate.py` vs. `services/paper_trading/safety.py`), and different testnet enforcement strength (P0-3 vs. P0-2 hardness). A signal generated for the dashboard may not match a signal that would be executed.
- **Fix:** pick one pipeline as canonical (recommend the paper-trading path because it has the hard testnet gate). Wrap the other in a thin façade that calls the canonical one. See `refactor-plan.md §2`.

### P1-2 · No provider abstraction for execution
- **Where:** `engine/core/master_orchestrator.py:40` (`ccxt.binanceusdm(...)`), `engine/exchange/binance_*_testnet_client.py`, `services/paper_trading/exchange_client.py`, `services/market_data/binance/client.py` — four parallel Binance clients.
- **Why it matters:** Adding Bybit/OKX execution would require touching all four. The blueprint's "provider abstraction" target is unmet.
- **Fix:** define `IExecutionProvider` (place_order, cancel_order, get_position, get_balance) and `IMarketDataProvider` (subscribe, fetch_ohlcv, fetch_funding) and adapt all current clients to them. See `refactor-plan.md §3`.

### P1-3 · Trading-engine FastAPI service is an empty skeleton
- **Where:** `services/trading-engine/app/` (0 .py files), `services/trading-engine/migrations/` (no migration files), `services/trading-engine/Dockerfile` (references a non-existent module).
- **Why it matters:** Anyone reading the repo expects a working service here; CI may already attempt to build it.
- **Fix:** either delete the skeleton or land a minimal `app/main.py` exposing one endpoint and a `db/session.py` with a real Alembic migration. See `refactor-plan.md §4`.

### P1-4 · Event bus is in-process only
- **Where:** `services/market_data/event_bus.py:1-160`
- **Why it matters:** Scanner, signals, and execution must run in one Python process to share the bus. Cannot scale horizontally; a single bug in a subscriber thread can starve publishers.
- **Fix:** put a Redis Streams adapter behind the same `EventBus` API. Default to in-process for local dev, Redis for prod. See `refactor-plan.md §5`.

### P1-5 · `engine/api.py` couples HTTP layer to orchestrator construction
- **Where:** `engine/api.py:60-66` constructs `CoinScopeOrchestrator(...)` per-request inside the route handler.
- **Why it matters:** A `/scan` call instantiates regime detectors, ML scorers, and a CCXT client every time. Slow, leaks connections, and makes the route untestable.
- **Fix:** move construction to FastAPI startup as a singleton; inject via `Depends`. See `refactor-plan.md §6`.

### P1-6 · No sanity / fallback gate between signals and execution
- **Where:** signals flow `signal_engine.py` → `order_manager.py` (paper_trading) and orchestrator → orchestrator-internal — no shared "this signal is sane" gate.
- **Why it matters:** The blueprint calls for an explicit sanity/fallback gate (e.g. cap notional, confirm market hours, refuse when last-tick > N seconds stale, refuse if regime detector hasn't been fit). Today, each pipeline implements its own subset.
- **Fix:** factor a `SignalSanityGate` in `risk_management/` and require both pipelines to pass through it.

### P1-7 · ML inference is inlined into scorers
- **Where:** `engine/signals/scoring_fixed.py` (loads joblib artefacts directly), `services/paper_trading/signal_engine.py` (separate inference path)
- **Why it matters:** No `IModel.predict()` interface; swapping LightGBM for an LSTM means rewriting the scorer. Versioning is implicit (`ml_models/trained/v3/`).
- **Fix:** introduce `MLEngine.score(features) -> ScoreVector` with explicit model-version metadata; route both pipelines through it.

### P1-8 · Dashboard talks directly to a third-party `frontend-forge` API from the browser
- **Where:** `apps/dashboard/src/components/Map.tsx:89` — `const API_KEY = import.meta.env.VITE_FRONTEND_FORGE_API_KEY;`
- **Why it matters:** API keys baked into the bundle are recoverable from any user's browser. Even with rate limits, this is a leak.
- **Fix:** proxy the call through the FastAPI layer; never embed third-party keys in the frontend bundle.

### P1-9 · Orchestrator constructs WhaleSignalFilter with `os.getenv("WHALE_ALERT_KEY", "")`
- **Where:** `engine/core/master_orchestrator.py:46`
- **Why it matters:** Empty key silently downgrades to a no-op filter — looks like the filter is on, isn't. Hides a regression.
- **Fix:** fail-fast at startup if any required key is missing, OR surface the no-op state in `/health`.

### P1-10 · CORS allow-list in `engine/api.py` will break in production
- **Where:** `engine/api.py:30-35` — `allow_origins=["http://localhost:5173", "http://localhost:3000"]`
- **Why it matters:** Production deploy at app.coinscope.ai will silently fail browser requests.
- **Fix:** read allowed origins from env var with a localhost-only default.

---

## P2 — Maintainability / hygiene

### P2-1 · Floating dependency versions
- **Where:** `requirements.txt` (`fastapi>=0.104.0`, `requests>=2.31.0`, etc.) and `services/trading-engine/requirements.txt` (`fastapi>=0.109.0`, `sqlalchemy>=2.0.0`, etc.)
- **Why it matters:** Reproducibility + supply-chain drift. A breaking 0.x bump can land mid-CI.
- **Fix:** use `pip-tools` / `uv` to compile pinned `requirements.lock`; keep upper bounds.

### P2-2 · Stale top-level directories
- **Where:** `frontend/` (only `dist/` + `node_modules/`), `backend/` (only `.pytest_cache/` + `logs/`)
- **Fix:** delete after confirming nothing is imported from them.

### P2-3 · Empty service skeletons
- **Where:** `services/trading-engine/app/`, `services/telegram-bot/{handlers,services,templates}/`
- **Fix:** either implement minimal stubs or remove the dirs to avoid confusing new contributors.

### P2-4 · `services/paper_trading/engine.py` and `engine_v2.py` coexist
- **Where:** `services/paper_trading/engine.py`, `services/paper_trading/engine_v2.py`
- **Why it matters:** Tests / scripts may import the old one.
- **Fix:** confirm v1 is unreferenced, then delete or alias.

### P2-5 · Mixed mainnet vs. testnet endpoint usage in `services/market_data`
- **Where:** `services/market_data/streams/{downloader,orderbook,funding}.py` use `https://fapi.binance.com` (mainnet, public REST).
- **Why it matters:** Correct (public market data is fine on mainnet) but visually conflicts with the testnet-only narrative; reviewers must triple-check every URL.
- **Fix:** add a comment header to each file: `# READ-ONLY public data. Mainnet endpoint is intentional.`

### P2-6 · Print-style error reporting
- **Where:** `engine/exchange/binance_rest_testnet_client.py:78-80` (`print("❌ Request failed: …")`)
- **Why it matters:** Bypasses logging config; emoji-only signal in a production exception path.
- **Fix:** use `logger.exception(...)`; reserve emoji for human-facing surfaces only.

### P2-7 · Generic `useApiData` hook with hard-coded 5 s polling
- **Where:** `apps/dashboard/src/hooks/useApiData.ts:20`
- **Why it matters:** Every page polls every 5 s — multiplied across 12 pages it's a hot loop.
- **Fix:** centralise refresh cadence; consider WebSocket/SSE for live data.

### P2-8 · No tests for testnet enforcement
- **Where:** repository-wide
- **Why it matters:** P0-2/P0-3 will regress silently without a guard test.
- **Fix:** add `tests/safety/test_testnet_only.py` that imports every exchange-client constructor and asserts it raises if a mainnet URL appears.

### P2-9 · `apps/dashboard/src/const.ts` references OAuth portal that has no server side here
- **Where:** `apps/dashboard/src/const.ts:5-8`
- **Fix:** either complete the OAuth flow (P0-4) or guard the dashboard so unauthenticated state is the explicit default.

### P2-10 · Two telegram code paths (only one populated)
- **Where:** `bot/telegram_alerts.py` (active), `services/telegram-bot/{handlers,services,templates}/` (empty)
- **Fix:** decide canonical location; remove the other.

---

## P3 — Cleanup / cosmetic

- **P3-1** · `engine/api.py` mixes inline imports inside route handlers (`from engine.core.master_orchestrator import CoinScopeOrchestrator` inside `/scan`).
- **P3-2** · `Cargo.toml` at the root of the legacy download is a leftover from an experiment; not in this git repo, but worth noting if it ever resurfaces.
- **P3-3** · Several files use `print` for status banners on startup (`engine/integrations/notion_sync_config.py:149`).
- **P3-4** · `coinscope_ai_architecture_*.svg` artefacts at repo root — fine for now, but they are not gitignored from `git status`.
- **P3-5** · 12 dashboard pages import from one big `useApiData` rather than per-resource hooks — worth splitting.
- **P3-6** · Some `__init__.py` files are empty placeholders that should re-export the public surface explicitly.

---

## Cross-cutting observations

- **What is actually safe today:** the `services/paper_trading/*` path is *genuinely* testnet-locked and will refuse to talk to mainnet. The hard gate is real and well-designed.
- **What gives a false sense of safety:** the orchestrator path. Its safety relies on every caller passing `testnet=True`. The fact that `engine/api.py` happens to do this is a convention, not an enforcement.
- **What is missing entirely:** auth, billing, persistent storage of trading state, distributed event bus, a real provider abstraction, sanity/fallback gate as a shared component.
- **What is implemented well:** the event bus design (topic + bounded queues + overflow policy), the testnet config validator in `services/paper_trading/config.py`, the separation of risk-management primitives in `risk_management/`, the React dashboard page split.

Continue to `refactor-plan.md` for sequenced remediation.

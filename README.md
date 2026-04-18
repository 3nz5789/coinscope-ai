# CoinScopeAI

> AI-driven Binance USD-M Futures scanner + autonomous trading engine. Capital preservation first, profit generation second. Binance Testnet only during validation.

**Status:** Validation phase (2026-04-10 to 2026-04-30). No core-engine changes until validation closes.
**Primary dashboard (separate repo):** <https://coinscope.ai/>
**Engine API (local):** `http://localhost:8001`

---

## What this repo is

A Python 3.11+ trading engine. Everything under this repo is backend:

- `coinscope_trading_engine/` - scanner, signal scoring, risk gate, execution, FastAPI HTTP surface, Celery workers, HMM regime detector.
- `billing/` + `billing_server.py` - Stripe webhook + entitlements subsystem (duplication under review; see `docs/ops/stripe-billing.md`).
- `ml/` - v3 regime classifier training pipeline (Random Forest + XGBoost ensemble; labels: Trending / Mean-Reverting / Volatile / Quiet).
- `dashboard/` - 3 static HTML pages (`pricing.html`, `billing_success.html`, `pnl_widget.html`) served alongside billing. The React dashboard at <https://coinscope.ai/> is a separate repo and is **not** in this tree.
- `data/` - runtime funding-rate cache.
- `tests/` - billing + smoke tests at repo root. Engine-specific tests live in `coinscope_trading_engine/tests/`.
- `scripts/` - operational scripts (reconciliation, Stripe product setup, journal watchdog).
- `incidents/` - incident artifacts.
- `docs/` - developer documentation set. Start at `docs/README.md`.
- `archive/` - quarantine for duplicate snapshots, `.docx` exports, historical reports, legacy scripts, skill artifacts. Nothing here is load-bearing.

## Architecture in one picture

```
Binance USD-M Futures Testnet
        |
        v  WebSocket + REST
   Data layer  -->  5 scanners (Volume . Liquidation . FundingRate . Pattern . OrderBook)
                          |
                          v
                 ConfluenceScorer (0-100; 0-12 confluence factors depending on scorer version)
                          |
                          v
                 EntryExitCalculator (ATR entry . SL . TP1/TP2 . R:R)
                          |
                          v
                  -- RiskGate --
                  |- CircuitBreaker (daily loss . max DD . consecutive losses)
                  |- ExposureTracker (heat cap . max 3 positions)
                  |- CorrelationAnalyzer
                  |- KellyRiskController (regime-aware: bull 1.0x . chop 0.5x . bear 0.3x, hard 2% cap)
                          |
                          v
                  Alerts (Telegram . webhook) + Trade Journal
                          |
                          v
                  Binance Testnet Executor
                          |
                          v
                  Journal + equity/daily PnL + metrics exporter

Background: HMM regime (bull/bear/chop) . v3 classifier (Trending/Mean-Reverting/Volatile/Quiet) . sentiment (if configured) . scheduled retraining
```

See `docs/architecture/system-overview.md` for prose and `docs/architecture/data-flow.md` for step-by-step.

## Quick start

```bash
# 1. Enter the engine
cd coinscope_trading_engine
cp .env.example .env
# edit .env: fill in BINANCE_FUTURES_TESTNET_API_KEY and _SECRET, TELEGRAM_BOT_TOKEN, etc.

# 2. Install (Python 3.11+ required)
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt     # root requirements.txt is canonical
pip install -r requirements.txt        # engine-local pins, if present

# 3. Smoke test
python testnet_check.py

# 4. Run the engine in dry-run (scans only, no alerts sent)
python main.py --testnet --dry-run

# 5. Start the HTTP API (separate terminal)
uvicorn api:app --host 0.0.0.0 --port 8001 --reload

# 6. Hit the health check
curl http://localhost:8001/health
```

Full local loop including Docker Compose: `docs/runbooks/local-development.md`.

## Running tests

```bash
# Root billing + smoke tests
pytest tests -v

# Engine-local tests
cd coinscope_trading_engine && pytest tests -v
```

CI definition: `.github/workflows/ci.yml` (Python 3.11, pytest against both test roots).

## Key endpoints (engine API, port 8001)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness probe |
| GET | `/config` | Safe config values |
| GET | `/signals` | Recent scored signals |
| POST | `/scan` | Trigger a scan cycle |
| GET | `/positions` | Open positions + PnL |
| GET | `/exposure` | Portfolio heat + max-position usage |
| GET | `/circuit-breaker` | Current breaker state |
| POST | `/circuit-breaker/reset` | Reset a tripped breaker |
| POST | `/circuit-breaker/trip` | Manually halt trading |
| GET | `/regime` | Current regime per symbol |
| GET | `/sentiment` | Sentiment score |
| GET | `/anomaly` | Anomaly score |
| GET | `/position-size` | Preview Kelly size for a candidate |
| GET | `/correlation` | Correlation matrix |
| GET | `/journal` | Trade journal entries |
| GET | `/performance` | Aggregate performance |
| GET | `/performance/equity` | Equity curve |
| GET | `/performance/daily` | Daily PnL |
| GET | `/scale` | Scale-up manager state |
| POST | `/scale/check` | Evaluate scale-up eligibility |
| GET | `/validate` | Validation-mode checks |

Full reference: `docs/api/backend-endpoints.md`.

## Risk thresholds (project-wide, non-negotiable during validation)

| Limit | Value |
| --- | --- |
| Max drawdown | 10% |
| Daily loss limit | 5% |
| Max leverage | 20x |
| Max concurrent positions | 3 |
| Position heat cap | 80% |
| Per-trade hard cap | 2% of equity (Kelly ceiling) |

See `docs/risk/risk-framework.md` and `docs/risk/failsafes-and-kill-switches.md`.

## Technology stack (as it actually is today)

- **Language:** Python 3.11+ (venv required).
- **HTTP:** FastAPI, uvicorn, aiohttp, websockets, requests.
- **Data/ML:** numpy, pandas, scikit-learn, hmmlearn, xgboost (training), ccxt.
- **Config:** pydantic + pydantic-settings.
- **Exchange:** Binance USD-M Futures (testnet during validation). Bybit / OKX / Hyperliquid are planned, not implemented.
- **Queue:** Celery with Redis broker (`celery_app.py`, `tasks.py`).
- **Observability:** Prometheus exporter (`metrics_exporter.py`), `prometheus.yml` at repo root.
- **Persistence:** filesystem journals + Redis caches. Billing uses SQLite locally (`billing_subscriptions.db`); a Postgres store exists at `billing/pg_subscription_store.py`.
- **Infra:** Docker / Docker Compose (`docker-compose.yml`). No Kubernetes manifests in this repo - K8s is planned.
- **LLM:** not used on the hot path (see `docs/decisions/adr-0003-llm-off-hot-path.md`).

## Status of modules - implemented vs planned

| Area | State |
| --- | --- |
| Binance USD-M scanners + signal scoring | Implemented |
| Risk gate + Kelly sizing + circuit breakers | Implemented |
| Binance testnet executor | Implemented |
| HMM regime detector (bull/bear/chop) | Implemented |
| v3 regime classifier (Trending/Mean-Reverting/Volatile/Quiet) | Training pipeline implemented; inference integration partial |
| Telegram alerts | Implemented |
| Stripe billing + entitlements | Implemented (root `billing_server.py` + package `billing/`; consolidation TODO, see `docs/ops/stripe-billing.md`) |
| Trade journal + performance endpoints | Implemented |
| Prometheus metrics exporter | Implemented |
| React dashboard | Separate repo, deployed at <https://coinscope.ai/> |
| Bybit / OKX / Hyperliquid adapters | Planned |
| Kubernetes deployment | Planned |
| PyTorch models | Not used; classical ML only |

## Documentation map

Start here: **`docs/README.md`** - the index.

Highlights:

- `docs/onboarding/new-developer-guide.md` - first hour of productive work.
- `docs/onboarding/first-week-checklist.md` - first week of onboarding.
- `docs/onboarding/glossary.md` - domain vocabulary.
- `docs/architecture/system-overview.md` - how the pieces fit.
- `docs/architecture/data-flow.md` - end-to-end flow.
- `docs/api/backend-endpoints.md` - full HTTP contract.
- `docs/risk/risk-framework.md` - invariants, guarantees, escalation.
- `docs/ml/ml-overview.md` - what the ML layer does (and does not) do.
- `docs/ops/binance-adapter.md` - exchange integration details.
- `docs/runbooks/local-development.md` - how to run on your laptop.
- `docs/runbooks/daily-ops.md` - daily operating checklist.
- `docs/decisions/` - ADRs.

## Contributing

See `CONTRIBUTING.md` for branching, PR expectations, and how to add or update docs.

## License

Private. Not open source. Not authorized for redistribution.

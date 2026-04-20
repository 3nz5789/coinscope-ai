# CoinScopeAI

> AI-driven Binance USDⓈ-M Futures scanner + autonomous trading engine.
> **Capital preservation first, profit generation second.**
> Running on Binance Futures **Demo** (`demo-fapi.binance.com`) during validation.

| Service | Port | URL |
|---|---|---|
| Engine API (FastAPI + Swagger) | 8001 | <http://localhost:8001/docs> |
| React Dashboard (Vite) | 5174 | <http://localhost:5174/> |
| Static PnL Widget | 5173 | <http://localhost:5173/pnl_widget.html> |
| Stripe webhook server | 8002 | `python billing_server.py` |
| Redis | 6379 | docker: `coinscopeai-redis` |

---

## What's in this repo

```
coinscope-ai/
├── coinscope_trading_engine/    Python trading engine (FastAPI on :8001)
├── coinscopeai-dashboard/       React/Vite dashboard (in-tree, on :5174)
├── dashboard/                   Static PnL widget HTML (on :5173)
├── ml/                          v3 regime classifier pipeline
├── testnet_trader/              Standalone testnet CLI
├── scripts/                     Ops scripts (reconciliation, stripe, watchdog)
├── tests/                       Billing + smoke tests
├── billing/ + billing_server.py Stripe webhook service (port 8002, separate)
├── docs/                        Developer docs — start at docs/README.md
├── incidents/                   Incident reports + post-mortems
├── data/                        Runtime funding-rate cache
├── logs/                        Logs, journals, PnL history
│   ├── coinscope.log            structured engine log (rotated)
│   ├── journal.json             trade journal (open + closed)
│   ├── decisions.jsonl          every gate verdict (primary; PG mirror optional)
│   └── klines.sqlite            90-day rolling OHLCV store for backtests
└── archive/                     dead code, old snapshots, cleanup residue
```

---

## Architecture — decision lifecycle

```
Binance Futures Demo (trading)         Binance Futures Mainnet (signal data)
   REST demo-fapi.binance.com              WS fstream.binance.com
           │                                        │
           ▼                                        ▼
┌──────────────────────────────────────────────────────────────┐
│                        ENGINE :8001                            │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│  │ 5 scanners   │ → │ Confluence   │ → │ Entry/Exit calc  │   │
│  │  Volume      │   │ Scorer 0–100 │   │  ATR SL + TP     │   │
│  │  Pattern     │   │ + indicators │   │  R:R gate        │   │
│  │  OrderBook   │   │   bonuses    │   └───────┬──────────┘   │
│  │  FundingRate │   └──────────────┘           │              │
│  │  Liquidation │                      ┌───────▼─────────┐    │
│  └──────────────┘                      │    Risk Gate    │    │
│                                        │  ✓ Breaker       │    │
│                                        │  ✓ Exposure      │    │
│                                        │  ✓ Correlation   │    │
│                                        │  ✓ Per-symbol    │    │
│                                        │  ✓ Direction     │    │
│                                        │  ✓ MTF (opt)     │    │
│                                        └───────┬─────────┘    │
│                                                │              │
│                                   ┌────────────▼───────────┐  │
│                                   │  Autotrade executor    │  │
│                                   │  MARKET entry          │  │
│                                   │  + Algo SL/TP bracket  │  │
│                                   └────────────┬───────────┘  │
│                                                │              │
│    ┌────────────┐   ┌──────────────┐    ┌──────▼─────────┐    │
│    │ Decision   │   │ Journal      │    │ Binance        │    │
│    │ Journal    │←──┤ (trades)     │    │ Futures Demo   │    │
│    │ JSONL + PG │   │ performance  │    │ (fills here)   │    │
│    └────────────┘   └──────────────┘    └────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

See [`docs/architecture/engine-internals.md`](docs/architecture/engine-internals.md) and
[`docs/architecture/trading-pipeline.md`](docs/architecture/trading-pipeline.md) for
full module-by-module and decision-lifecycle walkthroughs.

---

## Quick start

### 1. Engine (trading + API)
```bash
cd coinscope_trading_engine
cp ../.env.example .env          # or symlink to the root .env
../venv/bin/uvicorn api:app --host 127.0.0.1 --port 8001
```

### 2. Dashboard (React/Vite)
```bash
cd coinscopeai-dashboard
pnpm install
pnpm dev --port 5174 --host 127.0.0.1
```

### 3. Redis (required for scanner cache)
```bash
docker compose up -d redis
```

Or via the launch config:
```bash
# .claude/launch.json defines "coinscope-engine" + "coinscope-dashboard"
# Both boot with Redis prerequisites assumed.
```

---

## Operational controls

| Action | How |
|---|---|
| Enable autotrade | Dashboard → Settings → Autotrade power button |
| Kill switch | Dashboard → Risk Gate → Power button (trips breaker + cancels working orders) |
| Unpause a symbol | Dashboard → Risk Gate → Per-symbol grid → Unpause button |
| Run a backtest | Dashboard → Backtest Results → Run Backtest |
| View decisions | Dashboard → Decisions (full filterable audit log) |
| Test Telegram | `curl -X POST http://127.0.0.1:8001/autotrade/test-alert` |
| Force account sync | `curl -X POST http://127.0.0.1:8001/account/sync` |
| Force historical refresh | `curl -X POST http://127.0.0.1:8001/historical/refresh` |

---

## HTTP endpoints (grouped)

| Group | Routes |
|---|---|
| System | `GET /health`, `GET /config` |
| Account | `GET /account`, `/account/balance`, `/account/positions`, `POST /account/sync` |
| Prices | `GET /prices[/{symbol}]`, `GET /liquidations?symbol=&minutes=` |
| Signals | `GET /signals`, `POST /scan`, `GET /scan/status` |
| Orders | `POST /orders`, `POST /orders/close`, `POST /orders/bracket`, `GET /orders/open`, `GET /orders/algo/open`, `DELETE /orders/{id}?symbol=` |
| Risk | `GET /positions`, `/exposure`, `/circuit-breaker`, `POST /circuit-breaker/{trip,reset}`, `GET /correlation`, `GET /position-size` |
| Autotrade | `GET /autotrade/status`, `POST /autotrade/{enable,disable,config,test-alert}`, `GET /autotrade/telegram-diagnose` |
| Decisions | `GET /decisions`, `/decisions/stats`, `/decisions/per-symbol`, `POST /decisions/unpause/{symbol}` |
| Backtest | `POST /backtest/run`, `GET /backtest/jobs[/{id}]`, `DELETE /backtest/jobs/{id}` |
| Historical | `GET /historical/stats`, `/historical/klines`, `POST /historical/backfill`, `POST /historical/refresh` |
| Intelligence | `GET /regime`, `/sentiment`, `/anomaly` |
| Journal | `GET /journal`, `/performance`, `/performance/equity`, `/performance/daily` |
| Billing (Stripe) | `GET /billing/plans`, `/billing/subscription`, `POST /billing/{checkout,portal,webhook}` |

Full OpenAPI: <http://localhost:8001/docs>

---

## Risk framework

Reading order for anyone touching `risk/`, `execution/`, or sizing:

1. [`docs/risk/risk-framework.md`](docs/risk/risk-framework.md) — philosophy + invariants
2. [`docs/risk/risk-gate.md`](docs/risk/risk-gate.md) — what the gate checks
3. [`docs/risk/position-sizing.md`](docs/risk/position-sizing.md) — Kelly pipeline
4. [`docs/risk/failsafes-and-kill-switches.md`](docs/risk/failsafes-and-kill-switches.md) — breakers

The **six invariants** are in the risk-framework doc; the engine is
audited against them in [`docs/architecture/engine-internals.md`](docs/architecture/engine-internals.md).

---

## Persistence & history

| Store | What | Where |
|---|---|---|
| Trade journal | Opened + closed trades | `logs/journal.json` (file) |
| Decision journal | Every gate verdict (signal / accept / reject / skip / etc.) | `logs/decisions.jsonl` (primary) + Postgres mirror (`DECISIONS_PG_URL`) |
| Historical klines | 90-day rolling OHLCV for BTC/ETH/SOL/BNB × 5m/15m/1h/4h | `logs/klines.sqlite` (auto-backfilled on first boot, refreshed every 15 min) |
| Live mark prices | WS `markPrice@1s` | in-memory, 2 min TTL |
| Liquidation buffer | WS `forceOrder` (mainnet signal source) | in-memory, 30 min rolling |

---

## Environment

`.env` (never committed) holds:
- Binance Futures Demo: `BINANCE_FUTURES_TESTNET_{API_KEY,API_SECRET,BASE_URL,WS_URL}`
- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (supergroup ID works; see `/autotrade/telegram-diagnose`)
- Stripe test mode: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`
- Optional: `DECISIONS_PG_URL` (Postgres DSN for remote decision mirror)
- Optional: `LIQUIDATION_FEED_WS_URL` (defaults to mainnet `wss://fstream.binance.com`)
- Scan cadence: `SCAN_INTERVAL_SECONDS` (default 10 during active demo)

See `.env.example` for the full template.

---

## Development

```bash
# Run tests
pytest tests -v                             # billing + root smoke
cd coinscope_trading_engine && pytest tests # engine-specific

# Benchmark
python coinscope_trading_engine/benchmark.py

# Verify testnet connectivity
python coinscope_trading_engine/testnet_check.py
```

CI: `.github/workflows/ci.yml` (Python 3.11, pytest against both test roots).

---

## Current status (2026-04-20)

- ✅ **Engine live on Binance Futures Demo.** Trading + WS feeds + auto-scan at 10s cadence.
- ✅ **Autotrade** gated by `LONG_ONLY`, `min_score=65`, `risk_per_trade=1%`, `5x` leverage, bracket SL/TP via Algo Order API.
- ✅ **Per-symbol circuit breaker** — auto-pauses symbols after 3 consec losses or -1.5% daily.
- ✅ **Decision journal** — every verdict persisted to JSONL (local) + Postgres (remote mirror).
- ✅ **Historical klines store** — 149k rows / 22MB covering 90 days × 4 pairs × 4 timeframes.
- ✅ **Backtester** runs offline from the local SQLite store (10× faster than REST).
- ⚠️ **MTF filter** implemented but shipped OFF — A/B test on 2026-04-20 showed it reduces PF vs no-MTF on the current scanner mix.
- 🚧 **News / macro-calendar gating** not implemented (not a blocker; scheduled for a later phase).

Best-known config (30d backtest, 2026-04-20): `LONG_ONLY · min_score=60 · ATR 1.5/3.0 · no MTF` → PF 1.05 · 38.5% WR · +3.3% return · 17.5% max DD.

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for branching, PR expectations,
and risk-framework reviewer rules.

## License

Private. Not open source. Not authorized for redistribution.

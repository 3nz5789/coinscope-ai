# CoinScopeAI — Master Context Document

**Last updated:** 2026-04-15
**Engine version:** 2.0.0
**Status:** Active development — testnet mode

---

## Project Summary

CoinScopeAI is an AI-powered Binance USD-M Futures scanner and paper-trading engine. It continuously scans perpetual pairs, scores setups using a multi-factor confluence model, calculates ATR-based entry/exit levels, sizes positions with Kelly Criterion, and dispatches alerts via Telegram or webhook. All trading is testnet-only until paper-trading validation is complete.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| API framework | FastAPI 0.110+ (Python 3.11+) |
| Task queue | Celery 5 + Redis 7 |
| Data & ML | NumPy, Pandas, scikit-learn, PyTorch, hmmlearn |
| Exchange connectivity | Binance USD-M Futures REST + WebSocket |
| Alerts | python-telegram-bot, HMAC-signed webhooks |
| Monitoring | Prometheus + Grafana |
| Storage | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy + Alembic |
| Billing | Stripe (Checkout Sessions, Customer Portal, webhooks) |
| Config | pydantic-settings + `.env` |

---

## Repository Layout

```
CoinScopeAI/
├── coinscope_trading_engine/      ← Main engine package (v2.0.0)
│   ├── main.py                    # Async engine entry point
│   ├── api.py                     # FastAPI — 26 REST endpoints
│   ├── config.py                  # Pydantic-settings + .env
│   ├── celery_app.py / tasks.py   # Distributed task workers
│   ├── data/                      # Binance REST, WebSocket, cache, normalizer
│   ├── scanner/                   # 5 parallel scanners (Volume, Liq, Funding, Pattern, OB)
│   ├── signals/                   # Indicator engine, ConfluenceScorer, entry/exit calc
│   ├── risk/                      # Circuit breaker, exposure tracker, correlation, sizer
│   ├── models/                    # HMM regime, sentiment, LSTM predictor, anomaly
│   ├── alerts/                    # Telegram, webhook, priority queue, rate limiter
│   ├── intelligence/              # FinBERT stub, whale filter, kelly sizer, multi-TF
│   ├── storage/                   # Trade journal, portfolio sync, Notion integration
│   ├── monitoring/                # Prometheus metrics exporter
│   ├── validation/                # Walk-forward backtester
│   ├── execution/                 # OrderManager — retry-aware order lifecycle
│   ├── billing/                   # Stripe billing router (plans, checkout, portal, webhook)
│   │   ├── stripe_gateway.py      # FastAPI router — 5 billing endpoints
│   │   ├── models.py              # Pydantic schemas (PlanTier, SubscriptionInfo, etc.)
│   │   └── webhooks.py            # Stripe event handlers + state persistence
│   ├── setup_stripe_products.py   # One-time Stripe product/price setup script
│   └── execution/                 # OrderManager — retry-aware order lifecycle
│   └── tests/                     # pytest suite (api, scanners, signals, risk, order_manager)
├── billing/                       # Standalone billing service (port 8002)
│   ├── webhook_handler.py         # FastAPI app — webhook receiver + subscription API
│   ├── stripe_checkout.py         # Checkout session creator
│   ├── customer_portal.py         # Portal session API (POST /portal/session, GET /portal/config)
│   ├── subscription_store.py      # SQLite-backed SubscriptionStore (CRUD + idempotency)
│   ├── pg_subscription_store.py   # Async PostgreSQL store (production path)
│   ├── entitlements.py            # Entitlements dataclass + TIER_ENTITLEMENTS lookup
│   ├── notifications.py           # BillingNotifier — Telegram alerts for billing events
│   ├── models.py                  # Pydantic schemas (SubscriptionRecord, SubscriptionTier, …)
│   ├── config.py                  # Plan registry + Price ID helpers
│   ├── migrations/
│   │   └── 001_initial_billing_tables.sql  # Postgres schema (billing schema + ENUMs)
│   └── README.md                  # Billing service quick start
├── billing_server.py              # Entry point: uvicorn billing.webhook_handler:app --port 8002
├── dashboard/
│   ├── pricing.html               # Frontend pricing page (Starter/Pro/Elite/Team)
│   └── billing_success.html       # Post-checkout success landing page
├── docs/
│   ├── BILLING_Stripe_Setup_Runbook.md    # Step-by-step Stripe setup guide
│   └── QA_BILLING_COI39_2026-04-15.md    # QA report — 80/80 tests pass
└── scripts/
    └── setup_stripe_test_products.py      # Stripe test-mode product/price creator
├── market_scanner_skill/          # Standalone Claude skill for market scanning
├── testnet_trader/                # Lightweight testnet order executor
├── skills/                        # Claude skills (market scanner, risk gate, etc.)
├── docker-compose.yml             # Full production stack
├── README.md                      # Primary documentation
├── CLAUDE.md                      # Claude-specific instructions
├── AUDIT_REPORT.md                # Bug audit (2026-04-02): 16 bugs, 15 fixed
├── HEALTH_REPORT_2026-04-04.md    # System health check
└── CODE_REVIEW_2026-04-05.md      # Architecture code review (3 CRITICAL open)
```

---

## Signal Pipeline

```
Binance REST / WebSocket
       ↓
5 Parallel Scanners (per symbol, per cycle)
  ├── VolumeScanner        — volume spike ≥ 3× 20-bar avg
  ├── LiquidationScanner   — long/short liquidation dominance
  ├── FundingRateScanner   — extreme positive/negative funding
  ├── PatternScanner       — engulfing, hammer, doji reversals
  └── OrderBookScanner     — bid/ask imbalance ≥ 60/40
       ↓
ConfluenceScorer (0–100)
  — weighted scanner hits + multi-scanner bonuses + regime match
  — threshold: 65 (configurable MIN_CONFLUENCE_SCORE)
       ↓
EntryExitCalculator
  — entry: close ± ATR × 0.3
  — SL: ± ATR × 1.5  |  TP1: ± ATR × 1.5  |  TP2: ± ATR × 3.0
  — min R:R: 1.5
       ↓
RiskGate (CircuitBreaker + ExposureTracker + CorrelationAnalyzer)
       ↓
AlertQueue → TelegramNotifier + WebhookDispatcher
       ↓
ML Background (Celery workers)
  ├── HMM RegimeDetector    — 4-state Gaussian HMM (Bull/Bear/Chop/Volatile)
  ├── SentimentAnalyzer     — composite sentiment −100 to +100
  ├── LSTM PricePredictor   — next-candle direction (PyTorch)
  └── AnomalyDetector       — 5-method anomaly suite
```

---

## API Reference (v2.0.0)

Base URL: `http://localhost:8001` | Docs: `http://localhost:8001/docs`

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness probe — version, testnet flag |
| GET | `/config` | Safe (non-secret) runtime config values |

### Signals
| Method | Path | Description |
|--------|------|-------------|
| POST | `/scan` | Trigger scan for requested pairs; body: `{pairs, timeframe, limit}` |
| GET | `/signals` | Cached results from last scan cycle |

### Risk
| Method | Path | Description |
|--------|------|-------------|
| GET | `/positions` | All open positions with unrealised PnL |
| GET | `/exposure` | Portfolio exposure summary, daily P&L |
| GET | `/circuit-breaker` | Breaker state + trip history |
| POST | `/circuit-breaker/reset` | Manually reset a tripped breaker |
| POST | `/circuit-breaker/trip` | Manually halt trading; body: `{reason}` |
| GET | `/position-size` | Kelly / fixed-fractional size; params: `symbol, entry, stop_loss, account_balance, win_rate?, avg_rr?` |
| GET | `/correlation` | Pairwise Pearson matrix; params: `symbols` (comma-sep), `timeframe`, `limit` |

### Intelligence
| Method | Path | Description |
|--------|------|-------------|
| GET | `/regime` | HMM market regime; params: `symbol, timeframe, limit` |
| GET | `/sentiment` | Composite sentiment score; params: `symbol` |
| GET | `/anomaly` | Anomaly detection report; params: `symbol, timeframe, limit` |

### Journal
| Method | Path | Description |
|--------|------|-------------|
| GET | `/journal` | Recent trades from persistent journal; param: `days` (1–90, default 7) |
| GET | `/performance` | Aggregate performance stats + scale profile |
| GET | `/performance/daily` | Today's P&L summary |
| GET | `/performance/equity` | Full timestamped equity curve; params: *(none)* |

### Scale Management
| Method | Path | Description |
|--------|------|-------------|
| GET | `/scale` | Current scaling profile (risk tier, position limits) |
| POST | `/scale/check` | Evaluate scale-up eligibility; params: `trades, sharpe` |

### Validation
| Method | Path | Description |
|--------|------|-------------|
| GET | `/validate` | Walk-forward backtest on historical data; params: `symbol, timeframe, limit` |

### Billing *(expanded 2026-04-15)*
| Method | Path | Description |
|--------|------|-------------|
| GET | `/billing/plans` | All pricing tiers with features and amounts |
| GET | `/billing/subscription` | Current subscription status for authenticated customer |
| POST | `/billing/checkout` | Create a Stripe Checkout Session; body: `{tier, customer_email, customer_name?}` |
| POST | `/billing/portal` | Legacy alias → creates portal session; body: `{customer_email}` |
| POST | `/billing/webhook` | Stripe webhook receiver (HMAC-verified; hidden from Swagger docs) |

---

## Billing Service (Standalone — port 8002)

A separate FastAPI app (`billing/webhook_handler.py`) runs on port 8002. It handles Stripe webhooks, exposes subscription management endpoints, and persists state to SQLite (dev) or PostgreSQL (prod) via `SubscriptionStore` / `PgSubscriptionStore`. The checkout page frontend (`dashboard/pricing.html`) calls this service directly.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/billing/health` | Health probe — Stripe config + DB status |
| GET | `/billing/plans` | Plan list with features and Stripe Price ID status |
| GET | `/billing/subscriptions` | List all active/trialing subscriptions |
| POST | `/billing/checkout/session` | Create Checkout Session; body: `{tier, interval, customer_email?}` |
| POST | `/billing/portal/session` | Create Customer Portal session; body: `{customer_id?, email?, return_url?}` |
| GET | `/billing/portal/config` | Check Stripe portal configuration status |
| POST | `/billing/webhook` | Stripe event receiver (HMAC-verified, idempotent) |

```bash
# Run standalone billing server (recommended)
uvicorn billing.webhook_handler:app --host 0.0.0.0 --port 8002

# Or via convenience entry point
python billing_server.py
```

### Pricing Tiers & Entitlements

| Feature | Starter ($19/mo) | Pro ($49/mo) | Elite ($99/mo) | Team ($299/mo) |
|---------|:-:|:-:|:-:|:-:|
| Max symbols | 5 | 25 | Unlimited | Unlimited |
| Scan interval | 4h | 1h | 15min | 15min |
| Alerts/day | 3 | 20 | Unlimited | Unlimited |
| Journal retention | 30 days | Unlimited | Unlimited | Unlimited |
| Telegram alerts | ✅ | ✅ | ✅ | ✅ |
| Email alerts | — | ✅ | ✅ | ✅ |
| ML signals v3 | — | ✅ | ✅ | ✅ |
| Regime detection | — | ✅ | ✅ | ✅ |
| Kelly sizing | — | ✅ | ✅ | ✅ |
| Walk-forward validation | — | ✅ | ✅ | ✅ |
| API access | — | — | ✅ (300 rpm) | ✅ (1000 rpm) |
| TradingView webhooks | — | — | ✅ | ✅ |
| CVD/whale signals | — | — | ✅ | ✅ |
| Alpha decay monitoring | — | — | ✅ | ✅ |
| Multi-exchange | — | — | ✅ | ✅ |
| Max team seats | 1 | 1 | 3 | 10 |
| Priority support | — | — | ✅ | ✅ |
| SLA / dedicated onboarding | — | — | — | ✅ |

Entitlements are enforced at runtime via `billing/entitlements.py` (`Entitlements.for_customer(store, customer_id)` for live DB lookup; `Entitlements.for_tier(tier)` for static/offline use).

### One-Time Stripe Setup

```bash
cd coinscope_trading_engine
python setup_stripe_products.py          # creates products + prices in Stripe Test Mode
python setup_stripe_products.py --live   # live mode (real charges)
python setup_stripe_products.py --dry-run
```

Copy the printed Price IDs into `.env`.

### Webhook Events Handled

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Activates subscription, persists to DB, sends Telegram notification |
| `customer.subscription.updated` | Syncs plan tier and renewal date, notifies on tier change |
| `customer.subscription.deleted` | Marks subscription as canceled, revokes entitlements |
| `invoice.payment_succeeded` | Confirms renewal, updates period end, logs invoice |
| `invoice.payment_failed` | Flags `past_due`, sends Telegram alert |

All handlers are **idempotent** — duplicate Stripe event deliveries are deduplicated via the `webhook_events` table. Bug fix: `STRIPE_WEBHOOK_SECRET` is now read lazily per-request (not frozen at import time).

---

## Risk Management

### Circuit Breaker Triggers (default values)
| Trigger | Default | Env Var |
|---------|---------|---------|
| Daily loss | 2% of equity | `MAX_DAILY_LOSS_PCT` |
| Drawdown | 5% peak-to-trough | `MAX_DRAWDOWN_PCT` |
| Consecutive losses | 5 trades | `MAX_CONSECUTIVE_LOSSES` |
| Rapid loss (5 min window) | 1.5% | `RAPID_LOSS_PCT` |

### Position Sizing
- Default: **1% fixed-fractional** risk per trade
- Optional: **half-Kelly** when `win_rate` + `avg_rr` are supplied to `/position-size`
- Max leverage cap: configurable via `MAX_LEVERAGE`

### Correlation Gate
Blocks a new signal if any open position in the same direction has Pearson r ≥ 0.80 over the last 50 bars.

---

## Key Environment Variables

### Engine

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BINANCE_TESTNET_API_KEY` | ✅ | — | From testnet.binancefuture.com |
| `BINANCE_TESTNET_API_SECRET` | ✅ | — | From testnet.binancefuture.com |
| `TESTNET_MODE` | — | `true` | Route all traffic through testnet |
| `TELEGRAM_BOT_TOKEN` | — | *(blank)* | Blank = alerts disabled (log-only) |
| `SCAN_PAIRS` | — | 8 pairs | Comma-separated Binance Futures symbols |
| `MIN_CONFLUENCE_SCORE` | — | `65` | Minimum score to emit a signal |
| `SCAN_INTERVAL_SECONDS` | — | `5` | Scanner cycle frequency |
| `MAX_DAILY_LOSS_PCT` | — | `2.0` | Daily loss circuit breaker |
| `REDIS_HOST` | — | `localhost` | Redis hostname |
| `CORS_ORIGINS` | — | `localhost:*` | Restrict before any network-exposed deploy |

### Billing (Stripe)

| Variable | Required | Description |
|----------|----------|-------------|
| `STRIPE_SECRET_KEY` | ✅ | `sk_test_...` from Stripe Dashboard |
| `STRIPE_PUBLISHABLE_KEY` | ✅ | `pk_test_...` — passed to frontend |
| `STRIPE_WEBHOOK_SECRET` | ✅ | `whsec_...` from `stripe listen` output |
| `STRIPE_PRICE_STARTER_MONTHLY` | ✅ | `price_...` — created by `setup_stripe_products.py` |
| `STRIPE_PRICE_STARTER_ANNUAL` | — | Annual price ID (20% discount) |
| `STRIPE_PRICE_PRO_MONTHLY` | ✅ | |
| `STRIPE_PRICE_PRO_ANNUAL` | — | |
| `STRIPE_PRICE_ELITE_MONTHLY` | ✅ | |
| `STRIPE_PRICE_ELITE_ANNUAL` | — | |
| `STRIPE_PRICE_TEAM_MONTHLY` | ✅ | |
| `STRIPE_PRICE_TEAM_ANNUAL` | — | |
| `BILLING_SUCCESS_URL` | — | Redirect after successful checkout |
| `BILLING_CANCEL_URL` | — | Redirect on checkout cancel |

---

## Open Issues & Tech Debt

### Critical (blocking correct behavior)
1. **`signal_generator.py`** — `ScannerResult` accessed as dict (`res["signal"]`) → raises `TypeError` on first use. Also `sys.path.insert` hack and `scanner/` vs `scanners/` module duplication.
2. **`pattern_scanner.py`** — imports private helpers (`_candle_to_dict`, `_dict_to_candle`) directly from `volume_scanner`; breaks on any refactor.

### High Priority
3. **`alert_queue.py`** — CRITICAL alerts can be silently dropped when queue is full (200 items of lower priority). Add eviction or bypass.
4. **`rate_limiter.py`** — uses `threading.Lock` in async context; potential deadlock. Replace with `asyncio.Lock`.
5. **`entry_exit_calculator.py`** — SHORT structure SL uses `max(swing_highs)` instead of `min(swing_highs)`; places stop too far, degrades R:R.
6. **`cache_manager.py`** — `get_all_signals()` uses Redis `KEYS` (O(N) blocking); replace with `SCAN`.
7. **`telegram_alerts.py`** (root legacy) — uses synchronous `requests` in async context; blocks event loop up to 5s per call.

### Billing (pending)
8. **Subscription fulfilment stub** — `_handle_checkout_completed` in `billing/stripe_checkout.py` logs the event but does not write to a user DB or Notion. Needs actual provisioning logic once a users table / Notion DB is wired up.
9. **Customer Portal** — `GET /billing/portal` endpoint requires a Stripe Customer Portal configuration to be saved in the Stripe Dashboard before use.

### Pending Manual Cleanup
- **BUG-16**: Two conflicting `whale_signal_filter` files in `intelligence/`. Delete the `(1)` variant:
  ```bash
  rm "coinscope_trading_engine/intelligence/whale signal filter (1).py"
  ```

### Security Notes
- CORS currently allows `"*"` (plus localhost origins) — must be restricted before any non-local deployment.
- Grafana default password (`coinscopeai`) must be changed before network exposure.
- Telegram bot token can leak into logs via `self._base` URL string in `telegram_notifier.py`.

---

## Observability Stack

| Service | URL | Default Credentials |
|---------|-----|-------------------|
| FastAPI docs (Swagger) | http://localhost:8001/docs | — |
| FastAPI redoc | http://localhost:8001/redoc | — |
| Billing API docs | http://localhost:8002/docs | — |
| Celery Flower | http://localhost:5555 | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / coinscopeai |
| Prometheus metrics exporter | http://localhost:9000/metrics | — |

15 Prometheus metrics exported. Import `monitoring/grafana_dashboard.json` once signal history exists.

---

## Development Status

| Feature | Status |
|---------|--------|
| 5-scanner confluence pipeline | ✅ Complete |
| ATR-based entry/exit calculator | ✅ Complete |
| CircuitBreaker + ExposureTracker | ✅ Complete |
| HMM regime detector (4-state) | ✅ Complete |
| Sentiment analyzer | ✅ Complete |
| LSTM price predictor | ✅ Complete |
| Anomaly detector (5-method) | ✅ Complete |
| Trade journal + performance stats | ✅ Complete |
| Scale-up manager | ✅ Complete |
| Walk-forward validation | ✅ Complete |
| OrderManager (retry-aware execution) | ✅ Complete — added 2026-04-10 |
| Stripe billing integration | ✅ Complete (test mode) — added 2026-04-14 |
| Notion integration | ✅ Complete (optional) |
| Entitlements engine (per-tier feature gates) | ✅ Complete — added 2026-04-15 |
| Customer Portal integration | ✅ Complete (test mode) — added 2026-04-15 |
| FinBERT sentiment (real model) | 🔄 Stub only — HuggingFace integration pending |
| Billing fulfilment (user DB write) | ✅ Complete — SQLite store + Postgres store, idempotent |
| Live mainnet support | ❌ Pending paper-trading validation |
| Grafana dashboard JSON | ❌ Pending |
| Multi-exchange (OKX, Bybit) | ❌ Roadmap |
| Web UI (React signal table) | ❌ Roadmap |

---

## Recommended Launch Sequence

1. `python testnet_check.py` — 7-step connectivity smoke test
2. `python main.py --testnet --dry-run` — scan only, no alerts
3. Open Grafana at `:3000` — confirm metrics flowing
4. Validate 50–100 signals against actual price moves
5. Enable Telegram via `TELEGRAM_BOT_TOKEN` in `.env`
6. `docker compose up celery-default celery-ml` — enable ML workers
7. Remove `--dry-run` only after step 4 is satisfying

To enable billing:
1. Run `python coinscope_trading_engine/setup_stripe_products.py` to create Stripe products
2. Copy Price IDs into `.env`
3. Run `stripe listen --forward-to localhost:8002/billing/webhook` for local webhook testing
4. Set `STRIPE_WEBHOOK_SECRET` from the `whsec_...` printed by `stripe listen`

---

*CoinScopeAI is a research and paper-trading tool. It does not constitute financial advice.*

<div align="center">

# CoinScopeAI

**Regime-aware, risk-first trading intelligence for USDT-perpetual crypto futures.**

[![CI](https://github.com/3nz5789/CoinScopeAI/actions/workflows/ci.yml/badge.svg)](https://github.com/3nz5789/CoinScopeAI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-P0%20testnet%20validation-orange)](#validation-phase-freeze)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/engine-FastAPI-009688)](https://fastapi.tiangolo.com)

[Dashboard](https://app.coinscope.ai) · [API Docs](https://api.coinscope.ai/docs) · [Linear](https://linear.app/coinscopeai) · [Notion](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) · [Disclosures](https://app.coinscope.ai/legal)

</div>

---

## What is CoinScopeAI?

CoinScopeAI is an AI-driven trading intelligence system for Binance USDT-M perpetual futures. It scans the market, scores signal candidates with a multi-factor confluence model, gates every candidate through a layered risk engine, and delivers actionable alerts via Telegram — without placing trades autonomously.

**It is:**
- A signal scoring and regime-aware risk gate engine (Scanner → HMM + v3 classifier → Kelly sizer)
- A capital-preservation system with automatic circuit breakers and a manual kill switch
- A Telegram-native alert companion (`@ScoopyAI_bot`) with per-signal regime and confidence context
- A FastAPI engine serving a React dashboard at `app.coinscope.ai`

**It is not:**
- An auto-trading bot or fund manager
- A signal-selling or copy-trading service
- Investment advice of any kind

> **P0 validation phase active — May 2026.** The engine runs on **Binance Testnet only**. Real-capital trading is gate-locked behind the [Production Candidate Criteria v2 §8](#validation-phase-freeze) readiness checklist.

---

## Architecture

```
┌─────────────────────────────┐
│      Binance Futures        │  testnet today · mainnet gated by PCC v2 §8
│   REST + WebSocket streams  │
└──────────────┬──────────────┘
               │ OHLCV · OI · funding · liquidations · CVD
        ┌──────┴──────┐
        │   Adapter   │  normalises · rate-limits · reconnects · HMAC-signs
        └──────┬──────┘
               │
   ┌───────────┼────────────┐
   ▼           ▼            ▼
┌────────┐ ┌────────┐ ┌──────────────┐
│Scanner │ │Regime  │ │  Market data │
│multi-TF│ │HMM+v3  │ │  cache       │
└───┬────┘ └───┬────┘ └──────┬───────┘
    └──────┬───┘             │
           ▼                 │
     ┌──────────┐◀───────────┘
     │  Scorer  │  confluence 0–100 · per-signal label
     └────┬─────┘
          ▼
   ┌─────────────┐
   │  Risk Gate  │  regime · heat · corr · daily loss · drawdown · circuit breakers · kill switch
   └──────┬──────┘
          ▼
   ┌─────────────┐
   │   Executor  │  → Binance Testnet (mainnet gated by PCC v2 §8)
   └──────┬──────┘
          ▼
   ┌─────────────┐     ┌──────────────────────────────────────────┐
   │   Journal   │◀───▶│  FastAPI engine  ·  http://localhost:8001  │
   └─────────────┘     │  /scan  /risk-gate  /position-size        │
                       │  /regime/:symbol  /performance  /journal   │
                       └─────────────────┬────────────────────────┘
                                         ▼
                              ┌────────────────────┐
                              │  React Dashboard   │
                              │  app.coinscope.ai  │
                              └────────────────────┘
```

Full architecture: [`docs/architecture/architecture.md`](docs/architecture/architecture.md)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Engine API | Python 3.11+ · FastAPI · Uvicorn |
| Task queue | Celery · Redis |
| Database | PostgreSQL (prod) · SQLite (local dev) |
| ML / Signals | Scikit-learn · LightGBM · hmmlearn (HMM regime classifier) |
| Exchange | CCXT — Binance USDT-M Testnet |
| Dashboard | React 18 · TypeScript · Vite · Tailwind CSS (OKLCH design system v3) |
| Alerts | Telegram Bot API (`@ScoopyAI_bot`) |
| Billing | Stripe |
| Infra | Docker Compose · DigitalOcean SGP1 · GitHub Actions |
| Monitoring | Prometheus · structured JSON logging |

---

## Repository Structure

```
CoinScopeAI/
│
├── engine/                     Core trading engine
│   ├── api.py                  FastAPI app + router registration
│   ├── core/                   Config, shared state, base classes
│   ├── exchange/               Binance REST + WebSocket adapter
│   ├── integrations/           Exchange integrations (Binance primary)
│   ├── signals/                Multi-factor confluence scoring pipeline
│   ├── monitoring/             Health checks, Prometheus metrics
│   └── dashboard/              Dashboard BFF endpoints
│
├── apps/                       Application layer
├── backend/                    Backend services (auth, billing, onboarding)
├── services/                   Data ingestion pipelines (OHLCV, OI, funding)
├── strategies/                 Strategy definitions and offline backtests
│
├── risk_management/            Risk gate + position sizer + circuit breakers
│   ├── risk_gate.py            Pre-trade gate: regime, heat, corr, daily loss, drawdown
│   ├── kelly_sizer.py          Fractional Kelly (0.25x) with 2% hard cap + regime multiplier
│   ├── circuit_breakers.py     Daily loss, max drawdown, consecutive-loss breakers
│   └── kill_switch.py          Manual halt — persists across restarts
│
├── frontend/                   React 18 dashboard (Vite + Tailwind + OKLCH tokens)
│
├── configs/
│   ├── environments/
│   │   ├── development.yaml    Local dev defaults
│   │   ├── staging.yaml        Testnet staging defaults
│   │   └── production.yaml     Production defaults (gated)
│   └── logging.yaml            Structured JSON log config
│
├── scripts/
│   ├── drift_detector.py           Cross-doc canonical token consistency check
│   ├── risk_threshold_guardrail.py Codebase-wide threshold violation scanner
│   ├── daily_status.sh             Morning engine brief (polls all 6 endpoints)
│   ├── sync_verify.py              Cross-platform structure verifier
│   ├── auto_sync.py                Session-end git + drift + guardrail runner
│   └── setup_github_labels.py      GitHub label setup (27 labels — needs classic PAT)
│
├── docs/
│   ├── architecture/
│   │   ├── architecture.md              Full system architecture v5 (canonical)
│   │   └── design-system-manifest.md   OKLCH design tokens v3
│   ├── decisions/
│   │   ├── adr-0001-fastapi-and-uvicorn.md
│   │   ├── adr-0002-redis-celery-for-workers.md
│   │   └── adr-0003-llm-off-hot-path.md
│   ├── risk/
│   │   ├── risk-framework.md            Risk philosophy + 6 invariants (required reading)
│   │   ├── risk-gate.md                 Gate logic + full rejection taxonomy
│   │   ├── position-sizing.md           Kelly pipeline — 6 steps, all non-increasing
│   │   └── failsafes-and-kill-switches.md
│   ├── runbooks/
│   │   ├── daily-ops.md
│   │   ├── local-development.md
│   │   ├── digitalocean-deployment.md   Canonical VPS deployment guide
│   │   ├── troubleshooting.md
│   │   └── release-checklist.md
│   └── ml/
│       ├── regime-detection.md          HMM + v3 classifier architecture
│       └── confidence-scoring.md
│
├── tests/
│   ├── test_ci_smoke.py        15 CI smoke checks — run on every push to main
│   └── test_risk_gate.py       Risk gate unit tests
│
├── infra/                      Docker + deployment manifests
│
├── .github/
│   ├── workflows/ci.yml        Tests (15 smoke) + security scan (ubuntu-22.04)
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   ├── strategy_change.md  Required for any risk/gate/signal/ML changes
│   │   └── config.yml
│   └── PULL_REQUEST_TEMPLATE.md
│
├── coinscope.env.example       Canonical env template — thresholds locked PCC v2 §8
├── pyproject.toml              ruff · black · pytest config
├── docker-compose.yml          Local + VPS stack
├── Makefile                    make dev · make test · make lint · make guardrail
├── requirements.txt            Root Python dependencies
├── CLAUDE.md                   AI operator prompt — canonical thresholds + voice
├── CONTRIBUTING.md             Contribution rules + 2-reviewer policy
├── CODEOWNERS                  Auto-review assignments by path
└── SECURITY.md                 Vulnerability disclosure policy
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Binance Testnet API keys — [testnet.binancefuture.com](https://demo-fapi.binance.com)

### Setup

```bash
git clone https://github.com/3nz5789/CoinScopeAI.git
cd CoinScopeAI

python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp coinscope.env.example .env
# Required: BINANCE_FUTURES_TESTNET_API_KEY, BINANCE_FUTURES_TESTNET_API_SECRET
# Optional: TELEGRAM_BOT_TOKEN, NOTION_TOKEN, STRIPE_SECRET_KEY

docker compose up -d redis postgres
uvicorn engine.api:app --reload --port 8001

curl http://localhost:8001/health
curl http://localhost:8001/config | python3 -m json.tool
```

Full guide: [`docs/runbooks/local-development.md`](docs/runbooks/local-development.md)

### First scan

```bash
curl http://localhost:8001/scan | python3 -m json.tool
curl http://localhost:8001/risk-gate | python3 -m json.tool
curl http://localhost:8001/regime/BTCUSDT | python3 -m json.tool
```

---

## Engine API

Base URL: `http://localhost:8001` (dev) · `https://api.coinscope.ai` (prod)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service liveness |
| `/ready` | GET | All adapters and dependencies healthy |
| `/config` | GET | Running configuration + locked thresholds |
| `/scan` | GET | Signal scan — scored candidates across tracked symbols |
| `/risk-gate` | GET | Gate state: daily loss budget, drawdown, circuit breaker, kill switch |
| `/position-size` | POST | Kelly-fractional size for a given candidate |
| `/regime/{symbol}` | GET | HMM regime label + confidence score |
| `/journal` | GET | Append-only trade + gate-decision log |
| `/performance` | GET | Rolling P&L: win rate, profit factor, max drawdown |
| `/kill-switch` | POST | Engage or disengage manual kill switch |
| `/circuit-breaker/reset` | POST | Reset a tripped breaker (written reason required) |

---

## Canonical Risk Thresholds

Locked **2026-05-01** via PCC v2 §8. Enforced by `scripts/risk_threshold_guardrail.py` on every CI run.

| Threshold | Value | Config var |
|---|---|---|
| Max leverage | **10x** per position | `MAX_LEVERAGE=10` |
| Max open positions | **5** concurrent | `MAX_OPEN_POSITIONS=5` |
| Max drawdown | **10%** from peak equity | `max_drawdown_pct: 0.10` |
| Daily loss limit | **5%** rolling 24h | `max_daily_loss_pct: 0.05` |
| Position heat cap | **80%** deployed capital | `POSITION_HEAT_CAP_PCT=80` |
| Per-trade size cap | **2%** of equity | `KELLY_HARD_CAP_PCT=2` |

> These values are immutable during P0 validation. Any PR that changes them is blocked — see [Validation Phase Freeze](#validation-phase-freeze).

---

## Regime System

| Regime | Kelly multiplier | Description |
|---|---|---|
| **Trending** | 1.0x | Strong directional momentum — trend-following signals favoured |
| **Mean-Reverting** | 0.5x | Range-bound — oscillators and S/R levels favoured |
| **Volatile** | 0.3x | High fluctuations — higher score floor, smaller sizes |
| **Quiet** | 0.3x | Low vol/volume — tighter slippage tolerances |

---

## Key Invariant

> If the risk gate, executor, or adapter is in an uncertain state, the engine **halts — it never guesses**.

Every circuit breaker, kill switch, and rejection path enforces this invariant. See [`docs/risk/risk-framework.md`](docs/risk/risk-framework.md) for all 6 invariants.

---

## Telegram Bot

**Handle:** `@ScoopyAI_bot` — alert threshold: confluence score >= 8.0

| Command | Description |
|---|---|
| `/scan` | On-demand market scan |
| `/performance` | Current P&L snapshot |
| `/risk-gate` | Gate state and daily budget remaining |

---

## Running Tests

```bash
pytest -x -q tests/
pytest --cov=engine --cov-report=term-missing

python3 scripts/drift_detector.py
python3 scripts/risk_threshold_guardrail.py
python3 scripts/sync_verify.py
```

---

## Architecture Decision Records

| ADR | Decision | Status |
|---|---|---|
| [ADR-0001](docs/decisions/adr-0001-fastapi-and-uvicorn.md) | FastAPI + Uvicorn as engine framework | Accepted |
| [ADR-0002](docs/decisions/adr-0002-redis-celery-for-workers.md) | Redis + Celery for async task queue | Accepted |
| [ADR-0003](docs/decisions/adr-0003-llm-off-hot-path.md) | LLM calls prohibited on the hot path | Accepted |

---

## Validation Phase Freeze

**P0 validation runs through ~May 31, 2026.** These changes are blocked:

| Blocked | Why |
|---|---|
| Any canonical risk threshold change | Invalidates the validation cohort |
| Setting `BINANCE_TESTNET=false` | Real-capital gate is locked |
| Removing or bypassing any circuit breaker | Safety regression |
| Retraining or replacing ML artifacts mid-run | Changes signal distribution |
| Changing order submission semantics | Execution integrity |

If your PR touches any of the above, close it and open a `strategy_change` issue instead.

---

## Project Tracking

| Platform | Link |
|---|---|
| Issues & sprints | [linear.app/coinscopeai](https://linear.app/coinscopeai) |
| Ops knowledge base | [Notion — CoinScopeAI OS](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) |
| Business docs | [Google Drive](https://drive.google.com/drive/folders/1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8) |
| Dashboard | [app.coinscope.ai](https://app.coinscope.ai) |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Two reviewers required for changes to `risk_management/`, `engine/integrations/`, `coinscope.env.example`, `CLAUDE.md`, or `docker-compose.yml`.

---

## License

MIT — see [`LICENSE`](LICENSE).

> **Disclaimer:** CoinScopeAI is a risk management and signal intelligence tool. It does not provide investment advice, manage funds, or place trades autonomously. All trading decisions are made solely by the operator. See [app.coinscope.ai/legal](https://app.coinscope.ai/legal) for full disclosures.

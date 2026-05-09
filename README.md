<div align="center">

# CoinScopeAI

**AI-powered crypto futures trading intelligence — capital preservation first.**

[![CI](https://github.com/3nz5789/CoinScopeAI/actions/workflows/ci.yml/badge.svg)](https://github.com/3nz5789/CoinScopeAI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-testnet%20validation-orange)](https://linear.app/coinscopeai)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/engine-FastAPI-009688)](https://fastapi.tiangolo.com)

[Dashboard](https://app.coinscope.ai) · [API](https://api.coinscope.ai) · [Linear](https://linear.app/coinscopeai) · [Notion](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) · [Legal](https://app.coinscope.ai/legal)

</div>

---

## What is CoinScopeAI?

CoinScopeAI is a regime-aware, risk-first trading intelligence engine for USDT-perpetual crypto futures. It scans Binance Futures for high-probability setups, gates every candidate through a multi-layer risk engine, and delivers actionable alerts via Telegram — without placing trades autonomously.

**It is:**
- A signal scoring and risk gate engine (FixedScorer → HMM regime → Kelly sizer)
- A capital-preservation system that halts itself when drawdown limits are hit
- A Telegram-native alert system (`@ScoopyAI_bot`) with real-time regime awareness

**It is not:**
- An auto-trading bot or execution system that trades on your behalf
- An investment advice product or fund manager
- A signal-selling or copy-trading service

> **Validation phase active.** Engine runs on **Binance Testnet only**. Real-capital trading is gate-locked behind the Production Candidate Criteria v2 §8 readiness checklist.

---

## Architecture

```
            ┌─────────────────────┐
            │   Binance Futures   │  testnet today · mainnet gated
            │  REST + WebSocket   │
            └──────────┬──────────┘
                       │
                ┌──────┴──────┐
                │   Adapter   │  normalizes · reconnects · signs
                └──────┬──────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     ┌────────┐   ┌────────┐   ┌────────────┐
     │Scanner │   │Regime  │   │Market data │
     │        │   │HMM+v3  │   │cache       │
     └───┬────┘   └───┬────┘   └─────┬──────┘
         └─────┬──────┘              │
               ▼                     │
          ┌─────────┐◀───────────────┘
          │ Scorer  │  confluence score 0–100
          └────┬────┘
               ▼
        ┌────────────┐
        │ Risk Gate  │  regime · heat · daily loss · circuit breakers
        └─────┬──────┘
              ▼
        ┌────────────┐
        │ Executor   │  orders → Binance Testnet
        └─────┬──────┘
              ▼
         ┌─────────┐        ┌──────────────────────────────┐
         │ Journal │◀──────▶│  FastAPI :8001               │
         └─────────┘        │  /scan /risk-gate /regime    │
                            │  /journal /performance       │
                            └──────────────┬───────────────┘
                                           ▼
                              ┌────────────────────────┐
                              │  Dashboard             │
                              │  app.coinscope.ai      │
                              └────────────────────────┘
```

Full architecture: [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Engine API | Python 3.11+ · FastAPI · Uvicorn |
| Task queue | Celery · Redis |
| Database | PostgreSQL (billing · journal) · SQLite (local dev) |
| ML / Signals | Scikit-learn · LightGBM · HMM regime classifier (hmmlearn) |
| Exchange | CCXT — Binance USDT-M Testnet |
| Dashboard | React 18 · TypeScript · Vite · Tailwind CSS (OKLCH) |
| Alerts | Telegram Bot API (`@ScoopyAI_bot`) |
| Billing | Stripe |
| Infra | Docker Compose · DigitalOcean SGP1 · GitHub Actions |
| Monitoring | Prometheus · structured JSON logging |

---

## Repository Structure

```
CoinScopeAI/
│
├── engine/                         Core trading engine
│   ├── __init__.py
│   ├── api.py                      FastAPI router registration
│   ├── core/                       Shared config, state, base classes
│   ├── exchange/                   Binance adapter (REST + WebSocket)
│   ├── integrations/               Exchange integrations (Binance primary, OKX fallback)
│   ├── monitoring/                 Health checks, metrics
│   ├── signals/                    Signal scoring pipeline
│   └── dashboard/                  Dashboard BFF endpoints
│
├── apps/                           Application layer
│   ├── core/                       Shared application core
│   ├── exchange/                   Exchange connectivity
│   ├── integrations/               Integration layer
│   ├── monitoring/                 Observability
│   ├── signals/                    Signal pipeline
│   └── dashboard/                  Dashboard application
│
├── backend/                        Backend services
├── services/                       Microservices
├── strategies/                     Trading strategies
├── risk_management/                Risk gate + position sizing
├── frontend/                       React dashboard (Vite + Tailwind)
├── infra/                          Docker + deployment
├── configs/                        Configuration files
├── scripts/                        Operator scripts
│   ├── drift_detector.py           Cross-doc token consistency checker
│   ├── risk_threshold_guardrail.py Codebase-wide threshold validator
│   ├── daily_status.sh             Morning engine brief (6 endpoints)
│   ├── sync_verify.py              Cross-platform structure verifier
│   ├── auto_sync.py                Session-end auto-sync engine
│   └── setup_github_labels.py      GitHub label management (27 labels)
├── docs/                           Technical documentation
│   ├── architecture/               System overview, component map, design system
│   │   ├── system-overview.md      Architecture diagram + responsibility boundaries
│   │   ├── architecture.md         Architecture v5 (canonical)
│   │   ├── design-system-manifest.md  Design tokens v3
│   │   └── component-map.md        Component breakdown
│   ├── decisions/                  Architecture Decision Records
│   │   ├── adr-0001-fastapi-and-uvicorn.md
│   │   ├── adr-0002-redis-celery-for-workers.md
│   │   └── adr-0003-llm-off-hot-path.md
│   ├── risk/                       Risk framework documentation
│   │   ├── risk-framework.md       Risk philosophy + invariants
│   │   ├── risk-gate.md            Gate logic
│   │   ├── position-sizing.md      Kelly pipeline
│   │   └── failsafes-and-kill-switches.md
│   ├── runbooks/                   Operational runbooks
│   │   ├── daily-ops.md
│   │   ├── local-development.md
│   │   ├── digitalocean-deployment.md
│   │   └── release-checklist.md
│   └── ml/                         ML documentation
│       ├── regime-detection.md
│       └── confidence_scoring_baseline.md
├── tests/                          Test suite
├── .github/
│   ├── workflows/ci.yml            Lint · test · security scan
│   ├── ISSUE_TEMPLATE/             Bug report, feature request
│   └── pull_request_template.md
├── .env.example                    Canonical env template
├── CLAUDE.md                       AI operator instructions + thresholds
├── CONTEXT_PRIMER.md               Session on-ramp for AI operators
├── CONTRIBUTING.md                 Contribution rules + 2-reviewer policy
├── SECURITY.md                     Vulnerability disclosure
├── CODEOWNERS                      Auto-review assignments
├── docker-compose.yml              Local + VPS stack
└── requirements.txt                Root dependency manifest
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Binance Testnet API keys ([testnet.binancefuture.com](https://testnet.binancefuture.com))

### Setup

```bash
git clone https://github.com/3nz5789/CoinScopeAI.git
cd CoinScopeAI

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — add BINANCE_TESTNET_API_KEY, TELEGRAM_BOT_TOKEN, NOTION_API_KEY

docker compose up -d redis
uvicorn engine.api:app --reload --port 8001

curl localhost:8001/health
curl localhost:8001/ready
```

Full guide: [`docs/runbooks/local-development.md`](docs/runbooks/local-development.md)

---

## Engine API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service liveness |
| `/ready` | GET | All adapters healthy |
| `/config` | GET | Running configuration + thresholds |
| `/scan` | GET | Signal scan across tracked symbols |
| `/risk-gate` | GET | Gate state — daily loss, drawdown, kill switch |
| `/position-size` | GET | Kelly-based position size for a symbol |
| `/regime/{symbol}` | GET | HMM regime label + confidence score |
| `/journal` | GET | Trade journal entries |
| `/performance` | GET | Rolling win rate, drawdown, profit factor |
| `/kill-switch` | POST | Engage or disengage kill switch |

Base URL: `http://localhost:8001` (dev) · `https://api.coinscope.ai` (prod)

---

## Canonical Risk Thresholds

Locked **2026-05-01** via PCC v2 §8. Enforced by `scripts/risk_threshold_guardrail.py`.

| Threshold | Value | Env var |
|---|---|---|
| Max leverage | **10×** per position | `MAX_LEVERAGE=10` |
| Max open positions | **5** concurrent | `MAX_OPEN_POSITIONS=5` |
| Max drawdown | **10%** from peak | `MAX_DRAWDOWN_PCT=10` |
| Daily loss limit | **5%** rolling 24h | `MAX_DAILY_LOSS_PCT=5` |
| Position heat cap | **80%** deployed capital | `POSITION_HEAT_CAP_PCT=80` |

---

## Key Invariant

> If the risk gate, executor, or adapter is in an uncertain state, **the engine halts — it never guesses.**

Every circuit breaker, kill switch, and rejection path exists to honor this invariant.

---

## Telegram Bot

**Handle:** `@ScoopyAI_bot` (Chat ID: `7296767446`)

| Command | Description |
|---|---|
| `/scan` | On-demand market scan |
| `/performance` | Current P&L snapshot |
| `/risk-gate` | Risk gate status |

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

| ADR | Decision |
|---|---|
| [ADR-0001](docs/decisions/adr-0001-fastapi-and-uvicorn.md) | FastAPI + Uvicorn as engine framework |
| [ADR-0002](docs/decisions/adr-0002-redis-celery-for-workers.md) | Redis + Celery for async tasks |
| [ADR-0003](docs/decisions/adr-0003-llm-off-hot-path.md) | LLM calls prohibited on execution path |

---

## Validation Phase Freeze

These changes are **blocked** during testnet validation:

| Blocked | Reason |
|---|---|
| Any canonical risk threshold change | Invalidates validation cohort |
| `BINANCE_TESTNET=false` | Real-capital gate is locked |
| Removing any circuit breaker | Safety regression |
| Retraining ML artifacts mid-run | Changes signal distribution |

---

## Project Tracking

| Platform | Link |
|---|---|
| Linear (issues) | [linear.app/coinscopeai](https://linear.app/coinscopeai) |
| Notion (docs) | [CoinScopeAI OS](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) |
| Drive (files) | [CoinScopeAI folder](https://drive.google.com/drive/folders/1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8) |
| Dashboard | [app.coinscope.ai](https://app.coinscope.ai) |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Two reviewers required for changes to `risk_management/`, `engine/integrations/`, `.env.example`, `CLAUDE.md`, or `docker-compose.yml`.

---

## License

MIT — see [`LICENSE`](LICENSE).

> **Disclaimer:** CoinScopeAI is a risk management and signal intelligence tool. It does not provide investment advice, manage funds, or place trades autonomously. All trading decisions are made solely by the user. See [/legal](https://app.coinscope.ai/legal) for full disclosures.

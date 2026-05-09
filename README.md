<div align="center">

# CoinScopeAI

**AI-powered crypto futures trading intelligence — capital preservation first.**

[![CI](https://github.com/3nz5789/coinscope-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/3nz5789/coinscope-ai/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-testnet%20validation-blue)](https://linear.app/coinscopeai)
[![Engine](https://img.shields.io/badge/engine-FastAPI%20%2B%20Python%203.11-green)](https://fastapi.tiangolo.com)

[Dashboard](https://app.coinscope.ai) · [Linear](https://linear.app/coinscopeai) · [Notion](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) · [Drive](https://drive.google.com/drive/folders/1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8)

</div>

---

## What is CoinScopeAI?

CoinScopeAI is a regime-aware, risk-first trading intelligence engine for USDT-perpetual crypto futures. It scans Binance Futures for high-probability setups, gates every signal through a multi-layer risk engine, and pushes actionable alerts to traders — without placing trades on their behalf.

**What it is:**
- A signal scoring and risk gate engine for disciplined futures traders
- A capital-preservation tool that halts itself when drawdown limits are hit
- A Telegram-native alert system (`@ScoopyAI_bot`) with on-demand scan commands

**What it is not:**
- An auto-trading bot or execution system
- An investment advice product
- A signal-selling service

> **Validation phase active.** Engine runs on Binance Testnet only. Real-capital trading is gate-locked behind the PCC v2 §8 readiness checklist.

---

## Architecture

```
00  Customer Layer    Onboarding · Stripe billing · ToS acceptance
01  External          Binance · CoinGlass · CoinGecko · Tradefeeds
02  Ingestion         CCXT adapters · Vendor abstraction · EventBus
03  Stores            Redis (cache) · PostgreSQL (billing) · SQLite (journal)
04  Engine Core       Signal scoring → Risk Gate → Position Sizer → Order Manager
05  Engine API        FastAPI :8001 · Auth · Cost meter
06  UI                Dashboard (app.coinscope.ai) · Telegram bot · /legal
```

Full architecture: [`docs/architecture/architecture.md`](docs/architecture/architecture.md) · [Notion mirror](https://www.notion.so/35329aaf938e818e87c4ec03fbfdf1b1)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Engine API | Python 3.11 · FastAPI · Uvicorn |
| Task queue | Celery · Redis |
| Database | PostgreSQL (billing) · SQLite (journal, local) |
| ML / Signals | Scikit-learn · LightGBM · HMM regime classifier |
| Exchange | CCXT — Binance USDT-M (primary) |
| Dashboard | React · Vite · Tailwind CSS |
| Alerts | Telegram Bot API (`@ScoopyAI_bot`) |
| Infra | Docker Compose · DigitalOcean SGP1 · GitHub Actions |

---

## Repository Structure

```
coinscope-ai/
├── coinscope_trading_engine/   Core FastAPI engine
│   ├── app.py                  Application entry point
│   ├── config.py               Env var schema and validation
│   ├── scanner/                Signal scoring (RSI, EMA, CVD, OI, funding)
│   ├── risk/                   Risk gate, kill switch, position sizer
│   ├── regime/                 HMM market regime classifier
│   ├── journal/                Trade journal and performance tracker
│   └── alerts/                 Telegram alerts and Notion sync writer
├── app/                        Restructured engine modules (2026-04-19)
│   ├── engine/                 Signal scoring, regime, scanner
│   ├── integrations/           Exchange clients (Binance primary, OKX fallback)
│   └── core/config.py          Canonical config with env var schema
├── scripts/
│   ├── drift_detector.py       Cross-doc canonical value checker
│   ├── risk_threshold_guardrail.py  Codebase-wide threshold scanner
│   ├── daily_status.sh         Morning engine brief (hits all 6 endpoints)
│   └── setup_github_labels.py  GitHub label setup (matches Linear taxonomy)
├── docs/
│   ├── architecture/           Architecture v5, design system manifest, ADRs
│   ├── risk/                   Risk framework, failsafes, position sizing
│   ├── runbooks/               Daily ops, market scan, troubleshooting
│   └── ops/                    Deployment guides, release checklist
├── skills_src/                 Operator SKILL.md docs
├── tests/                      Full test suite
├── .github/
│   ├── workflows/ci.yml        Lint · test · security scan
│   ├── ISSUE_TEMPLATE/         Bug report, feature request
│   └── pull_request_template.md
├── .env.example                Canonical env template (all vars documented)
├── CLAUDE.md                   AI operator instructions and canonical thresholds
├── CONTRIBUTING.md             Contribution guide and validation-phase rules
├── SECURITY.md                 Vulnerability disclosure policy
├── CODEOWNERS                  Auto-review assignments for critical paths
└── docker-compose.yml          Local and VPS stack
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Binance Testnet API keys ([testnet.binancefuture.com](https://testnet.binancefuture.com))

### Setup

```bash
git clone https://github.com/3nz5789/coinscope-ai.git
cd coinscope-ai

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set BINANCE_TESTNET_API_KEY, TELEGRAM_BOT_TOKEN, NOTION_API_KEY

docker compose up -d redis

uvicorn coinscope_trading_engine.app:app --reload --port 8001

curl localhost:8001/health
curl localhost:8001/ready
```

Full guide: [`docs/runbooks/local-development.md`](docs/runbooks/local-development.md)

---

## Engine API

Base URL: `http://localhost:8001` (local) · `https://api.coinscope.ai` (production)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Service liveness |
| `/ready` | GET | All adapters healthy |
| `/scan` | GET | Market signal scan across tracked symbols |
| `/risk-gate` | GET | Gate state (daily loss, drawdown, kill switch) |
| `/position-size` | GET | Kelly-based position size for a symbol |
| `/regime/{symbol}` | GET | HMM regime label and confidence score |
| `/journal` | GET | Trade journal entries |
| `/performance` | GET | Rolling metrics (win rate, drawdown, profit factor) |
| `/kill-switch` | POST | Engage or disengage kill switch |

---

## Canonical Risk Thresholds

Defined in `CLAUDE.md`, enforced by `scripts/risk_threshold_guardrail.py`, locked 2026-05-01.

| Threshold | Value |
|---|---|
| Max leverage | **10x** per position |
| Max open positions | **5** concurrent |
| Max drawdown | **10%** from peak — triggers kill switch |
| Daily loss limit | **5%** rolling 24h — halts all trading |
| Position heat cap | **80%** total deployed capital |

---

## Telegram Bot

**Handle:** `@ScoopyAI_bot`

| Command | Description |
|---|---|
| `/scan` | On-demand market scan |
| `/performance` | Current P&L snapshot |
| `/risk-gate` | Risk gate status check |

Auto-alerts fire for: signals scoring 8.0+, kill switch activation, daily P&L digest (21:00 UTC).

---

## Running Tests

```bash
# Fast — unit tests only
pytest -x -q coinscope_trading_engine/tests

# Full suite (requires Redis running)
pytest

# With coverage report
pytest --cov=coinscope_trading_engine --cov-report=term-missing

# Exchange adapter smoke test
python -m scripts.binance_adapter_smoke --symbols BTCUSDT --duration 30
```

---

## Deployment

VPS: DigitalOcean SGP1 · Docker Compose · systemd

- [`docs/ops/digitalocean-deployment.md`](docs/ops/digitalocean-deployment.md)
- [`docs/runbooks/release-checklist.md`](docs/runbooks/release-checklist.md)

---

## Validation Phase Freeze

The following changes are **blocked** during testnet validation:

| Blocked | Reason |
|---|---|
| Any canonical risk threshold change | Invalidates the validation cohort |
| `BINANCE_TESTNET=false` | Real-capital gate is locked |
| Removing a circuit breaker | Safety regression |
| Retraining ML artifacts | Changes signal distribution |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/runbooks/release-checklist.md`](docs/runbooks/release-checklist.md).

---

## Project Tracking

| Platform | Link |
|---|---|
| Issues (Linear) | [linear.app/coinscopeai](https://linear.app/coinscopeai) |
| Docs (Notion) | [CoinScopeAI OS](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) |
| Files (Drive) | [CoinScopeAI folder](https://drive.google.com/drive/folders/1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8) |
| Dashboard | [app.coinscope.ai](https://app.coinscope.ai) |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Two reviewers required for risk logic, exchange adapters, or threshold changes.

---

## License

MIT — see [`LICENSE`](LICENSE).

> **Disclaimer:** CoinScopeAI is a risk management and signal intelligence tool. It does not provide investment advice, manage funds, or place trades on your behalf. All trading decisions are made solely by the user. Testnet signal performance does not guarantee future live results.

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
- A capital-preservation tool that halts itself when drawdown limits are hit
- A Telegram-native alert system (`@ScoopyAI_bot`) with real-time regime awareness

**It is not:**
- An auto-trading bot or execution system
- An investment advice product or fund manager
- A signal-selling or copy-trading service

> **Validation phase active.** Engine runs on **Binance Testnet only**. Real-capital trading is gate-locked behind the Production Candidate Criteria v2 §8 readiness checklist.

---

## Architecture

```
Tier 00  Customer Layer     Onboarding · Stripe billing · ToS acceptance gate
Tier 01  Exchange Layer     Binance USDT-M Testnet (primary) · OKX klines fallback
Tier 02  Ingestion          CCXT adapters · OHLCV · OI · Funding · Liquidations
Tier 03  Engine Core        Signal Scorer → HMM Regime → Risk Gate → Kelly Sizer
Tier 04  Engine API         FastAPI :8001 · Auth · Cost meter · Audit log
Tier 05  Dashboards         app.coinscope.ai · Telegram @ScoopyAI_bot · /legal
Tier 06  Ops Rail           DigitalOcean SGP1 · Docker · GitHub Actions · Notion sync
```

Full architecture: [`docs/architecture/architecture.md`](docs/architecture/architecture.md)

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
├── coinscope_trading_engine/          Core Python engine
│   ├── main.py                        Application entry point
│   ├── api.py                         FastAPI router registration
│   ├── config.py                      Env var schema (Pydantic Settings)
│   ├── celery_app.py                  Celery worker configuration
│   ├── scanner/                       Signal scoring modules
│   │   ├── base_scanner.py            Abstract scanner interface
│   │   ├── volume_scanner.py          Volume + CVD analysis
│   │   ├── funding_rate_scanner.py    Funding rate scanner
│   │   ├── liquidation_scanner.py     Liquidation cascade scanner
│   │   ├── orderbook_scanner.py       Order book depth scanner
│   │   └── pattern_scanner.py        Pattern recognition scanner
│   ├── scanners/                      Additional scanner implementations
│   │   ├── scalp_scanner.py           Scalp signal scanner (6-factor confluence)
│   │   ├── volume_scanner.py
│   │   └── liquidation_scanner.py
│   ├── risk/                          Risk gate + kill switch + position sizing
│   ├── core/                          Shared core modules
│   │   ├── tos_gate.py                ToS acceptance gate (P1.5)
│   │   ├── key_vault.py               AES-256-GCM API key vault (P1.5)
│   │   └── cost_meter.py              Per-user API cost tracker (P1.5)
│   ├── intelligence/                  HMM regime classifier
│   ├── execution/                     Order management
│   ├── signals/                       Signal pipeline
│   ├── monitoring/                    Health checks + metrics
│   ├── alerts/                        Telegram + Notion sync writer
│   ├── billing/                       Stripe integration
│   ├── storage/                       Journal + state persistence
│   ├── models/                        ML model artifacts
│   ├── tests/                         Engine unit tests
│   │   └── test_scalp_scanner_imports.py  COI-55 import regression tests
│   └── requirements.txt               Pinned engine dependencies
│
├── coinscopeai-dashboard/             React dashboard
│   ├── client/
│   │   ├── src/
│   │   │   ├── index.css              Design system — OKLCH color tokens
│   │   │   ├── components/            10 HUD components
│   │   │   │   ├── DashboardLayout.tsx
│   │   │   │   ├── MetricCard.tsx
│   │   │   │   ├── StatusBadge.tsx
│   │   │   │   └── ...
│   │   │   └── components/ui/         45 shadcn/ui base components
│   │   └── public/
│   │       └── legal.html             Public /legal disclosures page
│   └── server/                        Dashboard BFF server
│
├── docs/                              Technical documentation
│   ├── architecture/
│   │   ├── architecture.md            System architecture v5 (canonical)
│   │   └── design-system-manifest.md  Design tokens + component inventory v3
│   ├── decisions/                     Architecture Decision Records
│   │   ├── adr-0001-fastapi-and-uvicorn.md
│   │   ├── adr-0002-redis-celery-for-workers.md
│   │   └── adr-0003-llm-off-hot-path.md
│   ├── risk/                          Risk framework documentation
│   │   ├── risk-framework.md          Risk philosophy + invariants
│   │   ├── risk-gate.md               Gate logic + layer breakdown
│   │   ├── position-sizing.md         Kelly pipeline
│   │   └── failsafes-and-kill-switches.md
│   ├── runbooks/                      Operational runbooks
│   │   ├── daily-ops.md               Daily operator checklist
│   │   ├── local-development.md       Local dev setup
│   │   ├── digitalocean-deployment.md VPS deployment guide
│   │   ├── release-checklist.md       Pre-release gates
│   │   └── troubleshooting.md         Incident response
│   ├── ml/                            ML documentation
│   │   ├── regime-detection.md        HMM classifier design
│   │   ├── confidence_scoring_baseline.md
│   │   ├── models/                    Trained model artifacts (.pkl)
│   │   └── data/                      Training datasets
│   ├── incidents/                     Post-incident reports
│   └── onboarding/                    Developer onboarding
│
├── scripts/                           Operator scripts
│   ├── drift_detector.py              Cross-doc token consistency checker
│   ├── risk_threshold_guardrail.py    Codebase-wide threshold validator
│   ├── daily_status.sh                Morning engine brief (6 endpoints)
│   ├── sync_verify.py                 Cross-platform structure verifier (35/37)
│   ├── auto_sync.py                   Session-end auto-sync engine
│   └── setup_github_labels.py         GitHub label setup (27 labels)
│
├── 11-legal/                          Legal documents
│   ├── tos-and-disclosures-DRAFT.md   ToS + risk disclosures (pre-counsel)
│   ├── data-retention.md              Data retention policy
│   └── counsel-brief-v2.md            Counsel brief
│
├── .github/
│   ├── workflows/ci.yml               Lint · test · security scan
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── pull_request_template.md
│
├── .env.example                       Canonical env template (all vars)
├── .env.template                      Extended env template
├── CLAUDE.md                          AI operator instructions + thresholds
├── CONTEXT_PRIMER.md                  Session on-ramp for AI operators
├── CONTRIBUTING.md                    Contribution rules + 2-reviewer policy
├── SECURITY.md                        Vulnerability disclosure policy
├── CODEOWNERS                         Auto-review assignments
├── docker-compose.yml                 Local + VPS stack definition
├── requirements.txt                   Root dependency manifest
├── canonical-structure-spec.md        Cross-platform naming + structure rules
└── prometheus.yml                     Metrics scrape config
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
pip install -r coinscope_trading_engine/requirements.txt

cp .env.example .env
# Edit .env — add BINANCE_TESTNET_API_KEY, TELEGRAM_BOT_TOKEN, NOTION_API_KEY

# Start Redis
docker compose up -d redis

# Start engine
uvicorn coinscope_trading_engine.main:app --reload --port 8001

# Verify
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
| `/config` | GET | Running configuration (thresholds, env) |
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

## Design System

Colors, typography, and component tokens defined in [`docs/architecture/design-system-manifest.md`](docs/architecture/design-system-manifest.md) and implemented in [`coinscopeai-dashboard/client/src/index.css`](coinscopeai-dashboard/client/src/index.css).

| Token | OKLCH | Use |
|---|---|---|
| Primary / Profit | `oklch(0.70 0.17 162)` | Emerald — CTAs, profit |
| Accent | `oklch(0.75 0.12 200)` | Cyan — highlights |
| Destructive / Loss | `oklch(0.60 0.22 25)` | Crimson — errors, loss |
| Warning / Volatile | `oklch(0.78 0.16 75)` | Amber — caution |
| Background | `oklch(0.12 0.02 260)` | Dark navy |

---

## Telegram Bot

**Handle:** `@ScoopyAI_bot` (Chat ID: `7296767446`)

| Command | Description |
|---|---|
| `/scan` | On-demand market scan |
| `/performance` | Current P&L snapshot |
| `/risk-gate` | Risk gate status |

Auto-alerts fire for: signals ≥ 8.0, kill switch activation, P&L digest (21:00 UTC).

---

## Running Tests

```bash
# Unit tests
pytest -x -q coinscope_trading_engine/tests/

# Import regression (COI-55)
pytest coinscope_trading_engine/tests/test_scalp_scanner_imports.py -v

# Full suite
pytest --cov=coinscope_trading_engine --cov-report=term-missing

# Protective tooling
python3 scripts/drift_detector.py            # token consistency
python3 scripts/risk_threshold_guardrail.py  # threshold ceilings
python3 scripts/sync_verify.py               # cross-platform structure
```

---

## Operator Scripts

| Script | Purpose |
|---|---|
| `scripts/drift_detector.py` | Checks 10 canonical docs for token drift |
| `scripts/risk_threshold_guardrail.py` | Scans codebase for threshold violations |
| `scripts/daily_status.sh` | Morning engine brief (all 6 endpoints) |
| `scripts/sync_verify.py` | Cross-platform structure check (35/37 passing) |
| `scripts/auto_sync.py` | Session-end auto-sync: git + drift + guardrail |
| `scripts/setup_github_labels.py` | Creates 27 GitHub labels (Linear taxonomy) |

---

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [ADR-0001](docs/decisions/adr-0001-fastapi-and-uvicorn.md) | FastAPI + Uvicorn as engine framework |
| [ADR-0002](docs/decisions/adr-0002-redis-celery-for-workers.md) | Redis + Celery for async task processing |
| [ADR-0003](docs/decisions/adr-0003-llm-off-hot-path.md) | LLM calls prohibited on execution path |

---

## Validation Phase Freeze

These changes are **blocked** during testnet validation (PCC v2 §8):

| Blocked | Reason |
|---|---|
| Any canonical risk threshold change | Invalidates validation cohort |
| `BINANCE_TESTNET=false` | Real-capital gate is locked |
| Removing any circuit breaker | Safety regression |
| Retraining ML artifacts mid-run | Changes signal distribution |
| Changing order submission semantics | Execution integrity |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/runbooks/release-checklist.md`](docs/runbooks/release-checklist.md).

---

## Project Tracking

| Platform | Link |
|---|---|
| Linear (issues) | [linear.app/coinscopeai](https://linear.app/coinscopeai) |
| Notion (docs) | [CoinScopeAI OS](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) |
| Drive (files) | [CoinScopeAI folder](https://drive.google.com/drive/folders/1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8) |
| Dashboard | [app.coinscope.ai](https://app.coinscope.ai) |
| Legal | [/legal](https://app.coinscope.ai/legal) |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Two reviewers required for changes to `risk/`, `integrations/`, `.env.example`, `CLAUDE.md`, or `docker-compose.yml`.

---

## License

MIT — see [`LICENSE`](LICENSE).

---

> **Disclaimer:** CoinScopeAI is a risk management and signal intelligence tool. It does not provide investment advice, manage funds, or place trades autonomously. All trading decisions are made solely by the user. Testnet signal performance does not guarantee future live results. See [/legal](https://app.coinscope.ai/legal) for full disclosures.

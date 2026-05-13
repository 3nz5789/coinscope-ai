<div align="center">

# CoinScopeAI

**Regime-aware, risk-first trading intelligence for USDT-perpetual crypto futures.**

[![CI](https://github.com/3nz5789/CoinScopeAI/actions/workflows/ci.yml/badge.svg)](https://github.com/3nz5789/CoinScopeAI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-P0%20testnet%20validation-orange)](#validation-phase-freeze)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/engine-FastAPI-009688)](https://fastapi.tiangolo.com)

[Dashboard](https://app.coinscope.ai) · [API Docs](https://api.coinscope.ai/docs) · [P0 Status](docs/validation/p0-public-summary.md) · [Linear](https://linear.app/coinscopeai) · [Notion](https://www.notion.so/33a29aaf938e81efa983e47b83e15775) · [Disclosures](https://app.coinscope.ai/legal)

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

## Readiness

<!-- readiness:begin -->

**Updated:** 2026-05-13 · **Source of truth:** [`docs/validation/p0-evidence-pack.md`](docs/validation/p0-evidence-pack.md) §0 (honesty pass overrides body)

| Field | Value |
|---|---|
| Phase | **P0 — testnet validation** (Binance USDT-M Testnet only) |
| Freeze | **🔒 Active** — see [Validation Phase Freeze](#validation-phase-freeze). P0 runs through ~2026-05-31 |
| Latest tag | [`v0.1.0-p0.3`](https://github.com/3nz5789/CoinScopeAI/releases/tag/v0.1.0-p0.3) — 2026-05-13, "Risk Framework Docs" |
| Evidence baseline | [`p0-evidence-pack.md`](docs/validation/p0-evidence-pack.md) — start at §0.5 for the one-paragraph honest summary |
| Invariant coverage | 12 🟢 · 4 🟡 · 0 🔴 → [`invariant-matrix.md`](docs/validation/invariant-matrix.md) |
| Open PR-driven blockers | [#28](https://github.com/3nz5789/CoinScopeAI/pull/28) 65 invariant tests on `main` · [#50](https://github.com/3nz5789/CoinScopeAI/pull/50) kill-switch deactivate guard · [#51](https://github.com/3nz5789/CoinScopeAI/pull/51) WFV+CPCV harness |
| Open operator blockers | COI-68 VPS `.env` patch · COI-69 post-restart verification |

> **P0 graduates to P1 when** every PR-driven row above merges, both operator COI items complete, and the four 🟡 rows in the invariant matrix flip 🟢. Do not interpret this block in isolation — read against [`p0-evidence-pack.md`](docs/validation/p0-evidence-pack.md) §0.4 and the invariant matrix.

<!-- readiness:end -->

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

Present state on `main`. Planned migrations, naming clarifications, and any callouts not yet landed live in [`docs/architecture/repository-roadmap.md`](docs/architecture/repository-roadmap.md) — not here.

```
CoinScopeAI/
│
├── engine/                  FastAPI trading engine
│   ├── api.py                  App entry + router registration
│   ├── core/                   Pair monitor, orchestrator, shared state
│   ├── exchange/               Binance Futures Testnet REST/WS clients + executor
│   ├── integrations/           Notion sync, trade journal, portfolio sync
│   ├── monitoring/             Health/readiness probes, Prometheus metrics
│   └── signals/                Confluence scoring pipeline
│
├── risk_management/         Risk gate, sizer, regime detector
│   ├── risk_gate.py             Pre-trade gate: regime, heat, daily loss, drawdown
│   ├── kelly_position_sizer.py  Fractional Kelly with 2% per-trade hard cap
│   └── hmm_regime_detector.py   HMM regime classifier (bull / chop / bear)
│
├── services/                Long-running workers
│   ├── paper_trading/           Engine + safety gate + kill switch + CLI
│   ├── market_data/             Multi-venue stream recorders + aggregator
│   └── telegram-bot/            @ScoopyAI_bot worker
│
├── apps/dashboard/          React 18 + Vite + Tailwind dashboard
│
├── strategies/              Strategy configs · research · backtests (scaffold)
├── ml_models/               Model training scaffolding
├── data/                    Pipeline scaffolding (raw / processed / features)
│
├── configs/environments/    development.yaml · staging.yaml · production.yaml
├── infra/docker/            Dockerfiles + docker-compose.{dev,prod}.yml
├── infra/systemd/           systemd unit files
├── deploy/systemd/          Production unit installer
│
├── scripts/                 Operational + CI gate scripts (see table below)
├── tests/                   pytest — smoke + unit + directory-boundary
├── docs/                    Documentation (see index below)
│
├── bot/                     Telegram alert helper
├── notebooks/               Research notebooks
├── memory/                  Operator memory store
├── utils/                   Shared helpers
└── archive/                 Pre-restructure code retained for history
```

Root files: `README.md` · `CHANGELOG.md` · `CONTRIBUTING.md` · `SECURITY.md` · `CODEOWNERS` · `Makefile` · `requirements.txt` · `pyproject.toml` · `coinscope.env.example` · `prometheus.yml` · `prometheus-alert-rules.yml`

### Scripts on `main`

| Script | Purpose |
|---|---|
| `scripts/risk_threshold_guardrail.py` | Codebase-wide threshold drift scanner |
| `scripts/evidence_gate.py` | CI gate — sensitive PR must touch proof/freeze/release |
| `scripts/invariant_matrix_check.py` | CI gate — invariant-matrix citations resolve |
| `scripts/daily_status_check.py` + `scripts/run_daily_status.sh` | Morning engine brief |
| `scripts/health_check_paper_trading.py` | Paper-trading health verifier |
| `scripts/sync_verify.py` | Cross-platform structure verifier |
| `scripts/test_testnet_connectivity.py` | Binance testnet reachability probe |
| `scripts/setup_github_labels.py` | Label installer (classic PAT required) |

### Documentation index

| Path | Contents |
|---|---|
| `docs/architecture/` | Confluence scoring · design-system manifest |
| `docs/api/engine-api-contract.md` | Engine API contract |
| `docs/decisions/` | Architecture decision records |
| `docs/risk/` | Risk framework · gate · sizing · failsafes |
| `docs/runbooks/operator-workflow.md` | Trading session lifecycle |
| `docs/validation/p0-evidence-pack.md` | Validation proof hub |
| `docs/validation/invariant-matrix.md` | Invariant-to-test mapping |
| `docs/monitoring/slo-alerts-dashboard.md` | SLO and alert specs |

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

## Invariant cheatsheet

The six claims this README makes about the system, paired with the code that enforces each one and the tests that catch a regression. The full 16-row matrix — thresholds, regime gating, journaling, hot-path import boundary, drift detection, and the matrix's own integrity check — lives at [`docs/validation/invariant-matrix.md`](docs/validation/invariant-matrix.md).

| Claim | Code | Tests | Matrix |
|---|---|---|---|
| P0 runs on Binance Testnet only | `coinscope.env.example` · `configs/environments/staging.yaml` | `tests/test_ci_smoke.py::test_testnet_mode` | 🟢 I7 |
| No trade bypasses the risk gate | `services/paper_trading/safety.py` · `services/paper_trading/order_manager.py` | `tests/unit/paper_trading/test_safety.py` — every rejection class (BUG-10 is the canonical regression) | 🟢 I1 |
| No size exceeds the 2% per-trade hard cap | `risk_management/kelly_position_sizer.py` · `services/paper_trading/safety.py` | `tests/unit/paper_trading/test_safety.py` + `scripts/risk_threshold_guardrail.py` | 🟢 I2 |
| A tripped breaker blocks new entries | `services/paper_trading/safety.py` | Daily-loss · max-drawdown · consecutive-loss tests in `test_safety.py` | 🟢 I3 |
| Kill switch prevents new entries when engaged | `services/paper_trading/safety.py` · `services/paper_trading/kill.py` | `TestKillSwitch` + `TestSafetyGateKillSwitch` in `test_safety.py` | 🟡 I4 · [#47](https://github.com/3nz5789/CoinScopeAI/issues/47) |
| Engine halts on uncertain state — never guesses | `services/paper_trading/safety.py` (`validate_order` fail-closed) | `tests/unit/paper_trading/test_safety.py` (reject-default branch) | 🟢 I6 |

Status colour and matrix ID let you jump straight to the full row in [`invariant-matrix.md`](docs/validation/invariant-matrix.md). 🟡 rows carry a tracking issue — the link is in the Matrix column.

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

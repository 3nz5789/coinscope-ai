# CoinScopeAI Documentation

**Status:** current
**Audience:** everyone committing to, operating, or reviewing the CoinScopeAI repo
**Last updated:** 2026-04-18

This folder is the canonical documentation set for the CoinScopeAI trading engine. It is organized by audience and lifecycle, not by file type. If a doc is missing, start with [`repository-map.md`](repository-map.md) to find the right folder, then add a new file there.

Every doc in this tree carries a header with:

- **Status:** one of `current`, `draft`, `planned`. Treat `planned` as aspirational — the feature may not exist yet.
- **Audience:** who the doc is written for.
- **Related:** links to adjacent docs.

When you ship code, update the doc in the same PR. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for the docs-update checklist.

## Start here

If you are new to the repo, read these in order. The goal is to get you from zero to "can run the engine locally and read a signal" in an afternoon.

1. [`../README.md`](../README.md) — one-page repo overview, quick-start, and status.
2. [`onboarding/new-developer-guide.md`](onboarding/new-developer-guide.md) — environment setup end-to-end.
3. [`onboarding/first-week-checklist.md`](onboarding/first-week-checklist.md) — what to read, run, and ship in your first five days.
4. [`onboarding/glossary.md`](onboarding/glossary.md) — the vocabulary. Regime, heat, confluence, WFV, etc.
5. [`architecture/system-overview.md`](architecture/system-overview.md) — how the pieces fit together.
6. [`repo-audit.md`](repo-audit.md) — what this repo looked like before the 2026-04-18 restructure, and why things are where they are.

## By audience

### I am a new contributor

- [`onboarding/new-developer-guide.md`](onboarding/new-developer-guide.md)
- [`onboarding/first-week-checklist.md`](onboarding/first-week-checklist.md)
- [`onboarding/glossary.md`](onboarding/glossary.md)
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md)

### I am reviewing a PR or designing a change

- [`architecture/system-overview.md`](architecture/system-overview.md)
- [`architecture/component-map.md`](architecture/component-map.md)
- [`architecture/data-flow.md`](architecture/data-flow.md)
- [`decisions/`](decisions/) — ADRs with context and trade-offs
- [`risk/risk-framework.md`](risk/risk-framework.md) — mandatory reading for anything touching position sizing, stops, or circuit breakers

### I am operating the engine

- [`runbooks/local-development.md`](runbooks/local-development.md)
- [`runbooks/daily-ops.md`](runbooks/daily-ops.md)
- [`runbooks/troubleshooting.md`](runbooks/troubleshooting.md)
- [`runbooks/release-checklist.md`](runbooks/release-checklist.md)
- [`ops/stripe-billing-runbook.md`](ops/stripe-billing-runbook.md)

### I am working on the ML / signal side

- [`ml/ml-overview.md`](ml/ml-overview.md)
- [`ml/regime-detection.md`](ml/regime-detection.md) — covers both the HMM detector (bull/bear/chop) and the v3 classifier (Trending/Mean-Reverting/Volatile/Quiet)
- [`risk/position-sizing.md`](risk/position-sizing.md) — Kelly + regime multipliers
- [`testing/testing-strategy.md`](testing/testing-strategy.md)

### I am integrating an exchange or external service

- [`ops/exchange-integrations.md`](ops/exchange-integrations.md)
- [`ops/binance-adapter.md`](ops/binance-adapter.md)
- [`ops/telegram-alerts.md`](ops/telegram-alerts.md)
- [`ops/stripe-billing.md`](ops/stripe-billing.md)

### I am on the billing / commercial side

- [`ops/stripe-billing.md`](ops/stripe-billing.md)
- [`ops/stripe-billing-runbook.md`](ops/stripe-billing-runbook.md)
- [`backend/configuration.md`](backend/configuration.md) — environment variables for Stripe
- [`api/backend-endpoints.md`](api/backend-endpoints.md) — billing / entitlement endpoints

## By topic

### Architecture and shape of the system

| Doc | Status | Purpose |
| --- | --- | --- |
| [`architecture/system-overview.md`](architecture/system-overview.md) | current | One-page view of the engine, scanner, scorer, risk, execution, API, workers. |
| [`architecture/component-map.md`](architecture/component-map.md) | current | Every module, what it owns, who calls it. |
| [`architecture/data-flow.md`](architecture/data-flow.md) | current | Tick → candle → regime → signal → risk gate → sized trade → journal. |
| [`architecture/future-state-roadmap.md`](architecture/future-state-roadmap.md) | planned | Multi-exchange, mainnet, and post-validation directions. |
| [`repo-audit.md`](repo-audit.md) | current | 2026-04-18 snapshot of the repo before the restructure. |
| [`repository-map.md`](repository-map.md) | current | Every top-level folder explained in a table. |

### Backend and API

| Doc | Status | Purpose |
| --- | --- | --- |
| [`backend/backend-overview.md`](backend/backend-overview.md) | current | FastAPI app, uvicorn, Celery worker, Redis, SQLite/Postgres. |
| [`backend/configuration.md`](backend/configuration.md) | current | Every env var, default, and where it's read. |
| [`api/api-overview.md`](api/api-overview.md) | current | Auth, error format, rate limiting, base URL. |
| [`api/backend-endpoints.md`](api/backend-endpoints.md) | current | Full endpoint reference with request/response shapes. |

### Risk and ML

| Doc | Status | Purpose |
| --- | --- | --- |
| [`risk/risk-framework.md`](risk/risk-framework.md) | current | Risk philosophy, thresholds, and invariants. |
| [`risk/risk-gate.md`](risk/risk-gate.md) | current | The pre-trade gate that decides if a signal is tradable. |
| [`risk/position-sizing.md`](risk/position-sizing.md) | current | Kelly-fractional sizing and regime multipliers. |
| [`risk/failsafes-and-kill-switches.md`](risk/failsafes-and-kill-switches.md) | current | Circuit breakers, daily loss lockout, manual kill switch. |
| [`ml/ml-overview.md`](ml/ml-overview.md) | current | scikit-learn + hmmlearn + xgboost stack; no PyTorch. |
| [`ml/regime-detection.md`](ml/regime-detection.md) | current | HMM (3-state) and v3 classifier (4-label) — how they coexist. |

### Exchanges, integrations, ops

| Doc | Status | Purpose |
| --- | --- | --- |
| [`ops/exchange-integrations.md`](ops/exchange-integrations.md) | current | Supported exchanges and the adapter contract. |
| [`ops/binance-adapter.md`](ops/binance-adapter.md) | current | REST, WebSocket, signing, and the 2026-04-23 path migration. |
| [`ops/telegram-alerts.md`](ops/telegram-alerts.md) | current | Bot setup, alert types, rate limits. |
| [`ops/stripe-billing.md`](ops/stripe-billing.md) | current | Product model, webhook flow, entitlements. |
| [`ops/stripe-billing-runbook.md`](ops/stripe-billing-runbook.md) | current | Day-to-day Stripe ops — refunds, resyncs, failures. |
| [`runbooks/local-development.md`](runbooks/local-development.md) | current | Running the engine on a laptop. |
| [`runbooks/daily-ops.md`](runbooks/daily-ops.md) | current | Daily checks while validation is running. |
| [`runbooks/daily-market-scan-runbook.md`](runbooks/daily-market-scan-runbook.md) | current | Running and reading the scanner. |
| [`runbooks/release-checklist.md`](runbooks/release-checklist.md) | current | What to check before tagging a release. |
| [`runbooks/troubleshooting.md`](runbooks/troubleshooting.md) | current | Known failure modes and fixes. |
| [`runbooks/digitalocean-deployment.md`](runbooks/digitalocean-deployment.md) | current | The current VPS deployment. |
| [`runbooks/cloud-deployment-guide.md`](runbooks/cloud-deployment-guide.md) | current | Generic cloud deploy notes. |
| [`runbooks/incident-binance-ws-disconnect-2026-04-18.md`](runbooks/incident-binance-ws-disconnect-2026-04-18.md) | current | The 2026-04-18 WebSocket incident write-up. |

### Testing and quality

| Doc | Status | Purpose |
| --- | --- | --- |
| [`testing/testing-strategy.md`](testing/testing-strategy.md) | current | Test taxonomy: unit, integration, backtest, walk-forward. |
| [`testing/local-validation-checklist.md`](testing/local-validation-checklist.md) | current | What to run before pushing risk-adjacent code. |

### Decisions

| Doc | Status | Purpose |
| --- | --- | --- |
| [`decisions/README.md`](decisions/README.md) | current | How we write ADRs. |
| [`decisions/TEMPLATE.md`](decisions/TEMPLATE.md) | current | Copy this when opening a new ADR. |
| [`decisions/adr-0001-fastapi-and-uvicorn.md`](decisions/adr-0001-fastapi-and-uvicorn.md) | current | Why FastAPI + uvicorn. |
| [`decisions/adr-0002-redis-celery-for-workers.md`](decisions/adr-0002-redis-celery-for-workers.md) | current | Why Redis + Celery for background work. |
| [`decisions/adr-0003-llm-off-hot-path.md`](decisions/adr-0003-llm-off-hot-path.md) | current | Why the LLM never gates a trade. |

### Product and planning

| Doc | Status | Purpose |
| --- | --- | --- |
| [`product/implementation-backlog.md`](product/implementation-backlog.md) | current | Tier-2 docs and features queued for after validation. |

### Frontend

| Doc | Status | Purpose |
| --- | --- | --- |
| [`frontend/README.md`](frontend/README.md) | draft | What lives in this repo vs. the separate dashboard repo; covers the three static HTML pages under `/dashboard/`. |

### Historical

| Doc | Status | Purpose |
| --- | --- | --- |
| [`project-history.md`](project-history.md) | current | How the project got here. Keep for context, do not treat as a design doc. |
| [`RESTRUCTURE_SUMMARY.md`](RESTRUCTURE_SUMMARY.md) | current | Point-in-time record of the 2026-04-18 docs restructure. Read once. |
| [`../archive/README.md`](../archive/README.md) | current | Index of files retained for history but not load-bearing. |

## Conventions

- Every doc starts with a three-line header: `Status`, `Audience`, `Related`.
- File names are lowercase with hyphens. No spaces, no underscores, no title case.
- Links inside `docs/` are relative. Links to code use repo-rooted paths (e.g. `/coinscope_trading_engine/risk_gate.py`).
- Code blocks specify a language for syntax highlighting.
- Dates are absolute (`2026-04-18`), never relative ("last week").

## Gaps and what's next

The following Tier-2 docs are planned but not yet written. They are listed in [`product/implementation-backlog.md`](product/implementation-backlog.md):

- Frontend docs for the React dashboard at https://coinscope.ai/ (separate repository — not in this tree).
- Post-validation directory reorganization inside `coinscope_trading_engine/`.
- Per-exchange adapter docs for Bybit, OKX, and Hyperliquid once those adapters exist.
- Mainnet cutover runbook.
- Full SRE / observability doc set (Prometheus queries, SLOs, paging rules).

If you need any of those docs before they are written, read the code plus the closest current doc, then file an issue and pick up the writing.

# New Developer Guide

**Status:** current
**Audience:** a developer joining the CoinScopeAI engine team for the first time
**Related:** [`first-week-checklist.md`](first-week-checklist.md), [`glossary.md`](glossary.md), [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md), [`../runbooks/local-development.md`](../runbooks/local-development.md)

This guide takes you from "I just cloned the repo" to "I can run the engine against Binance testnet and see a signal appear in the journal." Plan on an afternoon, not a week.

## What you're about to work on

CoinScopeAI is a Python trading engine that scans Binance USDT-M perpetual futures, scores each symbol against a multi-factor confluence model, passes surviving candidates through a risk gate, and executes sized orders on testnet. The engine is in a **30-day validation phase (2026-04-10 to 2026-04-30)**. During the freeze:

- **No mainnet.** All execution is Binance Testnet.
- **No engine restructure.** Internal refactors are held until after 2026-04-30.
- **No risk-threshold changes.** The numbers in [`../risk/risk-framework.md`](../risk/risk-framework.md) are locked.

Bug fixes, tests, docs, and tooling are welcome.

## Prerequisites

You need, on your machine:

- **Python 3.11 or newer.** Check with `python3 --version`. If you have 3.10 or older, install 3.11+ — we use modern typing and `pydantic-settings`.
- **Git.**
- **Docker + Docker Compose**, if you want the full local stack (Redis, Postgres, Prometheus). You can run the engine without Docker, but the workers need Redis.
- **A Binance Testnet account and API key.** https://testnet.binancefuture.com/. Create the key with Trade + Read enabled. Testnet keys are throwaway; rotate if they ever appear in a diff.
- **A Stripe test-mode account,** only if you are touching billing. Most new contributors are not.

You do **not** need:

- A real Binance account or real funds.
- GPU hardware. The ML stack is scikit-learn + hmmlearn + xgboost. No PyTorch.
- Kubernetes. Deployment is Docker Compose on a VPS.

## Step 1: Clone and bootstrap

```bash
git clone git@github.com:3nz5789/coinscope-ai.git
cd coinscope-ai

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If you'll run the engine locally (not just read code), also install the engine's own requirements:

```bash
pip install -r coinscope_trading_engine/requirements.txt
```

## Step 2: Configure your environment

Copy the template and fill it in:

```bash
cp .env.example .env
```

Open `.env` and set, at minimum:

- `BINANCE_API_KEY` / `BINANCE_API_SECRET` — your testnet keys.
- `BINANCE_TESTNET=true`. **Do not flip this to false.** See [`../backend/configuration.md`](../backend/configuration.md) for every variable.
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are optional — leave them blank until you want alerts.

Do not commit `.env`. It is already in `.gitignore`.

## Step 3: Bring up the local stack

```bash
docker compose up -d redis postgres
```

This starts Redis (Celery broker) and Postgres (journal storage in non-SQLite mode). If you prefer SQLite for a first run, set `DATABASE_URL=sqlite:///./journal.db` in `.env` and skip the Postgres container.

Verify:

```bash
docker compose ps
redis-cli ping        # expect PONG
```

## Step 4: Run the engine

Two processes, two terminals:

```bash
# terminal 1 — the API
uvicorn coinscope_trading_engine.api.main:app --reload --port 8001

# terminal 2 — the worker
celery -A coinscope_trading_engine.worker.celery_app worker --loglevel=info
```

Smoke-test:

```bash
curl http://localhost:8001/health
curl http://localhost:8001/scan
```

`/scan` should return a ranked list of signals within a few seconds. If it returns an empty list, that's fine — it means nothing met the scoring floor. If it returns a 500, check the uvicorn logs.

Full endpoint reference: [`../api/backend-endpoints.md`](../api/backend-endpoints.md).

## Step 5: Run the tests

```bash
pytest                                       # everything the CI runs
pytest coinscope_trading_engine/tests/       # engine-internal tests
pytest tests/test_billing_*                  # only billing
pytest -m integration                        # opt-in integration tests (hit testnet)
```

The full test strategy lives in [`../testing/testing-strategy.md`](../testing/testing-strategy.md).

## Step 6: Read the shape of the system

Do these in order. Treat reading time as work time.

1. [`../architecture/system-overview.md`](../architecture/system-overview.md) — 15 minutes. The map.
2. [`../architecture/data-flow.md`](../architecture/data-flow.md) — 15 minutes. Tick → candle → regime → signal → gate → order.
3. [`../risk/risk-framework.md`](../risk/risk-framework.md) — 30 minutes. Required reading before you touch anything in `risk/` or `execution/`.
4. [`../ml/regime-detection.md`](../ml/regime-detection.md) — 20 minutes. Know that two regime systems coexist.
5. [`glossary.md`](glossary.md) — 10 minutes. Skim the vocabulary; come back when a term surprises you.

## Step 7: Ship your first PR

A good first PR is a doc fix, a test that pins down existing behavior, or a one-line bug fix. Follow [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md). Expect two reviewers for anything touching `risk/`, `execution/`, the scorer, or the billing webhook.

## Common gotchas

- **"Connection refused" on port 8001.** Uvicorn isn't running, or you started it on a different port. Check `--port` in your command.
- **"Binance API 401" on startup.** Testnet key is wrong, or `BINANCE_TESTNET=false` is sending you to mainnet. Always verify the base URL in the log line the adapter prints at boot.
- **"ModuleNotFoundError: coinscope_trading_engine" when running tests.** You forgot `pip install -e .` or your venv isn't active. Run `which python` to confirm.
- **The engine starts, runs for a few minutes, then goes quiet.** WebSocket path migration (2026-04-23). See [`../runbooks/troubleshooting.md`](../runbooks/troubleshooting.md) and [`../runbooks/incident-binance-ws-disconnect-2026-04-18.md`](../runbooks/incident-binance-ws-disconnect-2026-04-18.md).
- **Tests pass locally but CI fails.** Usually a dep that's installed in your venv but not pinned in `requirements.txt`. Pin it.

## When to ask for help

Ask loudly and early if:

- You are about to change anything in `coinscope_trading_engine/risk/` or `coinscope_trading_engine/execution/`.
- You think a risk threshold or Kelly parameter should change.
- You are about to switch `BINANCE_TESTNET` to `false`.
- You want to add a new exchange.

For any of the above during validation, the answer is almost always "not yet — queue it in [`../product/implementation-backlog.md`](../product/implementation-backlog.md) for post-validation."

For everything else — conventions, where a file goes, how to structure a test, how to write a doc — just ask. The cost of asking is ten minutes; the cost of guessing wrong is a review cycle.

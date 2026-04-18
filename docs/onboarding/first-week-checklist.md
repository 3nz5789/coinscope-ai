# First-Week Checklist

**Status:** current
**Audience:** a new developer in their first five days
**Related:** [`new-developer-guide.md`](new-developer-guide.md), [`glossary.md`](glossary.md), [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md)

The goal for week one is not heroics — it is to get oriented, ship something small, and earn context you'll use for months. If you work through this checklist end-to-end, you will have read the important docs, run the engine, opened a PR, and built a mental model of the system.

## Day 1 — Environment

By end of day, you can run the engine locally and hit `/scan`.

- [ ] Clone the repo. Create and activate a Python 3.11+ venv.
- [ ] Install top-level and engine requirements.
- [ ] Copy `.env.example` to `.env` and fill in Binance testnet keys. Confirm `BINANCE_TESTNET=true`.
- [ ] Bring up Redis (and Postgres if you are not using SQLite) with `docker compose up -d`.
- [ ] Start `uvicorn` and `celery`. Confirm both processes are healthy.
- [ ] `curl http://localhost:8001/health` and `curl http://localhost:8001/scan`. See non-500 responses.
- [ ] Run `pytest`. All green.

Reference: [`new-developer-guide.md`](new-developer-guide.md).

## Day 2 — Map the system

By end of day, you can draw the tick-to-order path on a napkin.

- [ ] Read [`../architecture/system-overview.md`](../architecture/system-overview.md).
- [ ] Read [`../architecture/component-map.md`](../architecture/component-map.md). Identify the scanner, scorer, regime detectors, risk gate, sizer, and executor.
- [ ] Read [`../architecture/data-flow.md`](../architecture/data-flow.md). Trace one symbol from ingest to journal.
- [ ] Skim [`../api/backend-endpoints.md`](../api/backend-endpoints.md). Know which endpoints exist and which are read-only.
- [ ] Skim [`glossary.md`](glossary.md). Bookmark it for the rest of the week.

## Day 3 — Risk and ML

By end of day, you know what "capital preservation first" means in code.

- [ ] Read [`../risk/risk-framework.md`](../risk/risk-framework.md) in full. This is the most important doc in the tree.
- [ ] Read [`../risk/risk-gate.md`](../risk/risk-gate.md). Walk the gate checks in the code.
- [ ] Read [`../risk/position-sizing.md`](../risk/position-sizing.md). Understand Kelly-fractional sizing and regime multipliers.
- [ ] Read [`../risk/failsafes-and-kill-switches.md`](../risk/failsafes-and-kill-switches.md). Know how the engine halts itself.
- [ ] Read [`../ml/ml-overview.md`](../ml/ml-overview.md). scikit-learn + hmmlearn + xgboost — no PyTorch.
- [ ] Read [`../ml/regime-detection.md`](../ml/regime-detection.md). **Note that two regime systems coexist** — the HMM (bull/bear/chop) and the v3 classifier (Trending/Mean-Reverting/Volatile/Quiet). Know which consumes which.

## Day 4 — Operations

By end of day, you can explain how a trade reaches Binance testnet, and what stops it.

- [ ] Read [`../ops/binance-adapter.md`](../ops/binance-adapter.md). Understand REST vs. WebSocket responsibilities and the 2026-04-23 path migration.
- [ ] Read [`../ops/exchange-integrations.md`](../ops/exchange-integrations.md). Know that only Binance is implemented.
- [ ] Read [`../runbooks/local-development.md`](../runbooks/local-development.md) and [`../runbooks/daily-ops.md`](../runbooks/daily-ops.md).
- [ ] Read [`../runbooks/troubleshooting.md`](../runbooks/troubleshooting.md) and the 2026-04-18 incident write-up.
- [ ] Watch the engine run for 15 minutes against testnet. Open `/performance` and `/journal`. See a real signal pass or fail the gate.

## Day 5 — Ship

By end of day, you have a PR open that reviewers can approve without changes.

- [ ] Pick one of these starter PRs (in order of preference):
  - A doc fix you noticed this week. Wrong link, stale value, missing prerequisite.
  - A test that pins down existing behavior (not one that adds a new feature).
  - A `fix/` PR for an actual bug you found while reading.
- [ ] Follow [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md). Use `feat/`, `fix/`, or `docs/` branch naming. Write a PR description with a risk note.
- [ ] Run `pytest` locally. Run `black` and `ruff`. Confirm CI is green.
- [ ] Ask a reviewer.

## What you should *not* do in week one

- Do not change risk thresholds, Kelly parameters, or circuit-breaker logic.
- Do not touch anything in `coinscope_trading_engine/risk/`, `coinscope_trading_engine/execution/`, or the Binance adapter without a reviewer who has touched those paths before.
- Do not flip `BINANCE_TESTNET` to `false` on any machine for any reason.
- Do not restructure directories inside `coinscope_trading_engine/`. The validation freeze lasts until 2026-04-30.
- Do not add a new exchange. Bybit, OKX, and Hyperliquid are queued for after validation.

## End-of-week self-check

By the end of week one, you should be able to answer all of these without looking:

1. What is the primary goal of the engine?
2. What halts the engine automatically?
3. Where is the risk gate code? Where are the Kelly parameters?
4. What is the difference between the HMM regime detector and the v3 classifier?
5. Which exchange is implemented? Which are planned?
6. What runs on port 8001? What runs on Celery?
7. Where do you add a new env var? (Two places.)
8. When does the validation freeze end?

If you can't answer any of them, go back to the relevant doc. If a doc doesn't answer it, file an issue — that's exactly the gap this checklist is meant to surface.

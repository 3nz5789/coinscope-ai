# Repository Map

**Status:** current
**Audience:** anyone opening the repo for the first time, or trying to find where something lives
**Related:** [`README.md`](README.md), [`repo-audit.md`](repo-audit.md), [`../CONTRIBUTING.md`](../CONTRIBUTING.md)

This page explains every top-level folder in the CoinScopeAI repository — what lives in it, who maintains it, and when to touch it. If you find yourself asking "where should this file go?", this is the right page.

The repo was restructured on 2026-04-18. Historical context — what the tree looked like before, and why things moved — is captured in [`repo-audit.md`](repo-audit.md). The internal layout of `coinscope_trading_engine/` is **frozen during the validation phase (2026-04-10 to 2026-04-30)**; queued internal refactors land after 2026-04-30.

## Top-level tree

```
CoinScopeAI/
├── README.md                       — one-page repo overview
├── CONTRIBUTING.md                 — how to commit, branch, PR, test
├── CODEOWNERS                      — review ownership
├── .env.example                    — template for local config
├── docker-compose.yml              — local stack (engine + Redis + Postgres)
├── prometheus.yml                  — local Prometheus scrape config
├── requirements.txt                — top-level Python deps (engine)
├── billing_server.py               — Stripe webhook + entitlement HTTP server
├── coinscope_trading_engine/       — the engine (FROZEN during validation)
├── billing/                        — billing module source (coexists with billing_server.py)
├── ml/                             — ML training scripts + saved artifacts
├── scripts/                        — operator scripts (scans, backfills, utilities)
├── tests/                          — repo-wide tests (engine tests live inside engine/)
├── docs/                           — this documentation tree
├── archive/                        — historical files, not load-bearing
└── .github/                        — CI workflows and templates
```

## Folder-by-folder

### `coinscope_trading_engine/` — the engine (FROZEN)

The core Python package that runs the signal → risk → execute loop. Everything the product does at runtime is here.

- **Who owns it:** @3nz5789 (see `/CODEOWNERS`)
- **When to touch it:** bug fixes and new tests are fine with PR review. Renaming, restructuring, or changing risk thresholds is **blocked until 2026-04-30**. See [`../CONTRIBUTING.md`](../CONTRIBUTING.md#validation-freeze-2026-04-10-to-2026-04-30).
- **What's inside, at a high level:** scanners, scorer, regime detectors, risk gate, Kelly sizer, circuit breakers, Binance adapter, execution loop, FastAPI app, journal, metrics. The per-module breakdown lives in [`architecture/component-map.md`](architecture/component-map.md).
- **Planned internal reorg:** collapse the `core/` vs root duplication, merge `scanner/` and `scanners/`, flatten top-level `.py` files into explicit subpackages. Queued in [`product/implementation-backlog.md`](product/implementation-backlog.md).

### `billing/` and `billing_server.py` — commercial layer

Two coexisting entry points for the Stripe billing flow. The intent is that `billing_server.py` is the production HTTP server and `billing/` holds the package code it imports — but the two have drifted and there is duplication. This is a known debt item.

- **When to touch:** billing PRs should run `pytest tests/test_billing_*` locally, add a reviewer who has touched this before, and call out which path (module vs. server) was modified. Do not silently consolidate the two during the freeze.
- **Where to read more:** [`ops/stripe-billing.md`](ops/stripe-billing.md) for the model, [`ops/stripe-billing-runbook.md`](ops/stripe-billing-runbook.md) for day-to-day ops.
- **Secrets:** Stripe keys belong in the environment only. See [`backend/configuration.md`](backend/configuration.md).

### `ml/` — training scripts and saved artifacts

Offline ML code: feature engineering notebooks, training drivers, and the serialized artifacts (`.pkl`, `.joblib`) that the engine loads at startup.

- **Stack:** scikit-learn + hmmlearn + xgboost. **No PyTorch.** Older briefs referenced PyTorch; the reality is classical ML plus an HMM and gradient-boosted trees.
- **Two regime systems coexist:** the HMM detector (bull/bear/chop) and the v3 classifier (Trending, Mean-Reverting, Volatile, Quiet). Both are documented in [`ml/regime-detection.md`](ml/regime-detection.md).
- **When to touch:** retraining is safe during the freeze as long as the saved artifact filenames the engine loads stay the same. Changing the feature contract is engine-adjacent and needs review.

### `scripts/` — operator scripts

One-off and recurring CLI scripts that the operator runs by hand or from cron. Think backfills, daily scans, data dumps, smoke checks. Not imported by the engine; invoked externally.

- **Convention:** every script starts with a header block stating what it does, what it writes, and whether it is safe to re-run.
- **When to add:** if you find yourself pasting a Python one-liner into a terminal twice, make it a script here.

### `tests/` — repo-wide tests

Tests that cut across the engine, billing, and scripts. Engine-internal tests live inside `coinscope_trading_engine/tests/` so they ship with the package.

- **Run everything:** `pytest` from the repo root.
- **Convention:** mirror the module path. A test for `billing/webhook.py` lives at `tests/test_billing_webhook.py`.
- **Integration tests** that talk to Binance testnet are marked `@pytest.mark.integration` and opt-in via `pytest -m integration`.
- See [`testing/testing-strategy.md`](testing/testing-strategy.md) for the full taxonomy.

### `docs/` — this documentation tree

Everything a developer or operator needs to understand, run, or change the engine. Organized by audience, not by file type. Starting point is [`docs/README.md`](README.md).

- **Convention:** every page starts with `Status` / `Audience` / `Related` headers. `planned` docs describe intent; `current` docs describe reality.
- **When to update:** in the same PR as the code. The doc checklist is in [`../CONTRIBUTING.md`](../CONTRIBUTING.md#adding-or-updating-docs).

### `archive/` — historical, non-load-bearing

Files kept for history but no longer imported or referenced. Includes Finder-duplicated engine snapshots (`coinscope_trading_engine 2/3/4/`), a `fixed/` patch folder from 2026-04-11, legacy macOS `.command` bootstrap scripts, Scoopy/Manus skill artifacts, historical `.docx` exports, prior doc-update reports, and old point-in-time audit / health / review docs.

- **Safety valve:** nothing here is in `.gitignore`. History is preserved; you can `git mv` anything back out.
- **Deletable after 2026-07-01** if nobody has needed it by then.
- **Full inventory:** [`../archive/README.md`](../archive/README.md).

### `.github/` — CI and automation

GitHub Actions workflows (`ci.yml`), issue templates, and PR templates. Changes here need a reviewer who has touched CI before, because a broken workflow silently lets bad code through.

### Top-level configs

- `docker-compose.yml` — local stack: engine, Redis, Postgres, Prometheus. Not the production compose; ops guidance is in [`runbooks/digitalocean-deployment.md`](runbooks/digitalocean-deployment.md).
- `prometheus.yml` — local scrape config for the metrics endpoint. Production Prometheus runs separately.
- `requirements.txt` — top-level Python deps; the engine may pin more tightly in its own `requirements.txt` inside `coinscope_trading_engine/`.
- `.env.example` — template. The real `.env` never lands in git. Full variable reference in [`backend/configuration.md`](backend/configuration.md).

## What is *not* in this repo

Some things developers reasonably expect to find here live elsewhere. Knowing what's out of scope saves search time.

- **The React dashboard at https://coinscope.ai/.** Separate repository. Not in this tree. When the UI and the engine disagree, the engine is authoritative.
- **Production Kubernetes manifests.** There are none. Deployment is Docker Compose on a VPS today. See [`runbooks/digitalocean-deployment.md`](runbooks/digitalocean-deployment.md).
- **Bybit, OKX, Hyperliquid adapters.** Planned, not built. Only Binance is implemented. Placeholder refs in the codebase are aspirational.
- **The Notion workspace / Linear project.** Operational — not code. Paths and IDs live in the operator's memory / skills, not this repo.
- **Secrets, API keys, Stripe dashboard state.** Ephemeral by design. `.env`, `*.key`, and `billing_subscriptions.db` are git-ignored.

## Where should this go?

A quick cheat sheet for "I have a new file, where does it belong?"

| The file is… | Put it in… |
| --- | --- |
| A new engine module | `coinscope_trading_engine/<subpackage>/` — but **not** during validation freeze |
| A one-off backfill or scan | `scripts/` |
| A feature or bug-fix test | next to the module it tests (`coinscope_trading_engine/tests/` or `tests/`) |
| A runbook or operator checklist | `docs/runbooks/` |
| A design decision with trade-offs | `docs/decisions/adr-XXXX-<slug>.md` |
| A new env var | `.env.example` **and** `docs/backend/configuration.md` |
| A new API endpoint | code in the engine, reference in `docs/api/backend-endpoints.md` |
| An ML training notebook | `ml/` |
| A historical artifact you don't want to lose | `archive/<subfolder>/` |
| A Stripe dashboard screenshot, deal doc, or anything non-code | not in this repo — use the project's Notion / Drive |

If none of these fit, open an issue before adding the file. We'd rather resolve the placement once than have every contributor invent their own.

# Docs Restructure — Summary

**Status:** current
**Date:** 2026-04-18
**Audience:** anyone opening `docs/` for the first time after the restructure and wondering what changed
**Related:** [`README.md`](README.md), [`repo-audit.md`](repo-audit.md), [`repository-map.md`](repository-map.md), [`../archive/README.md`](../archive/README.md)

This document is the capstone for the 2026-04-18 documentation restructure. It records what was added, what moved, what was archived, and where to go from here. It is meant to be read once.

The restructure happened while the engine is in its 30-day validation freeze (2026-04-10 → 2026-04-30). **No engine code was changed.** Only documentation was added, relocated, and renamed.

## Goals

1. Make it possible to go from "fresh clone" to "running the engine and reading a signal" in one afternoon, using `docs/` alone.
2. Remove ambiguity between what the engine *is* today and what it *might become*. Every doc now carries a `Status` of `current`, `draft`, or `planned`.
3. Stop the documentation drift where three folders (`docs/`, repo-root markdown, Google Drive exports) each claimed to be authoritative. There is now one authoritative tree: `docs/`.
4. Capture the institutional reasoning behind architectural choices before the people who made them forgot. That lives in `docs/decisions/` as ADRs.
5. Leave the repo runnable. No imports were moved, no config paths changed.

## What the reader should do next

- New contributor → [`onboarding/new-developer-guide.md`](onboarding/new-developer-guide.md), then [`onboarding/first-week-checklist.md`](onboarding/first-week-checklist.md).
- PR reviewer or designer → [`architecture/system-overview.md`](architecture/system-overview.md) and [`risk/risk-framework.md`](risk/risk-framework.md).
- Operator on-call → [`runbooks/daily-ops.md`](runbooks/daily-ops.md) and [`runbooks/troubleshooting.md`](runbooks/troubleshooting.md).
- Planning post-validation work → [`product/implementation-backlog.md`](product/implementation-backlog.md) and [`architecture/future-state-roadmap.md`](architecture/future-state-roadmap.md).

The [`README.md`](README.md) in this folder is the canonical index. Start there if you are unsure.

## What was added

46 markdown files now live under `docs/`, totaling ~8,600 lines. Of those, the following were written or fully rewritten during the restructure.

### Root index and maps

| File | Purpose |
| --- | --- |
| [`README.md`](README.md) | Canonical docs index, organized by audience and topic. |
| [`repository-map.md`](repository-map.md) | Every top-level folder in the repo, explained. |
| [`repo-audit.md`](repo-audit.md) | Pre-restructure snapshot of the repo. |
| [`RESTRUCTURE_SUMMARY.md`](RESTRUCTURE_SUMMARY.md) | This document. |

### Onboarding

| File | Purpose |
| --- | --- |
| [`onboarding/new-developer-guide.md`](onboarding/new-developer-guide.md) | Environment setup end to end. |
| [`onboarding/first-week-checklist.md`](onboarding/first-week-checklist.md) | Five-day path to shipping a first PR. |
| [`onboarding/glossary.md`](onboarding/glossary.md) | Vocabulary: regime, heat, confluence, WFV, Kelly fraction, etc. |

### Architecture

| File | Purpose |
| --- | --- |
| [`architecture/system-overview.md`](architecture/system-overview.md) | One-page view of the full engine. |
| [`architecture/component-map.md`](architecture/component-map.md) | Module-by-module inventory with callers. |
| [`architecture/data-flow.md`](architecture/data-flow.md) | Tick → candle → regime → signal → risk → sized trade → journal. |
| [`architecture/future-state-roadmap.md`](architecture/future-state-roadmap.md) | Multi-exchange, mainnet, post-validation directions. `Status: planned`. |

### Backend and API

| File | Purpose |
| --- | --- |
| [`backend/backend-overview.md`](backend/backend-overview.md) | FastAPI + uvicorn + Celery + Redis + SQLite/Postgres. |
| [`backend/configuration.md`](backend/configuration.md) | Every env var, default, and where it is read. |
| [`api/api-overview.md`](api/api-overview.md) | Auth, error envelope, rate limiting, base URL. |
| [`api/backend-endpoints.md`](api/backend-endpoints.md) | Full endpoint reference with request/response shapes. |

### Risk and ML

| File | Purpose |
| --- | --- |
| [`risk/risk-framework.md`](risk/risk-framework.md) | Risk philosophy, thresholds, invariants. Mandatory reading for risk-adjacent PRs. |
| [`risk/risk-gate.md`](risk/risk-gate.md) | Pre-trade gate that accepts or rejects a signal. |
| [`risk/position-sizing.md`](risk/position-sizing.md) | Kelly-fractional sizing and regime multipliers. |
| [`risk/failsafes-and-kill-switches.md`](risk/failsafes-and-kill-switches.md) | Circuit breakers, daily-loss lockout, manual kill switch. |
| [`ml/ml-overview.md`](ml/ml-overview.md) | scikit-learn + hmmlearn + xgboost stack. Explicitly no PyTorch/TensorFlow. |
| [`ml/regime-detection.md`](ml/regime-detection.md) | HMM (bull/bear/chop) and v3 classifier (Trending/Mean-Reverting/Volatile/Quiet). |

### Ops and runbooks

| File | Purpose |
| --- | --- |
| [`ops/exchange-integrations.md`](ops/exchange-integrations.md) | Adapter contract and the Binance-first policy. |
| [`ops/binance-adapter.md`](ops/binance-adapter.md) | REST, WebSocket, signing, and the 2026-04-23 path migration. |
| [`ops/telegram-alerts.md`](ops/telegram-alerts.md) | Bot setup, severity tiers, rate limits, failure modes. |
| [`ops/stripe-billing.md`](ops/stripe-billing.md) | Product model, webhook flow, entitlement gating. |
| [`runbooks/local-development.md`](runbooks/local-development.md) | Running the engine on a laptop against Binance Testnet. |
| [`runbooks/daily-ops.md`](runbooks/daily-ops.md) | Five-minute morning check and event-driven response during validation. |
| [`runbooks/release-checklist.md`](runbooks/release-checklist.md) | Pre-PR, pre-deploy, during-deploy, post-deploy, rollback. |

### Testing

| File | Purpose |
| --- | --- |
| [`testing/testing-strategy.md`](testing/testing-strategy.md) | Test pyramid: ~75% unit, ~20% integration, <5% replay. |
| [`testing/local-validation-checklist.md`](testing/local-validation-checklist.md) | What to run before pushing risk-adjacent code. |

### Decisions

| File | Purpose |
| --- | --- |
| [`decisions/README.md`](decisions/README.md) | How we write ADRs. |
| [`decisions/TEMPLATE.md`](decisions/TEMPLATE.md) | Copy this when opening a new ADR. |
| [`decisions/adr-0001-fastapi-and-uvicorn.md`](decisions/adr-0001-fastapi-and-uvicorn.md) | FastAPI + uvicorn + Pydantic v2. |
| [`decisions/adr-0002-redis-celery-for-workers.md`](decisions/adr-0002-redis-celery-for-workers.md) | Redis + Celery for the async worker path. |
| [`decisions/adr-0003-llm-off-hot-path.md`](decisions/adr-0003-llm-off-hot-path.md) | No LLM on the trading hot path. |

### Product

| File | Purpose |
| --- | --- |
| [`product/implementation-backlog.md`](product/implementation-backlog.md) | Canonical list of accepted-but-deferred work for after validation. |

## What was kept in place

The following docs existed before the restructure and were kept where they were because they are already well-scoped. They did receive cross-link updates to the new tree.

- [`project-history.md`](project-history.md)
- [`ml/confidence_scoring_baseline.md`](ml/confidence_scoring_baseline.md)
- [`ops/stripe-billing-runbook.md`](ops/stripe-billing-runbook.md)
- [`runbooks/cloud-deployment-guide.md`](runbooks/cloud-deployment-guide.md)
- [`runbooks/daily-market-scan-runbook.md`](runbooks/daily-market-scan-runbook.md)
- [`runbooks/digitalocean-deployment.md`](runbooks/digitalocean-deployment.md)
- [`runbooks/incident-binance-ws-disconnect-2026-04-18.md`](runbooks/incident-binance-ws-disconnect-2026-04-18.md)
- [`runbooks/troubleshooting.md`](runbooks/troubleshooting.md)
- [`testing/qa-billing-coi39-2026-04-15.md`](testing/qa-billing-coi39-2026-04-15.md)
- [`testing/qa-risk-daily-loss-halt-2026-04-16.md`](testing/qa-risk-daily-loss-halt-2026-04-16.md)
- [`testing/qa-ws-replay-consistency-2026-04-16.md`](testing/qa-ws-replay-consistency-2026-04-16.md)

These eight-of-eleven migrated-in-place docs do not yet carry the standard `Status`/`Audience`/`Related` header. They are listed in [`product/implementation-backlog.md`](product/implementation-backlog.md) under a docs-grooming item and will be given the header in a post-validation pass. The content is accurate; only the frontmatter is non-conforming.

## What was archived

Nothing that might still be useful was deleted. Everything that was displaced lives under [`/archive/`](../archive/) with an index at [`/archive/README.md`](../archive/README.md) explaining why each subfolder is there and when it is safe to delete.

Summary:

| Subfolder | What | Why archived |
| --- | --- | --- |
| `duplicate_engine_snapshots/` | Finder-duplicated copies of `coinscope_trading_engine 2/3/4/` plus a tarball and zip | Canonical engine is at repo root. These were 2026-04-05 backups. |
| `fixed_patches_2026-04-11/fixed/` | Older patched module versions | Keep until a per-file diff confirms every patch landed in the live engine. |
| `legacy_scripts/` | `.command` launchers, `setup_engine.sh`, `github_setup.sh` | Machine-specific bootstrapping; replaced by the quick-start in the root `README.md`. |
| `skill_artifacts/` | Scoopy/Manus tooling exports | Not used by the engine itself. |
| `docx_exports/` | Google Drive `.docx` exports of earlier docs | Markdown equivalents live under `docs/`. |
| `doc_update_reports/` | `DOC_UPDATE_REPORT_2026-04-*.md` daily reports | Historical audit trail. |
| `historical_reports/` | Old audit, code review, health, integration, SOP, workspace-setup, and context docs | The current view of each subject is in `docs/`. |
| `unrelated/` | `ps-form-1583-june-2024.pdf` | Misfiled personal document. |

## What changed at the repo root

The following root-level files were added or rewritten during the restructure. No engine source files were touched.

- [`../README.md`](../README.md) — rewritten as a one-page repo overview with quick-start, status, and links into `docs/`.
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — contribution and docs-update checklist.
- [`../CODEOWNERS`](../CODEOWNERS) — review routing.
- [`../.env.example`](../.env.example) — refreshed to match `backend/configuration.md`.

## Conventions the new tree enforces

- **Every doc starts with a three-line header:** `Status`, `Audience`, `Related`. Status is one of `current`, `draft`, `planned`.
- **File names are lowercase-hyphen.** No spaces, no underscores, no title case. Existing non-conforming files were left in place to avoid breaking external links; new files follow the rule.
- **Links inside `docs/` are relative.** Links to code use repo-rooted paths (e.g. `/coinscope_trading_engine/risk_gate.py`).
- **Dates are absolute.** "2026-04-18", never "last week".
- **Code blocks declare a language** for syntax highlighting.
- **Update the doc in the PR that changes the code.** `CONTRIBUTING.md` lists the doc-update checklist.

## Verification

At the end of the restructure we ran two checks.

**Markdown link check.** 345 inline links across all 46 docs in `docs/` were resolved against the filesystem. 0 broken. This was run with a small Python script that walks `docs/`, finds every `](target)` link that is not `http(s)://` or `mailto:`, and verifies the target path exists.

**Repo-rooted-path check.** 125 occurrences of `/…`-prefixed tokens (either in markdown-link form or in backticks) were inspected. The apparent misses are all HTTP endpoint paths (`/scan`, `/ready`, `/metrics`) and Binance WebSocket stream suffixes (`/public`, `/private`, `/market`) rather than filesystem paths. The references to actual source files (`/coinscope_trading_engine/...`) all resolved.

Both checks can be re-run from the repo root:

```bash
python3 - <<'PY'
import re, pathlib
root = pathlib.Path('docs').resolve()
broken = []
for md in root.rglob('*.md'):
    text = md.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'\]\(([^)#\s]+)(#[^)\s]*)?\)', text):
        t = m.group(1)
        if t.startswith(('http://','https://','mailto:')):
            continue
        dest = (root.parent / t.lstrip('/')).resolve() if t.startswith('/') else (md.parent / t).resolve()
        if not dest.exists():
            broken.append((md.relative_to(root), t))
print(f"broken: {len(broken)}")
for row in broken: print(row)
PY
```

## Open items

These are known-deferred and live in [`product/implementation-backlog.md`](product/implementation-backlog.md).

- A docs-grooming pass to add the standard header to the eight migrated-in-place docs listed under "What was kept in place."
- A frontend / React dashboard doc set. That dashboard lives in its own repo and has its own docs surface; a stub in `docs/frontend/` is intentionally empty until we decide whether to mirror or just link.
- A mainnet cutover runbook. Flagged P0 in the backlog. To be written in the week after validation closes.
- Per-exchange adapter docs for Bybit, OKX, Hyperliquid. Flagged P1/P2/P3. Each will be authored against the typed `Adapter` protocol when the second adapter lands and forces it to exist.
- An SRE/observability doc set (Prometheus queries, SLOs, paging rules).

## How to update this summary

Do not. This document is point-in-time. If another restructure happens later, write a new summary at `docs/RESTRUCTURE_SUMMARY_YYYY-MM-DD.md` and mark this one `superseded by …` in the header. The list of docs in this tree is maintained in [`README.md`](README.md), not here.

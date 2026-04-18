# Repository Audit — CoinScopeAI

**Author:** Scoopy (restructure pass)
**Date:** 2026-04-18
**Status:** Current (audit snapshot)
**Audience:** Project lead, future maintainers, onboarding engineers
**Related:** `docs/repository-map.md` (proposed), `README.md`

> Phase 1 deliverable. This document describes the repository *as it is today*, identifies pain points, and proposes the restructure principles that the rest of the documentation set will apply. No files are moved by this document — it is a plan, not a change.

---

## 1. Executive summary

CoinScopeAI is, in practice today, a **Python-only backend project**: a FastAPI scanner + Celery worker + Binance-testnet execution system, plus a thin HTML billing dashboard. The repo at `/Users/mac/Documents/Claude/Projects/CoinScopeAI` also carries a large amount of **documentation, archives, skill definitions, and duplicated engine snapshots** mixed into the root.

The codebase itself is reasonably organized inside `coinscope_trading_engine/`, but the repository root is noisy, several duplicated copies of the engine folder exist, and developer-facing documentation is scattered across the root, `docs/`, and exported `.docx` files.

Given the project is in a **30-day validation phase (Apr 10–30, 2026)** with an explicit "no core engine changes" policy, this audit deliberately separates:

- **Safe-now moves**: root-level cleanup, archive of duplicates, doc consolidation.
- **Deferred refactors**: anything that reorganizes modules *inside* `coinscope_trading_engine/` or changes import paths.

The validation freeze is respected below.

---

## 2. What the repo actually contains

### 2.1 Top-level structure (current)

| Path | Purpose | State |
| --- | --- | --- |
| `coinscope_trading_engine/` | Primary Python engine — FastAPI, Celery, scanners, risk, signals, ML | Load-bearing, **do not restructure during validation** |
| `coinscope_trading_engine 2/` | Finder-duplicated snapshot (2026-04-05) | Stale, archive candidate |
| `coinscope_trading_engine 3/` | Finder-duplicated snapshot (2026-04-05) | Stale, archive candidate |
| `coinscope_trading_engine 4/` | Finder-duplicated snapshot (2026-04-05) | Stale, archive candidate |
| `coinscope_trading_engine.tar.gz` | Archive of an older engine state | Archive candidate |
| `coinscope_ai_project.zip` | Archive | Archive candidate |
| `billing/` | Stripe billing subsystem (webhooks, entitlements, Postgres store) | Load-bearing, in validation |
| `billing_server.py` | Standalone billing FastAPI app at repo root | Possibly redundant with `billing/` — needs owner confirmation |
| `billing_subscriptions.db`, `.db-journal` | Local SQLite snapshot | Should be gitignored, not committed |
| `dashboard/` | 3 static HTML files: `pricing.html`, `billing_success.html`, `pnl_widget.html` | **Not a React app.** Real React dashboard lives outside this repo (coinscope.ai) |
| `ml/` | Regime classifier v3 + dataset loader | Load-bearing |
| `data/funding_rates/` | Persisted funding-rate cache | Load-bearing |
| `docs/` | Small set of runbooks, QA reports, one ML note | Partial — will become the canonical docs home |
| `tests/` | Root-level billing + smoke tests | Load-bearing (do not move during freeze) |
| `scripts/` | 3 operational Python scripts (reconciliation, Stripe setup, watchdog) | Load-bearing |
| `fixed/` | Older patched versions of engine files (Apr 11 snapshot) | Historical, archive candidate |
| `incidents/` | Incident artifacts | Load-bearing (preserve) |
| `research/` | Research notes | Preserve |
| `tasks/` | Task-tracking scratch | Preserve |
| `skills/`, `coinscopeai-skills/`, `market_scanner_skill/`, `manus_setup/`, `manus_upload/`, `crypto_futures_dev/` | Multiple overlapping skill/tooling dirs | Needs owner decision — candidate for `tools/skills/` consolidation |
| `binance-futures-api.skill`, `market_scanner_skill.zip`, `binance-skill-review.html`, `telegram-alerts-skill-review.html` | Skill artifacts + review pages at root | Archive candidate |
| `.github/workflows/ci.yml` | CI pipeline (Python-only, no frontend build) | Load-bearing |
| `docker-compose.yml` | Compose stack for engine | Load-bearing — should live under `infra/` long-term |
| `prometheus.yml` | Prometheus scrape config | Load-bearing — should live under `infra/monitoring/` long-term |
| `requirements.txt` | Python dependencies | Load-bearing |
| `setup_engine.sh`, `github_setup.sh`, `*.command` | Legacy shell + macOS `.command` scripts | Mostly obsolete; archive or consolidate under `scripts/` |

### 2.2 Inside `coinscope_trading_engine/`

- **Entrypoints:** `main.py` (engine orchestrator), `api.py` (FastAPI on :8001).
- **Organized subpackages:** `signals/`, `risk/`, `execution/`, `scanner/`, `scanners/` (note: both singular and plural exist), `data/`, `models/`, `storage/`, `alerts/`, `monitoring/`, `billing/`, `intelligence/`, `live/`, `utils/`, `validation/`, `tests/`.
- **Many top-level `.py` files** that look like they should be inside a subpackage: `alpha_decay_monitor.py`, `kelly_position_sizer.py`, `hmm_regime_detector.py`, `funding_rate_filter.py`, `multi_timeframe_filter.py`, `whale_signal_filter.py`, `pair_monitor.py`, `metrics_exporter.py`, `portfolio_sync.py`, `retrain_scheduler.py`, `scale_up_manager.py`, `realtime_dashboard.py`, `trade_journal.py`, `trade_logger.py`, `testnet_check.py`, etc.
- **Name-collision with duplicated files:** `trade_journal.py` + `trade_journal (2).py`, `whale_signal_filter.py` + `whale_signal_filter (1).py`. These Finder-duplicate filenames should be resolved (keep one, archive the other).
- **`core/` duplication:** `core/risk_gate.py`, `core/scoring_fixed.py`, `core/multi_timeframe_filter.py` *also* appear at the engine root as `risk_gate.py`, `scoring_fixed.py`, `multi_timeframe_filter.py`. One set must be canonical — current import graph should be checked before any move.

### 2.3 Existing `/docs/` content

Already committed under `docs/`:

- `BILLING_Stripe_Setup_Runbook.md`
- `INCIDENT_Binance_WS_Disconnect_Storm_2026-04-18.md`
- `OPS_Daily_Market_Scan_Runbook.md`
- `QA_BILLING_COI39_2026-04-15.md`
- `QA_RISK_DailyLossHalt_2026-04-16.md`
- `QA_WS_REPLAY_CONSISTENCY_2026-04-16.md`
- `ml/confidence_scoring_baseline.md`

These are good seeds — but need to be organized under clearly named subfolders (`runbooks/`, `qa/`, `incidents/`, `ml/`, etc.) and referenced from an index.

---

## 3. Major pain points

### 3.1 Root-level noise

The repo root has **18 markdown files, 6 `.docx` files, 2 binary archives, 4 `.command` scripts, 2 loose HTML skill reviews, 1 skill bundle, and 1 unrelated `.pdf` (USPS form 1583)**. A new engineer opening this directory cannot quickly tell what is code, what is doc, and what is history.

### 3.2 Duplicated engine snapshots

Three identically-named copies (`coinscope_trading_engine 2/`, `... 3/`, `... 4/`) from **2026-04-05** plus an older `.tar.gz` and a `fixed/` directory of patched modules. These are almost certainly Finder-duplication artifacts from a previous restructure attempt. Keeping them in-tree creates:

- Confusion about which engine is canonical.
- False positives when grepping for symbols.
- Repo bloat.

### 3.3 Mixed concerns in the root

- Billing artifacts (`billing_server.py`, `billing_subscriptions.db`) live *next to* the billing package (`billing/`) and inside the engine (`coinscope_trading_engine/billing/`) — three places to look for billing logic.
- Static HTML billing pages (`dashboard/*.html`) exist at repo root but are clearly part of the billing flow.
- Skills are spread across four directories.

### 3.4 Naming issues

- **Singular vs plural collision** inside the engine: `scanner/` and `scanners/` both exist with overlapping responsibilities.
- **`fixed/`** has no semantic meaning — it appears to be "the patched versions I applied later". Either those changes are in `coinscope_trading_engine/` now (in which case `fixed/` should be archived) or they aren't (in which case this is a hidden divergence).
- **"(1)", "(2)"** suffixes on duplicated filenames.
- **File-per-concept at engine root** (`kelly_position_sizer.py`, `hmm_regime_detector.py`, …) should be grouped into subpackages — but this is deferred until after validation.

### 3.5 Module boundary issues (deferred refactors)

These are real but **not safe to touch during validation**:

- `core/` duplicates modules at engine root — one set needs to be canonical.
- Scanners are split across `scanner/` and `scanners/`.
- Risk logic lives in `risk/`, `risk_gate.py` (root), and `core/risk_gate.py`.
- `intelligence/`, `signals/`, and `ml/` (both inside engine and at repo root) have unclear boundaries for ML vs signal scoring.

These should be consolidated **after** 2026-04-30 (end of validation).

### 3.6 Missing docs

Compared to what a production-candidate project needs, the repo lacks:

- Onboarding flow (no new-developer guide, no first-week checklist, no glossary).
- Architecture docs (no system overview, no component map, no data flow).
- Backend deep-dive (no service boundary map, no domain-model doc, no config reference, no background-job doc, no error-handling doc).
- API reference (no enumerated contract for `/scan`, `/status`, `/signals`, `/positions`, `/exposure`, `/regime`, `/sentiment`, `/health`, `/circuit-breaker/*`, `/rate-limiter/stats`, `/config`).
- Risk framework docs (risk gate, position sizing, failsafes and kill-switch decision tree — note: `RISK_KillSwitch_DecisionTree.docx` exists but not as markdown).
- ML docs (feature pipeline, model lifecycle, regime detection explanation, sentiment pipeline — note: `docs/ml/confidence_scoring_baseline.md` is a seed).
- Exchange integration docs (Binance adapter, future Bybit adapter).
- Testing strategy + test matrix.
- Runbook index.
- ADR index — no `docs/decisions/` exists yet.
- Contributor guide (`CONTRIBUTING.md`).
- `CODEOWNERS`.

---

## 4. What the original brief assumed vs. what the repo actually contains

The overarching brief listed technologies the repo does **not** currently contain. For honesty and to avoid the "invented features" anti-pattern, I am recording the reality explicitly:

| Brief claim | Repo reality |
| --- | --- |
| React 18, TypeScript, Vite, Tailwind CSS | Not in this repo. 3 static HTML files in `dashboard/` only. The coinscope.ai dashboard lives in a separate codebase. |
| PyTorch | Not in `requirements.txt`. Actual ML: `scikit-learn`, `hmmlearn`. |
| PostgreSQL | Optional — billing uses SQLite locally (`billing_subscriptions.db`); `pg_subscription_store.py` exists for Postgres as an alternative. Engine persistence is primarily files + Redis. |
| Redis | Listed in README, used by Celery; present via `docker-compose.yml`. Load-bearing. |
| Kubernetes | No `k8s/` manifests in repo. Only `docker-compose.yml`. K8s is **planned**, not implemented here. |
| Bybit, OKX, Hyperliquid integrations | Only Binance is implemented. Other exchanges are **planned**. |
| OpenAI API | No direct OpenAI client code in the repo surface I inspected. If used, it is not primary. |

All doc pages that discuss these items will be labeled **planned** / **draft** / **current** so readers don't mistake aspiration for implementation.

---

## 5. Restructuring principles

The rest of the restructure follows these rules, in priority order:

1. **Preserve behavior.** The engine must start and tests must pass after every step. Any change that could break imports is deferred.
2. **Respect the validation freeze.** No reorganization *inside* `coinscope_trading_engine/` until after 2026-04-30.
3. **Root cleanup first.** Moving files *out of* the root into semantic folders is low-risk and high-value. This is where the bulk of Phase 2 effort goes.
4. **Archive, don't delete.** Stale duplicates move to `archive/` with a `README.md` explaining what and why.
5. **Docs are the product.** Most of the value delivered in this pass is documentation. Code reorganization is deliberately conservative.
6. **Distinguish *is* from *will be*.** Every doc page declares `Status: current | draft | planned` at the top.
7. **Cross-link everything.** Docs link to related docs and to actual repo paths.
8. **No invented surface.** If a module, env var, endpoint, or integration isn't in the repo, it is either labeled *planned* or left out entirely.

---

## 6. Proposed target structure (post-restructure, validation-safe scope)

Changes that are safe now, given the freeze:

```
/
├── README.md                       (updated)
├── CONTRIBUTING.md                 (new)
├── CODEOWNERS                      (new — placeholder, single owner for now)
├── .env.example                    (rewritten from .env.template, organized by domain)
├── .gitignore                      (keep)
├── requirements.txt                (keep — engine root has its own too)
├── docker-compose.yml              (keep at root for now; move to infra/ post-freeze)
├── prometheus.yml                  (keep at root for now)
│
├── coinscope_trading_engine/       (UNCHANGED during validation freeze)
├── billing/                        (UNCHANGED during validation freeze)
├── ml/                             (UNCHANGED during validation freeze)
├── dashboard/                      (UNCHANGED — billing static pages)
├── data/                           (UNCHANGED — runtime data)
├── scripts/                        (UNCHANGED — ops scripts)
├── tests/                          (UNCHANGED)
├── incidents/                      (UNCHANGED)
├── research/                       (UNCHANGED)
│
├── docs/                           (EXPANDED — see Section 7)
│   ├── README.md
│   ├── repo-audit.md               ← this document
│   ├── repository-map.md
│   ├── architecture/
│   ├── backend/
│   ├── api/
│   ├── ml/
│   ├── risk/
│   ├── ops/
│   ├── runbooks/
│   ├── frontend/                   (thin — documents the billing HTML only; the React app lives elsewhere)
│   ├── testing/
│   ├── decisions/
│   ├── onboarding/
│   └── product/
│
└── archive/                        (new)
    ├── README.md                   (explains what's here and why)
    ├── duplicate_engine_snapshots/
    │   ├── coinscope_trading_engine 2/
    │   ├── coinscope_trading_engine 3/
    │   ├── coinscope_trading_engine 4/
    │   ├── coinscope_trading_engine.tar.gz
    │   └── coinscope_ai_project.zip
    ├── fixed_patches_2026-04-11/   (the fixed/ folder moved here)
    ├── legacy_scripts/             (.command files, setup_engine.sh, github_setup.sh)
    ├── skill_artifacts/            (binance-skill-review.html, telegram-alerts-skill-review.html, binance-futures-api.skill, market_scanner_skill.zip)
    ├── docx_exports/               (the 6 .docx files at repo root — keep .md docs in /docs, keep the exports archived)
    ├── doc_update_reports/         (DOC_UPDATE_REPORT_*.md, HEALTH_REPORT_*.md — history, not current)
    └── unrelated/                  (ps-form-1583-june-2024.pdf and anything else that doesn't belong)
```

Out-of-scope for this pass (queue for post-validation, 2026-05-01+):

- Splitting `coinscope_trading_engine/` into a proper `app/` tree with `api/`, `services/`, `engine/`, `integrations/`, `data/`, `ml/`, `workers/`, `utils/`.
- Resolving `core/` vs root-level module duplication inside the engine.
- Merging `scanner/` and `scanners/`.
- Moving `docker-compose.yml`, `prometheus.yml` into `infra/`.

---

## 7. Proposed documentation set

Rather than promise all 50 docs the brief lists and ship empty stubs, I propose a **tiered delivery** so each doc that ships is real and implementation-usable:

**Tier 1 — ships in this pass (highest onboarding + ops leverage):**

- `README.md` (rewrite, reality-aligned)
- `CONTRIBUTING.md`
- `.env.example` (cleaned, organized by domain — reconciled against `.env.template`)
- `docs/README.md` (doc index)
- `docs/repository-map.md`
- `docs/onboarding/new-developer-guide.md`
- `docs/onboarding/first-week-checklist.md`
- `docs/onboarding/glossary.md`
- `docs/architecture/system-overview.md`
- `docs/architecture/component-map.md`
- `docs/architecture/data-flow.md`
- `docs/architecture/future-state-roadmap.md` (explicit implemented / partial / planned split)
- `docs/backend/backend-overview.md`
- `docs/backend/configuration.md`
- `docs/api/api-overview.md`
- `docs/api/backend-endpoints.md` (only endpoints actually in `api.py`)
- `docs/risk/risk-framework.md`
- `docs/risk/risk-gate.md`
- `docs/risk/position-sizing.md`
- `docs/risk/failsafes-and-kill-switches.md` (port key decisions from the existing `.docx`)
- `docs/ml/ml-overview.md`
- `docs/ml/regime-detection.md`
- `docs/ops/exchange-integrations.md`
- `docs/ops/binance-adapter.md`
- `docs/ops/telegram-alerts.md`
- `docs/ops/stripe-billing.md` (current billing exists)
- `docs/runbooks/local-development.md`
- `docs/runbooks/daily-ops.md`
- `docs/runbooks/release-checklist.md`
- `docs/testing/testing-strategy.md`
- `docs/testing/local-validation-checklist.md`
- `docs/decisions/README.md` + ADR template + 2–3 ADRs for already-made decisions (FastAPI, Redis/Celery, exchange-native feeds, LLM off hot path)
- `CODEOWNERS` (placeholder)

**Tier 2 — defer to post-validation unless you want them now:**

- `docs/backend/service-boundaries.md`
- `docs/backend/domain-model.md`
- `docs/backend/background-jobs.md`
- `docs/backend/error-handling.md`
- `docs/ml/feature-pipeline.md`
- `docs/ml/model-lifecycle.md`
- `docs/ml/sentiment-pipeline.md` (**note:** sentiment is in the README's ML background list but I need to verify it actually runs before documenting it as current)
- `docs/ml/offline-vs-online-inference.md`
- `docs/api/auth-and-access.md`
- `docs/architecture/repository-boundaries.md`
- `docs/frontend/*` (limited to billing HTML; the real React dashboard is a separate repo and deserves its own doc set over there)
- `docs/runbooks/exchange-outage-response.md`
- `docs/runbooks/webhook-debugging.md`
- `docs/testing/test-matrix.md`
- `docs/ops/bybit-adapter.md` (**planned integration**)
- `docs/ops/openai-integration.md` (**verify first** — no OpenAI client was found on quick inspection)
- `docs/product/implementation-backlog.md`

Rationale: shipping 50 half-filled docs is worse than shipping 30 real ones and a clear backlog of the rest. Any Tier-2 doc can be pulled forward on request.

---

## 8. Risks and avoided changes

- **`coinscope_trading_engine/` internals are not touched.** Resolving `core/` duplication, merging `scanner/`/`scanners/`, or flattening the top-level `.py` files all risk breaking imports mid-validation. Queued for May.
- **`fixed/` is archived, not deleted.** Until someone confirms every change in `fixed/` made it into the live engine (diff pass), we retain history.
- **Duplicate engine snapshots are archived, not deleted.** Same reasoning.
- **`billing_server.py` at root is left in place.** I don't know yet whether it's the live billing entry-point or a relic of `billing/`. Needs owner confirmation before any move.
- **`docker-compose.yml` stays at root** for this pass. Moving it risks breaking `docker compose up` muscle memory and CI paths without a corresponding update sweep.
- **No changes to CI.** `.github/workflows/ci.yml` references `requirements.txt` at root — safe to leave.

---

## 9. Open questions for the project lead

Before I execute Phase 2 I need your call on the items below. They directly affect file-move safety and how much documentation is "real" vs "planned":

1. **Move duplicate engine snapshots into `archive/`?** (`coinscope_trading_engine 2/`, `...3/`, `...4/`, `coinscope_trading_engine.tar.gz`, `coinscope_ai_project.zip`, `fixed/`). Safe and reversible, but touches git history.
2. **Move root-level `.md`/`.docx`/`.command`/`.pdf` clutter into `archive/` or `docs/`?** Non-destructive, high-impact.
3. **Is `billing_server.py` at root still used, or is `billing/` the live path?** Affects whether we document one billing entrypoint or two.
4. **Is the React dashboard at coinscope.ai in a separate repo?** If yes, I'll document the split clearly and keep `docs/frontend/` minimal here. If there's an adjacent repo I should audit, I need the path.
5. **Tier-1 vs Tier-2 doc scope** — should I ship the Tier-1 doc set described in Section 7 and leave Tier-2 as a tracked backlog, or push for all 50 in this pass (with the honesty cost that more will be labeled *planned*)?

---

## 10. What ships after approval

On approval of Sections 6–9, Phase 2–5 will produce, in order:

1. Root cleanup into `archive/` (moves only, no deletions).
2. Tier-1 docs listed in Section 7.
3. `CONTRIBUTING.md`, `CODEOWNERS`, rewritten `README.md`, organized `.env.example`.
4. ADR scaffolding with 2–3 retroactive ADRs.
5. Cross-linking pass and a final summary in `docs/RESTRUCTURE_SUMMARY.md`.

All work will be incremental, auditable, and reversible.

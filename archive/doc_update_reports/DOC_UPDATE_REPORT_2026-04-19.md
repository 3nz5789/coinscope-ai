# DOC_UPDATE_REPORT — 2026-04-19

**Run type:** Scheduled (`documentation-update`, autonomous mode)
**Author:** Scoopy (Claude)
**Scope:** CoinScopeAI-Context.md · README.md · docs/api/* · new-feature log for the week of Apr 12–19, 2026
**Branch:** `restructure/2026-04-18-tier1-docs` (working tree clean at report time)
**Mode notes:** The engine is mid 30-Day Testnet Validation (COI-41) under a no-engine-code-change freeze. This run is report-only in line with the convention established by the five prior runs in this folder; any canonical-doc edits should go through PR review against the `restructure/2026-04-18-tier1-docs` branch with CODEOWNERS sign-off.

---

## 1. Executive Summary

- The **Tier-1 restructure landed overnight** (commit `59416a2`, 2026-04-19 01:47 UTC+3). It supersedes most of the 2026-04-18 report's "stale" findings:
  - `CoinScopeAI-Context.md` was **retired** and moved to `archive/historical_reports/`. Its role is now covered by the new `docs/` tree plus the rewritten root `README.md`.
  - `README.md` was **rewritten** (432 → 199 lines). The new content reflects current code, the validation freeze, and the `ml/`, `research/`, `incidents/`, and `docs/` additions.
  - `docs/` now has twelve subdirectories (`architecture/`, `backend/`, `api/`, `ml/`, `risk/`, `ops/`, `runbooks/`, `testing/`, `onboarding/`, `decisions/`, `product/`, `frontend/`) plus `repo-audit.md`, `repository-map.md`, `project-history.md`, `RESTRUCTURE_SUMMARY.md`.
- **No new commits** have landed since the restructure landed; the only activity since 2026-04-15 is this single restructure commit plus the untracked files already existing on disk pre-commit (research/, tasks/, tests/, manus_upload/, crypto_futures_dev/).
- **One material doc drift remains after the restructure:** `docs/api/backend-endpoints.md` describes an **aspirational / non-shipping API surface** that does not match `coinscope_trading_engine/api.py`. Details in §4.
- `docs/api/api-overview.md` is conceptually accurate and cross-cutting; no changes recommended.
- The root `README.md`'s key-endpoints table **does** match code exactly (21/21), so external readers who stop at the README get a correct picture. The drift is inside the deeper reference doc.

Overall grade: **documentation is broadly current after the restructure — one sub-doc (`docs/api/backend-endpoints.md`) needs a targeted rewrite.**

---

## 2. CoinScopeAI-Context.md — Status

**File:** `archive/historical_reports/CoinScopeAI-Context.md` · **Size:** 412 lines · **Last touched on disk:** 2026-04-18 23:32

- **Status: retired.** The file is now in `archive/historical_reports/` per commit `59416a2`. That commit's `archive/README.md` index explicitly lists it as "legacy material… nothing here is load-bearing" (root `README.md`, §"What this repo is").
- The content overlap with the new `docs/` tree is high:
  - "Technology Stack" → now in `docs/backend/backend-overview.md` and root `README.md`.
  - "Repository Layout" → now in `docs/repository-map.md` and root `README.md`.
  - "Engine API" table → now in root `README.md` and `docs/api/backend-endpoints.md`.
  - "Risk Management" → now in `docs/risk/risk-framework.md`.
  - "Environment Variables" → now in `docs/backend/configuration.md`.
  - "Development Status" → now split across `docs/product/implementation-backlog.md` and root `README.md` ("Status of modules" table).
- **Recommendation:** no action. Leave it in archive. Do not revive or back-port; the new docs/ tree is the canonical replacement.
- **Cross-check:** all five prior doc-update reports from 2026-04-10 through 2026-04-18 are now preserved alongside it in `archive/doc_update_reports/`, so the context-doc lineage is fully traceable.

---

## 3. README.md — Status

**File:** `/README.md` · **Size:** 199 lines · **Last touched:** 2026-04-19 (commit `59416a2`)

### 3a. Accurate
- **One-line description, status block, and dashboard pointer** all current. Mentions the 2026-04-10 → 2026-04-30 validation freeze up front.
- **"What this repo is" section** covers all nine top-level directories that exist today: `coinscope_trading_engine/`, `billing/` + `billing_server.py`, `ml/`, `dashboard/`, `data/`, `tests/`, `scripts/`, `incidents/`, `docs/`, `archive/`. Verified against `ls` output on disk — no missing or invented directories.
- **Architecture ASCII diagram** is consistent with the scorer, risk gate, executor, journal, and regime-detector code paths.
- **Quick Start** commands are valid against `coinscope_trading_engine/.env.example` (tested existence, not execution).
- **Key endpoints table (port 8001)** lists 21 endpoints; this matches `coinscope_trading_engine/api.py` exactly (see §4 for the side-by-side).
- **Risk thresholds table** matches `docs/risk/risk-framework.md` and the constants visible in `risk_gate.py`.
- **Technology stack** matches `requirements.txt` (sampled numpy/pandas/hmmlearn/xgboost/ccxt/pydantic/celery).
- **"Status of modules" table** flags the v3 regime classifier as "inference integration partial", which is the accurate current state (the training pipeline is in `ml/regime_classifier_v3.py`; it's not yet wired into the hot path).
- **Documentation map** points at real files in the new `docs/` tree. Spot-checked `docs/runbooks/local-development.md`, `docs/onboarding/new-developer-guide.md`, `docs/risk/risk-framework.md`, `docs/ml/ml-overview.md` — all present.

### 3b. Minor observations (no action required during freeze)
- The README mentions "Bybit / OKX / Hyperliquid adapters — Planned" and "Kubernetes deployment — Planned". The `research/` folder now contains `okx_vs_bybit_oi.md`; that's research, not adapter work, so the "Planned" label is still accurate. No edit needed.
- The README does not mention `incidents/2026-04-18_*.md` directly, but `docs/runbooks/` does include `incident-binance-ws-disconnect-2026-04-18.md`, which covers the same content at the right layer. Acceptable.

**Recommendation:** no edits. README is current.

---

## 4. API endpoint documentation — **needs rewrite**

This is the one material gap that survived the Tier-1 restructure.

### 4a. `docs/api/api-overview.md` — accurate
Cross-cutting concerns (base URL, bearer-token + Stripe-signed auth, error envelope, versioning, CORS, timeouts, observability) are all described correctly and do not reference specific endpoints. No edits recommended.

### 4b. `docs/api/backend-endpoints.md` — **drifted**
The file claims "**21 endpoints total** as of 2026-04-18" at the bottom, but the 19 endpoints it actually describes do not match the 21 endpoints shipping in `coinscope_trading_engine/api.py`.

**Engine code (`coinscope_trading_engine/api.py`) — actual:**

| # | Method | Path | Tag |
| - | - | - | - |
| 1 | GET | `/health` | System |
| 2 | GET | `/config` | System |
| 3 | GET | `/signals` | Signals |
| 4 | **POST** | `/scan` | Signals |
| 5 | GET | `/positions` | Risk |
| 6 | GET | `/exposure` | Risk |
| 7 | GET | `/circuit-breaker` | Risk |
| 8 | POST | `/circuit-breaker/reset` | Risk |
| 9 | POST | `/circuit-breaker/trip` | Risk |
| 10 | GET | `/regime` | Intelligence |
| 11 | GET | `/sentiment` | Intelligence |
| 12 | GET | `/anomaly` | Intelligence |
| 13 | GET | `/position-size` | Risk |
| 14 | GET | `/correlation` | Risk |
| 15 | GET | `/journal` | Journal |
| 16 | GET | `/performance` | Journal |
| 17 | GET | `/performance/equity` | Journal |
| 18 | GET | `/performance/daily` | Journal |
| 19 | GET | `/scale` | Scale |
| 20 | POST | `/scale/check` | Scale |
| 21 | GET | `/validate` | Validation |

Plus the engine-side billing router (`coinscope_trading_engine/billing/stripe_gateway.py`, included via `app.include_router(billing_router)`):
- GET `/plans`
- GET `/subscription` (path confirmed from file inspection; see file)
- POST `/checkout` (see file)
- POST `/portal` (see file)
- POST `/webhook` (see file)

**Doc (`docs/api/backend-endpoints.md`) — described:**

The doc describes endpoints that **do not exist in code today** — these appear to be designed-but-unshipped or earlier-draft spec:
- `GET /ready`
- `GET /scan` (code uses **POST**)
- `GET /regime/{symbol}` (code uses `GET /regime` with no path param)
- `GET /risk-gate` (no such endpoint; `/exposure` + `/circuit-breaker` cover this surface)
- `GET /orders`
- `POST /kill-switch` (code uses `/circuit-breaker/trip` and `/circuit-breaker/reset`)
- `GET /symbols`
- `GET /depth/{symbol}`
- `GET /billing/me`
- `POST /billing/portal` (engine-side path is under the router prefix — path differs)
- `GET /metrics` (served by `metrics_exporter.py`, not by FastAPI)

And the doc **omits these shipping endpoints**:
- `GET /config`
- `GET /signals`
- `GET /exposure`
- `GET /circuit-breaker`
- `POST /circuit-breaker/trip`
- `GET /sentiment`
- `GET /anomaly`
- `GET /correlation`
- `GET /performance/equity`
- `GET /scale`
- `POST /scale/check`
- `GET /validate`

### 4c. Recommended rewrite
Replace `docs/api/backend-endpoints.md` with a direct dump of the FastAPI surface grouped by tag (System · Signals · Risk · Intelligence · Journal · Scale · Validation · Billing), preserving the existing conventions section (bearer auth, open / Stripe-signed annotations, error envelope). Retain `GET /ready`, `/kill-switch`, `/orders`, `/symbols`, `/depth/{symbol}`, `/metrics` only if a companion marker clarifies they are **planned / post-validation** endpoints — otherwise strip them to avoid reader confusion.

Sample tag-grouped outline (for the PR author):
- **System:** `/health`, `/config`
- **Signals:** `/signals`, `/scan`
- **Risk:** `/positions`, `/exposure`, `/circuit-breaker`, `/circuit-breaker/reset`, `/circuit-breaker/trip`, `/position-size`, `/correlation`
- **Intelligence:** `/regime`, `/sentiment`, `/anomaly`
- **Journal:** `/journal`, `/performance`, `/performance/equity`, `/performance/daily`
- **Scale:** `/scale`, `/scale/check`
- **Validation:** `/validate`
- **Billing (mounted router):** `/plans`, `/subscription`, `/checkout`, `/portal`, `/webhook`

This should be a pure-docs PR; it does not touch engine code and therefore is freeze-compatible.

### 4d. Billing service (port 8002) — unchanged since last week
Findings from the 2026-04-18 report still hold:
- `billing/webhook_handler.py` serves `/billing/health`, `/billing/subscriptions`, `/billing/customer/{customer_id}` (undocumented), `/billing/webhook`.
- `billing/customer_portal.py` serves `/billing/portal/config`, `/billing/portal/session`.
- `billing/stripe_checkout.py` serves `/billing/health` (dup), `/billing/plans`, `/billing/checkout/session`, `/billing/webhook` (dup).
- None of these are mentioned in `docs/api/backend-endpoints.md`. Coverage is in `docs/ops/stripe-billing.md` and `docs/ops/stripe-billing-runbook.md`; the cross-link is OK but the endpoint reference itself is missing.

Fold this into the same PR as §4c.

---

## 5. New features / activity — week of Apr 12–19, 2026

### 5a. Commits
Git log is sparse this week — only one commit:

| SHA | Date | Subject |
| --- | --- | --- |
| `59416a2` | 2026-04-19 | `docs: Tier-1 restructure + repo hygiene pass (2026-04-18)` |

Prior commit for reference: `7260c91` (2026-04-10) `[BUILD] execution/order_manager.py — retry-aware order lifecycle`.

This is expected — the engine is in a code freeze. The single commit is pure docs + repo hygiene + redaction of leaked Stripe test keys.

### 5b. What shipped in `59416a2`
Already covered by `docs/RESTRUCTURE_SUMMARY.md` — no additional doc update needed. Worth highlighting for stakeholders:
- Full `docs/` tree (12 subdirs + 4 top-level index/audit files).
- Root files refreshed: `README.md`, `CONTRIBUTING.md`, `CODEOWNERS`, `.env.example`.
- Stripe test keys redacted across five files (archive guide, `docs/project-history.md`, `billing/README.md`, `docs/ops/stripe-billing-runbook.md`, `scripts/setup_stripe_test_products.py`). **Security-sensitive — ensure downstream consumers rotate any cached copies.**
- First-time commit of `billing/`, `dashboard/`, `ml/`, and engine subdirs (these were previously untracked on disk).
- Legacy material consolidated under `archive/` with `archive/README.md` as index.

### 5c. On-disk changes (untracked relative to git, pre-restructure)
The 2026-04-18 report already flagged these; they are now either archived, included in the restructure, or still untracked and awaiting a future PR:
- `ml/regime_classifier_v3.py`, `ml/regime_label_dataset_v1.py` — **included in restructure commit.**
- `scripts/watchdog_journal_duplicates.py`, `scripts/reconcile_binance_vs_journal.py` — **included in restructure commit.**
- `research/funding-data-vendor-comparison.md`, `research/okx_vs_bybit_oi.md`, `research/regime_features_research.md`, `research/regime_features_matrix.xlsx` — **present on disk; not part of the restructure commit**; these look like research artifacts that can stay local or move to a long-form doc later.
- `incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md`, `incidents/2026-04-18_dashboard_redis_drift.md` — **present on disk; not part of the restructure commit**. Mirrored in `docs/runbooks/incident-binance-ws-disconnect-2026-04-18.md` which IS in the commit, so the canonical operator-facing write-up is tracked.
- `docs/ml/confidence_scoring_baseline.md` — **included in restructure commit.**
- `manus_upload/*_SKILL.md` (7 files), `crypto_futures_dev/SKILL.md`, `tasks/QA-BILLING-Stripe-Connector-Smoke-Test.md` — present on disk; these are external collaborator uploads / tasking notes, not canonical engine docs. No action recommended.

### 5d. Features that need new documentation
Nothing net-new this week that is not already documented. The v3 regime classifier, reconciliation script, duplicate-order watchdog, and WS replay consistency test harness were all pre-existing on disk and are now **documented** via the new `docs/` tree:
- v3 classifier: `docs/ml/regime-detection.md` + root `README.md` "Status of modules".
- Reconciliation & watchdog scripts: listed in root `README.md` "What this repo is" (`scripts/`); operator notes live in `docs/runbooks/daily-ops.md`.
- WS replay consistency test harness: `docs/testing/local-validation-checklist.md`.
- Incidents: `docs/runbooks/incident-binance-ws-disconnect-2026-04-18.md`.

---

## 6. Recommended next actions

| # | Action | Owner | Blocker | Effort |
| - | - | - | - | - |
| 1 | Open a pure-docs PR rewriting `docs/api/backend-endpoints.md` to match actual `coinscope_trading_engine/api.py` surface (see §4c outline). Include billing router and port-8002 billing-service endpoints. | Docs owner | None — freeze-compatible | ~1 hour |
| 2 | Decide whether `/ready`, `/orders`, `/kill-switch`, `/symbols`, `/depth/{symbol}`, `/metrics` stay in the doc as "planned / post-validation" or are removed. Record decision in `docs/decisions/` as ADR-0004 if you keep them. | Engine lead | None | ~30 min |
| 3 | Audit and remove or commit the remaining untracked files on disk (`research/`, `incidents/`, `tests/`, `tasks/`, `manus_upload/`) so the working tree is truly clean. | Repo maintainer | None | ~30 min |
| 4 | After validation window closes (2026-04-30), re-run this same scheduled report and re-open any drift items deferred during the freeze. | Automation | Validation window end | Automatic |

---

## 7. What this run changed

- **Wrote** this report to `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-04-19.md` (matches the convention established by the five prior scheduled runs).
- **Wrote** an identical copy to the session outputs folder for immediate visibility.
- **No other files were modified.** No canonical docs, no engine code, no `.env*`, no billing material.
- **No git operations** (add / commit / push) were performed.

---

*End of report.*

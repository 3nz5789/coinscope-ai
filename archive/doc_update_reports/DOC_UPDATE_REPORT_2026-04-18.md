# DOC_UPDATE_REPORT — 2026-04-18

**Run type:** Scheduled (`documentation-update`, autonomous mode)
**Author:** Scoopy (Claude)
**Scope:** CoinScopeAI-Context.md · README.md · API reference · new-feature log for the week of Apr 11–18, 2026
**Mode notes:** The engine is mid 30-Day Testnet Validation (COI-41) under a **no-engine-code-change freeze**. This report therefore records findings and recommended edits; it does not push changes into the live doc set unless the scheduled task explicitly asked for a write. The only file written by this run is this report.

---

## 1. Executive Summary

- `CoinScopeAI-Context.md` (2026-04-15) and `README.md` (2026-04-15) are **still broadly accurate** for the engine and billing surface area.
- Since 2026-04-11, the project has added **three top-level directories** (`ml/`, `research/`, `incidents/`, plus substantial expansion of `scripts/` and `docs/`) that are **not reflected** in either the Context doc's Repository Layout or the README.
- The **v3 ML regime classifier** (Random Forest + XGBoost ensemble) shipped this week and is not mentioned in either doc — the Development Status table still only lists the 4-state HMM.
- Two **incident reports** (Binance WS disconnect storm, Execution duplicate-orders tabletop) and one **dashboard-drift investigation** were filed this week; the docs don't reference the new `incidents/` workflow.
- The **engine API (port 8001)** is **fully in sync** with `coinscope_trading_engine/api.py` (21 endpoints) and the engine-side billing router `coinscope_trading_engine/billing/stripe_gateway.py` (5 endpoints).
- The **standalone billing service (port 8002)** has one **undocumented endpoint** (`GET /billing/customer/{customer_id}`) and the Context doc's description of which file implements which endpoint is out of date.

Overall grade: **documentation is current on the "what works" axis, stale on the "what shipped this week" axis.**

---

## 2. CoinScopeAI-Context.md — Findings

**File:** `/CoinScopeAI-Context.md` · **Last updated:** 2026-04-15 · **Size:** 412 lines

### 2a. Still accurate
- Engine version (2.0.0), technology stack, signal pipeline diagram, scanner list, risk management section, entitlements matrix, environment variables, observability stack — all consistent with code on disk as of 2026-04-18.
- Engine API table (`/health`, `/config`, `/scan`, `/signals`, `/positions`, `/exposure`, `/circuit-breaker*`, `/position-size`, `/correlation`, `/regime`, `/sentiment`, `/anomaly`, `/journal`, `/performance*`, `/scale*`, `/validate`) matches `coinscope_trading_engine/api.py` exactly (21/21 endpoints).
- Engine-side billing router (`/billing/plans`, `/billing/subscription`, `/billing/checkout`, `/billing/portal`, `/billing/webhook`) matches `coinscope_trading_engine/billing/stripe_gateway.py` exactly (5/5 endpoints).

### 2b. Stale — Repository Layout section
The "Repository Layout" tree (lines ~27–92) does **not** include directories that exist and were active this week:
- `ml/` — v3 regime classifier source + labeled dataset builder (added 2026-04-17)
- `research/` — regime features, funding data vendor, OKX vs Bybit OI comparison (added 2026-04-17)
- `incidents/` — structured incident reports (added 2026-04-17/18)
- `scripts/` — now contains `watchdog_journal_duplicates.py` and `reconcile_binance_vs_journal.py` on top of the pre-existing `setup_stripe_test_products.py`
- `docs/ml/confidence_scoring_baseline.md` — added 2026-04-17

### 2c. Stale — Development Status table
Lines ~388–407 omit features that exist in code today:
| Missing entry | Reality |
|---|---|
| ML v3 Regime Classifier (RF + XGBoost) | Implemented in `ml/regime_classifier_v3.py`; training dataset in `ml/regime_label_dataset_v1.py`; 4-class taxonomy (Trending / Mean-Reverting / Volatile / Quiet) distinct from the HMM's Bull/Bear/Chop/Volatile |
| Execution-path reconciliation + duplicate-order watchdog | Implemented in `scripts/reconcile_binance_vs_journal.py` and `scripts/watchdog_journal_duplicates.py` (Phase-1, freeze-compatible) |
| WS replay consistency test harness | `coinscope_trading_engine/tests/test_ws_replay_consistency.py` — 45/45 passing |
| Partial-fill handling tests | `coinscope_trading_engine/tests/test_partial_fill_handling.py` |
| Daily-loss halt simulation tests | `coinscope_trading_engine/tests/test_daily_loss_halt_sim.py` |

### 2d. Stale — Billing port 8002 table
The Context doc (lines ~194–204) implies all port-8002 endpoints are in `billing/webhook_handler.py`. In fact:
- `billing/webhook_handler.py` serves: `/billing/health`, `/billing/subscriptions`, `/billing/customer/{customer_id}` ← **undocumented**, `/billing/webhook`
- `billing/customer_portal.py` (router): `/billing/portal/config`, `/billing/portal/session`
- `billing/stripe_checkout.py`: `/billing/health` (duplicate — only one is wired into the final app), `/billing/plans`, `/billing/checkout/session`, `/billing/webhook` (duplicate)

Recommendation: add `GET /billing/customer/{customer_id}` to the table, and add a footnote that the standalone service composes routers from `webhook_handler.py` + `customer_portal.py` (with `stripe_checkout.py` retained as a reference/standalone variant).

### 2e. Missing — Validation-phase context
The doc does not mention the **30-Day Testnet Validation (COI-41)** window or the **engine-code freeze** that currently governs all work. This is referenced in every incident file this week and should be a top-level block in the Context doc. Suggested wording:

> **Validation phase (as of 2026-04-10):** The engine is in a 30-day testnet-only validation window (COI-41). During this window, engine source is frozen — only config, ops, monitoring, and out-of-process tooling (watchdogs, reconciliation scripts, dashboards, ML training off the hot path) may be changed without a SEV1 waiver.

### 2f. Stale — Open Issues & Tech Debt
Lines ~320–351 list 9 items from 2026-04-05 code review. During the freeze these cannot be fixed; they should be annotated as **"deferred until validation window closes"** so readers don't assume inaction is oversight. Items 1–2 (`signal_generator.py` and `pattern_scanner.py`) may also already be partially addressed — worth a post-freeze re-audit.

---

## 3. README.md — Findings

**File:** `/README.md` · **Last updated:** 2026-04-15 · **Size:** 432 lines

### 3a. Still accurate
- Quick Start (local + Docker), Signal Pipeline, Risk Management, Architecture, Environment Variables, Performance Targets, Recommended Launch Sequence — all consistent with repo state.
- Engine API table matches `api.py` (21 endpoints).
- Billing section (Stripe pricing tiers, test cards, setup flow) matches current billing code.

### 3b. Stale — API Reference table (port 8002 subsection)
Lines ~160–163 list 4 port-8002 endpoints:
- `/billing/health` ✓
- `/billing/subscriptions` ✓
- `/billing/portal/session` ✓
- `/billing/portal/config` ✓

Missing:
- `GET /billing/customer/{customer_id}` — live in `billing/webhook_handler.py`
- `POST /billing/webhook` (port 8002) — live in `webhook_handler.py`; docs only mention the engine-side (`:8001`) webhook
- `GET /billing/plans` (port 8002, via `stripe_checkout.py`) — listed only under port 8001

### 3c. Stale — Roadmap
Lines ~416–428 have no entry for this week's ML work. Suggested additions:
- `[x] ML v3 regime classifier (Random Forest + XGBoost ensemble) — 4-class taxonomy`
- `[x] Execution reconciliation + duplicate-order watchdog (Phase-1 freeze-compatible)`
- `[x] WS replay consistency test harness (45/45 passing)`

### 3d. Missing — Ops & Incidents pointer
The README doesn't point operators at the new `incidents/` and `docs/` directories. Suggest adding a short "Operations & Incidents" section that links:
- `docs/OPS_Daily_Market_Scan_Runbook.md`
- `docs/BILLING_Stripe_Setup_Runbook.md`
- `docs/INCIDENT_Binance_WS_Disconnect_Storm_2026-04-18.md`
- `incidents/2026-04-18_*.md` (x2)
- `docs/QA_WS_REPLAY_CONSISTENCY_2026-04-16.md`
- `docs/QA_RISK_DailyLossHalt_2026-04-16.md`
- `docs/QA_BILLING_COI39_2026-04-15.md`

---

## 4. API Endpoint Audit

### 4a. Engine (port 8001) — `coinscope_trading_engine/api.py`
Enumerated 21 decorated routes. All 21 are documented in both `CoinScopeAI-Context.md` and `README.md`. **No drift.**

### 4b. Engine billing router — `coinscope_trading_engine/billing/stripe_gateway.py`
Enumerated 5 routes, all mounted under `/billing`. All 5 are documented in both docs. **No drift.**

### 4c. Standalone billing service (port 8002)
Assembled from three modules (`webhook_handler.py` + `customer_portal.py` router + optional `stripe_checkout.py`):

| Endpoint | Source file | In Context.md? | In README.md? |
|---|---|:-:|:-:|
| `GET /billing/health` | webhook_handler.py | ✅ | ✅ |
| `GET /billing/plans` | stripe_checkout.py | ✅ | — (only listed under :8001) |
| `GET /billing/subscriptions` | webhook_handler.py | ✅ | ✅ |
| `GET /billing/customer/{customer_id}` | webhook_handler.py | ❌ | ❌ |
| `POST /billing/checkout/session` | stripe_checkout.py | ✅ | — |
| `POST /billing/portal/session` | customer_portal.py | ✅ | ✅ |
| `GET /billing/portal/config` | customer_portal.py | ✅ | ✅ |
| `POST /billing/webhook` | webhook_handler.py + stripe_checkout.py | ✅ | — (only listed under :8001) |

**Action items:**
1. Add `GET /billing/customer/{customer_id}` to both docs (or decide whether to hide it — it's a lookup-by-id endpoint with no auth gate visible in the file).
2. Clarify in the README that port 8002 also exposes `/billing/webhook` and `/billing/plans` (identical shape to :8001, different process).
3. In Context.md, fix the implication that all port-8002 endpoints live in `webhook_handler.py` — they're split across three modules.

---

## 5. New Features Added This Week (2026-04-11 → 2026-04-18)

Compiled from file mtimes and content review. Git log is shallow (2 commits), so mtimes are the authoritative source.

### 5a. ML v3 Regime Classifier (Apr 17)
- `ml/regime_classifier_v3.py` — Random Forest + XGBoost soft-voting ensemble. Loads `ml/data/regime_labeled_v1.csv`, group-aware train/test split by `session_id` (prevents temporal leakage), saves model + metadata to `ml/models/`.
- `ml/regime_label_dataset_v1.py` — Builds the labeled training set using regime-matched synthetic OHLCV: GBM with drift (Trending), Ornstein–Uhlenbeck (Mean-Reverting), elevated-σ + jump diffusion (Volatile), low-σ low-volume GBM (Quiet). Calibrated from BTCUSDT/ETHUSDT statistics.
- Taxonomy change: v3 uses **Trending / Mean-Reverting / Volatile / Quiet** rather than the HMM's **Bull / Bear / Chop / Volatile**. This is a material change and should be called out in the Intelligence section of both docs.
- Supporting research: `research/regime_features_research.md`, `research/regime_features_matrix.xlsx`, `docs/ml/confidence_scoring_baseline.md`.

### 5b. Freeze-compatible execution safeguards (Apr 17)
- `scripts/watchdog_journal_duplicates.py` — polls `/journal` and flags entries sharing (symbol, side, qty) inside a configurable window. Lives outside the engine (does not touch the freeze).
- `scripts/reconcile_binance_vs_journal.py` — compares Binance fills vs the local journal to detect drift.
- Both spawned from the duplicate-order tabletop exercise (`incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md`).

### 5c. Incident response & QA (Apr 15–18)
- `incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md` — SEV-1 tabletop exercise on retry-induced duplicate orders.
- `incidents/2026-04-18_dashboard_redis_drift.md` — active SEV3 (provisional) investigation into stale dashboard values.
- `docs/INCIDENT_Binance_WS_Disconnect_Storm_2026-04-18.md` — SEV2 draft for correlated WebSocket disconnect bursts under the single-asyncio-loop + 5-conns-per-5-min rate limit.
- `docs/QA_WS_REPLAY_CONSISTENCY_2026-04-16.md` — 45/45 passing across 8 categories (DataNormalizer determinism, REST↔WS parity, envelope unwrapping, closed-candle gating, float precision, multi-candle ordering, etc.).
- `docs/QA_RISK_DailyLossHalt_2026-04-16.md` — daily-loss halt simulation report.
- `docs/QA_BILLING_COI39_2026-04-15.md` — billing QA, 80/80 tests pass.

### 5d. Research (Apr 17)
- `research/okx_vs_bybit_oi.md` — multi-exchange open-interest comparison (feeds the "Multi-exchange" roadmap item).
- `research/funding-data-vendor-comparison.md` — funding-rate data vendor evaluation.

### 5e. Tests added (Apr 14–16)
- `coinscope_trading_engine/tests/test_ws_replay_consistency.py`
- `coinscope_trading_engine/tests/test_partial_fill_handling.py`
- `coinscope_trading_engine/tests/test_daily_loss_halt_sim.py`
- `tests/test_billing_webhook.py`, `tests/test_billing_portal.py`, `tests/test_billing_schema.py`

---

## 6. Recommended Edits (for after the freeze, or as doc-only updates during the freeze)

Documentation-only edits are not engine code changes and should be safe during the COI-41 freeze. Priority order:

1. **CoinScopeAI-Context.md** — bump "Last updated" to 2026-04-18; insert the validation-phase block from §2e; add `ml/`, `research/`, `incidents/`, expanded `scripts/` to Repository Layout; add v3 regime classifier + watchdog + reconciliation rows to Development Status; fix the port-8002 billing source-of-truth footnote (§2d); add `GET /billing/customer/{customer_id}` to the port-8002 table.
2. **README.md** — bump "Last updated"; add the three port-8002 rows (§3b) to the API Reference table; add the new Roadmap entries (§3c); add an "Operations & Incidents" pointer section (§3d).
3. **docs/** — no changes needed to runbooks / incident files themselves; they're all fresh.
4. **API docs** — Swagger is auto-generated from code; no drift there. The only drift is in the narrative docs above.

No changes were made to engine code, billing code, or any production file during this run.

---

## 7. Files Written by This Run

- `/Users/mac/Documents/Claude/Projects/CoinScopeAI/DOC_UPDATE_REPORT_2026-04-18.md` (this report)

No other writes. All other findings are recommendations for human review before edits are applied — consistent with the scheduled-task rule "when in doubt, producing a report of what you found is the correct output."

---

*Report generated by Scoopy under scheduled-task `documentation-update` on 2026-04-18.*

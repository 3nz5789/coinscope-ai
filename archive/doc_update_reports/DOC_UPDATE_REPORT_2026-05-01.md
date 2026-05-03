# DOC_UPDATE_REPORT — 2026-05-01

**Run type:** Scheduled (`documentation-update`, autonomous mode)
**Author:** Scoopy (Claude)
**Scope:** `CoinScopeAI-Context.md` · `README.md` · `docs/api/*` · new-feature log since the 2026-04-21 run
**Branch:** `restructure/2026-04-18-tier1-docs` (HEAD `59416a2`, unchanged since 2026-04-19)
**Mode notes:** This report is report-only and does not modify canonical docs. Any rewrites recommended below should go through a pure-docs PR against `restructure/2026-04-18-tier1-docs` with CODEOWNERS sign-off. The 2026-04-10 → 2026-04-30 testnet-validation window **closed yesterday** — for the first time since the report cadence began this run is no longer freeze-justified, and the README's freeze banner has now drifted into staleness (§3).

---

## 1. Executive Summary

- **Engine code is still frozen.** `git log -1` returns `59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)`. No commits since 2026-04-19. `git status` shows the same accumulating untracked-artifact pile as prior runs, plus three new artifacts noted below. **Thirteen consecutive days with zero source changes** in the engine modules under daily review.
- **The validation freeze window ended 2026-04-30.** Today is the first scheduled run after the window closed. The README still reads `Status: Validation phase (2026-04-10 to 2026-04-30). No core-engine changes until validation closes.` That status line is now stale by one day and is the **first material README edit recommended by this report cadence** (§3).
- **Two net-new canonical-grade artifacts have appeared in the working tree** since the 2026-04-21 run:
  - `architecture/architecture.md` (296 lines, mtime 2026-04-29) — v4 canonical six-tier architecture diagram with vendor-adapter, sanity-gate, and real-capital-gate annotations.
  - `mvp-readiness-checklist.md` (193 lines, mtime 2026-04-29) — the "real capital" readiness gate (post-validation, post-Phase-2).

  Both files are **untracked**, and neither is linked from `README.md` or `docs/README.md`. They duplicate (and in some places contradict) `docs/architecture/system-overview.md` and the README's module-status table. This is the most consequential documentation event of the week and is covered in detail in §5.

- **Previously-flagged drift items are still outstanding:**
  - `docs/api/backend-endpoints.md` rewrite — outstanding **12 days** (since 2026-04-19). Now overdue.
  - `0–12 confluence` cross-link to `docs/ml/confidence_scoring_baseline.md` — outstanding 10 days (since 2026-04-21).
  - Untracked code-review and doc-update artifacts (`CODE_REVIEW_*.md` × 8 → 9 today; `DOC_UPDATE_REPORT_*.md` × 2 → 3 today) still not committed or triaged.
- **`CoinScopeAI-Context.md`** — still retired in `archive/historical_reports/`. No action.

Overall grade: **documentation has materially drifted this week** for the first time since the cadence began. The cause is not engine churn (there is none) but two new top-of-tree planning artifacts that are now the canonical view of architecture and MVP readiness yet are invisible from the docs map.

---

## 2. CoinScopeAI-Context.md — Status

**File:** `archive/historical_reports/CoinScopeAI-Context.md` · 412 lines · last on-disk touch 2026-04-18 23:32 (unchanged).

- Status: still retired. Resides in `archive/historical_reports/`, indexed by `archive/README.md`, not linked from the root `README.md` or any doc in the live `docs/` tree. Its former content remains covered by the post-restructure `docs/` tree plus the rewritten root README (mapping reproduced in the 2026-04-19 report, §2).
- Recommendation: **no action.** Leave in archive. Do not revive.

---

## 3. README.md — Stale freeze banner (NEW)

**File:** `/README.md` · 199 lines · last touch 2026-04-19 (commit `59416a2`).

Re-verified against the tree on 2026-05-01. The body of the README — directory list, key-endpoints table, risk thresholds, tech stack, module-status table, documentation map — is still accurate against the engine code, which has not changed.

The single material edit is the status banner at the top of the file:

```
**Status:** Validation phase (2026-04-10 to 2026-04-30). No core-engine changes until validation closes.
```

This sentence is now stale. Validation closed yesterday. There are three options for the maintainer; this report does not pick one:

1. **Validation passed and post-validation is in motion.** Replace with `**Status:** Post-validation hardening — engine frozen on `59416a2` while the P0/P1 backlog from the daily code reviews (`CODE_REVIEW_2026-04-19.md` → `CODE_REVIEW_2026-05-01.md`) is triaged.`
2. **Validation extended.** Replace with `**Status:** Validation phase extended to <new date>. No core-engine changes until validation closes.` Note the new end date.
3. **Validation outcome pending review.** Replace with `**Status:** Validation phase concluded 2026-04-30; outcome under review. Engine remains frozen on `59416a2` pending sign-off.`

Independent of which option is chosen, the README should also gain one short paragraph either above or below the status banner pointing to the two new top-level artifacts (§5):

> See `architecture/architecture.md` for the v4 canonical architecture and `mvp-readiness-checklist.md` for the real-capital gate. These are paired — the diagram is the map, the checklist is the gate.

Estimated effort: 5 minutes for the status edit, 5 minutes for the cross-link paragraph. Pure docs, can land independently of any engine work.

**Other README sections re-verified clean:**

- "What this repo is" directory list still matches `ls` output for the canonical top-level directories. The two new top-level artifacts (`architecture/`, `mvp-readiness-checklist.md`) are **not** in this list and should be added if the maintainer chooses option 1 above. If the maintainer treats them as transient working-set artifacts, leave the list as-is.
- Key-endpoints table (21 endpoints, port 8001) still matches `coinscope_trading_engine/api.py`.
- Risk thresholds, tech stack, module-status table, documentation map: all still accurate.

---

## 4. API endpoint documentation — **still drifted (12 days outstanding)**

### 4a. `docs/api/api-overview.md` — accurate

No changes since last run. Base URL, auth scheme, error envelope, versioning, CORS, timeouts, observability — all still correct. No edits recommended.

### 4b. `docs/api/backend-endpoints.md` — drifted, unchanged from 2026-04-21

Re-verified on 2026-05-01 by comparing `grep -nE "^@app\.(get|post)" coinscope_trading_engine/api.py` against the doc. The drift is identical to the 2026-04-19 and 2026-04-21 reports.

**Shipping engine surface (21 endpoints in `coinscope_trading_engine/api.py`, tag-grouped):**

| Tag | Endpoints |
| --- | --- |
| System | `GET /health`, `GET /config` |
| Signals | `GET /signals`, `POST /scan` |
| Risk | `GET /positions`, `GET /exposure`, `GET /circuit-breaker`, `POST /circuit-breaker/reset`, `POST /circuit-breaker/trip`, `GET /position-size`, `GET /correlation` |
| Intelligence | `GET /regime`, `GET /sentiment`, `GET /anomaly` |
| Journal | `GET /journal`, `GET /performance`, `GET /performance/equity`, `GET /performance/daily` |
| Scale | `GET /scale`, `POST /scale/check` |
| Validation | `GET /validate` |

**Plus the mounted billing router** (`APIRouter(prefix="/billing", tags=["Billing"])` in `coinscope_trading_engine/billing/stripe_gateway.py:135`, mounted via `app.include_router(billing_router)` at `api.py:218`):

| Method | Path |
| --- | --- |
| GET | `/billing/plans` |
| GET | `/billing/subscription` |
| POST | `/billing/checkout` |
| POST | `/billing/portal` |
| POST | `/billing/webhook` |

**Endpoints described in the doc that do not exist in code today:** `GET /ready`, `GET /scan` (code uses POST), `GET /regime/{symbol}` (code uses GET /regime with no path param), `GET /risk-gate` (split across `/exposure` + `/circuit-breaker`), `GET /orders`, `POST /kill-switch` (split across `/circuit-breaker/{trip,reset}`), `GET /symbols`, `GET /depth/{symbol}`, `GET /billing/me`. `GET /metrics` is served by `metrics_exporter.py`, not FastAPI.

**Endpoints shipping but not documented:** `GET /config`, `GET /signals`, `GET /exposure`, `GET /circuit-breaker`, `POST /circuit-breaker/trip`, `GET /sentiment`, `GET /anomaly`, `GET /correlation`, `GET /performance/equity`, `GET /scale`, `POST /scale/check`, `GET /validate`.

The doc footer still claims "**21 endpoints total** as of 2026-04-18", which numerically agrees with the engine count but is a false-agreement artifact: five of the doc's 19 enumerated items don't exist in code, and 12 shipping endpoints are missing.

### 4c. New cross-reference relevant this run

The new `architecture/architecture.md` v4 diagram (§5) labels Tier 05 as "Engine API · api.coinscope.ai · FastAPI · **98 paths**". This number does not match either the doc (19 enumerated paths) or the engine (21 paths plus 5 billing-router paths = 26). The "98 paths" figure may be a forward-looking total (engine + billing + auth + admin); the diagram does not source the count. Whoever owns the API-reference rewrite should reconcile this before the rewrite lands so readers don't see "21" in one place, "26" in another, and "98" in a third.

### 4d. Recommended rewrite (unchanged from 2026-04-19 §4c)

Replace `docs/api/backend-endpoints.md` with a direct tag-grouped enumeration of the FastAPI surface, preserving the existing conventions prelude (bearer auth, open / Stripe-signed annotations, error envelope). Include the mounted billing router. Either strip the planned-but-unshipped endpoints (`/ready`, `/orders`, `/kill-switch`, `/symbols`, `/depth/{symbol}`, `/metrics`) or keep them under a clearly-labeled **planned / post-validation** subheading with a cross-link to a new ADR-0004 that records the decision.

Outline for the PR author, identical to the 2026-04-19 recommendation:

- **System:** `/health`, `/config`
- **Signals:** `/signals`, `/scan`
- **Risk:** `/positions`, `/exposure`, `/circuit-breaker`, `/circuit-breaker/reset`, `/circuit-breaker/trip`, `/position-size`, `/correlation`
- **Intelligence:** `/regime`, `/sentiment`, `/anomaly`
- **Journal:** `/journal`, `/performance`, `/performance/equity`, `/performance/daily`
- **Scale:** `/scale`, `/scale/check`
- **Validation:** `/validate`
- **Billing (mounted router):** `/plans`, `/subscription`, `/checkout`, `/portal`, `/webhook`

Effort estimate: still ~1 hour. Still freeze-compatible (pure docs, no engine change).

### 4e. Billing service (port 8002) — unchanged

Coverage gap for `billing/webhook_handler.py`, `billing/customer_portal.py`, and `billing/stripe_checkout.py` endpoints is unchanged. Fold into the same PR as §4d.

---

## 5. New features / activity — week of Apr 24 → May 1, 2026

### 5a. Commits

Zero commits since the prior scheduled run. Full git log since the last report:

| SHA | Date | Subject |
| --- | --- | --- |
| _(none)_ | — | — |

`HEAD` is still `59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)`.

### 5b. NEW: top-of-tree canonical-grade artifacts (untracked)

Two files appeared at the top of the tree on 2026-04-29 (mtime 2026-04-29 12:28 / 12:20). Both are net-new since the 2026-04-21 run. Neither is committed.

#### `architecture/architecture.md` — 296 lines, mtime 2026-04-29 12:28

**What it is:** A self-described "v4 canonical (readiness-aware)" six-tier architecture diagram (Mermaid `flowchart TB`) plus prose annotations for vendor adapters, sanity gate, per-provider health, backtest pipeline, and a real-capital gate. Six tiers:

1. T01 — External: CCXT (Binance · Bybit · OKX · Hyperliquid), CoinGlass v4, Tradefeeds, CoinGecko, Claude API
2. T02 — Ingestion + vendor abstraction + EventBus (recording daemon, "133 events/sec")
3. T03 — Stores (Redis, Postgres journal) + ML engine (Sentiment Analyzer, Signal Classifier v3 with **162 features**, Regime Detector — 4 labels, Risk Predictor — P3)
4. T04 — Trading Engine Core (Signal Generator, Risk Gate, Risk Manager, Position Sizer, Order Manager — Binance Testnet, "🔒 REAL-CAPITAL GATE LOCKED")
5. T05 — Engine API ("api.coinscope.ai · FastAPI · **98 paths**")
6. T06 — UI (Web Dashboard at `app.coinscope.ai` with 16 pages, Telegram bot, marketing site at `coinscope.ai`)

Plus an Ops rail (Sentry, Grafana, runbooks) and an Operator Sync rail.

**Conflicts and gaps vs. existing canonical docs:**

| Field in new artifact | Same field in existing canonical doc | Drift |
| --- | --- | --- |
| Multi-exchange ingestion (Binance, Bybit, OKX, Hyperliquid) | `README.md` Status table: "Bybit / OKX / Hyperliquid adapters — Planned" | `architecture/architecture.md` shows them as P1, in scope. README says planned. |
| **162 features** in Signal Classifier v3 | `docs/ml/ml-overview.md` and `docs/ml/confidence_scoring_baseline.md` describe the v3 ensemble but do not state a feature count of 162. | New numeric claim, unsourced. |
| FastAPI **98 paths** | `coinscope_trading_engine/api.py` has 21 paths, plus 5 billing-router paths, total 26. `docs/api/backend-endpoints.md` enumerates 19. | The "98" appears nowhere else in the repo. |
| Web dashboard at `app.coinscope.ai` with **16 pages** | `README.md`: "The React dashboard at <https://coinscope.ai/> is a separate repo and is not in this tree." | New domain (`app.` subdomain) and new page count, both unsourced. |
| EventBus + Recording Daemon, "133 events/sec" | No file under `coinscope_trading_engine/` references an EventBus or a recording-daemon abstraction. `grep -rni "EventBus" coinscope_trading_engine` returns nothing. | New architectural component, possibly aspirational. |
| Six-tier numbering and "Phase 1 MVP" labels | `docs/architecture/system-overview.md` uses a different decomposition (data layer / scanners / scoring / risk gate / executor) and does not use phase labels. | The two architecture docs now disagree about the canonical decomposition. |

**Recommendation:** This file represents a forward-looking architecture plan rather than the as-built system. It should land in one of three places, and the choice matters:

- **Option A — Move it under `docs/architecture/` and label it `architecture-v4-target.md`.** Treat it as the target architecture for post-validation work (Phase 2 / multi-exchange / EventBus). Add a header banner: "Target architecture, not as-built. As-built is in `system-overview.md`." Cross-link from `docs/architecture/README.md`.
- **Option B — Move it under `docs/architecture/` and label it `architecture-v4.md`** as the new canonical, then immediately rewrite `docs/architecture/system-overview.md` to match. This is a larger lift and should not be done while the engine is frozen, because the README's "Bybit / OKX / Hyperliquid adapters — Planned" status row would need to flip and that depends on actual engine work.
- **Option C — Leave it where it is** and add a one-line note to `README.md`: "See `architecture/architecture.md` (working draft) for the v4 target architecture." Lowest cost; preserves the as-is canonical view.

Whichever option: the **162 features**, **98 paths**, **16 pages**, **133 events/sec**, and **EventBus / Recording Daemon** claims need either source citations or removal before the file is treated as canonical anywhere. They are unsourced numerics and a possibly-aspirational component.

#### `mvp-readiness-checklist.md` — 193 lines, mtime 2026-04-29 12:20

**What it is:** A "real capital" readiness checklist organized into 9+ sections (Data & Providers, Data Quality / Monitoring / Failover, Core Engine & Risk Controls, Backtesting, LLM & Tools Hygiene, Observability & Audit Trail, plus follow-on sections in the unread tail of the file). Each row carries a status (✅ / 🟡 / ❌ / ⏸) and a phase label (P1 / P1.5 / P2 / P3).

**Why it matters:** This is the first file in the repo that explicitly distinguishes the **"ship Phase 1 to testnet" gate (COI-41, the validation window that just closed)** from the **"connect to real capital" gate (this checklist)**. The README only mentions the validation window. The two gates have very different acceptance criteria.

**Conflicts and gaps vs. existing canonical docs:**

| Field in checklist | Same field in existing canonical doc | Drift |
| --- | --- | --- |
| `max_total_exposure_pct: 80` | `README.md` "Position heat cap: 80%" | Match — just terminology. |
| `max_daily_loss_pct: 2`, `max_drawdown: 10` | `README.md` "Daily loss limit: 5%, Max drawdown: 10%" | **Daily loss disagrees.** README says 5%, checklist says 2%. The 2% figure also matches the 2026-04-15 archived `CoinScopeAI-Context.md` ("MAX_DAILY_LOSS_PCT default: 2.0"). The README's 5% is the one that's drifted. |
| Running leverage ceiling: 10× (cap 20×) | `README.md` "Max leverage: 20x" | README quotes the cap, checklist quotes the running setting. Not a contradiction; arguably the README should mention both. |
| Max concurrent positions: "≤ 5" | `README.md` "Max concurrent positions: 3" | **Disagreement.** README says 3, checklist says 5. One of them is wrong. |
| OKX + Hyperliquid via CCXT (data) — ✅ P1 | `README.md` "Bybit / OKX / Hyperliquid adapters — Planned" | Disagreement, same as the architecture-doc finding above. |

**Recommendation:** This file should be promoted to `docs/risk/mvp-readiness-checklist.md` (or `docs/product/mvp-readiness-checklist.md`) and linked from `docs/README.md`. Before it is committed, the maintainer should reconcile the **two numeric disagreements** with `README.md` and pick a single canonical value:

1. Daily loss limit — README 5% vs. checklist 2%. Likely the checklist is correct (matches 2026-04-15 context doc and the engine's `MAX_DAILY_LOSS_PCT=2.0` default in `coinscope_trading_engine/config.py`); the README's 5% appears to be the author's aspirational ceiling, not the running setting. Confirm against `coinscope_trading_engine/config.py` and pick one.
2. Max concurrent positions — README 3 vs. checklist 5. Confirm against `coinscope_trading_engine/risk/exposure_tracker.py` and pick one.

Both are pure-docs edits (no engine change) once the maintainer confirms which value is correct. Effort: ~15 minutes for the reconciliation, ~5 minutes for the cross-link from `docs/README.md`.

### 5c. New code-review artifacts since 2026-04-21

| Path | Type | Notes |
| --- | --- | --- |
| `CODE_REVIEW_2026-04-22.md` | Report | Already present at 2026-04-21 run? Re-checked — yes, present in tree on 2026-04-22 (mtime 2026-04-22 09:28). Untracked, same status as siblings. |
| `CODE_REVIEW_2026-04-23.md` | Report | mtime 2026-04-23 07:16. Untracked. |
| `CODE_REVIEW_2026-04-24.md` | Report | mtime 2026-04-24 08:22. Untracked. |
| `CODE_REVIEW_2026-04-26.md` | Report | mtime 2026-04-26 06:13. Untracked. |
| `CODE_REVIEW_2026-04-30.md` | Report | mtime 2026-04-30 06:15. Untracked. |
| `CODE_REVIEW_2026-05-01.md` | Report | mtime 2026-05-01 06:17. Untracked. Today's automated code review. |

**Cumulative:** Nine `CODE_REVIEW_*.md` files (Apr 19 through May 01) are now untracked at the repo root. The 2026-05-01 review is the **thirteenth consecutive day** with zero source changes in scope; it carries seven P0s, seventeen P1s, and twenty-two P2s — all but a small number of which are carryovers from earlier reviews.

### 5d. What's in `CODE_REVIEW_2026-05-01.md`

Verification pass over the same engine files reviewed on 2026-04-30 (no source changes). Severity tally:

- **P0 (7):** unchanged from the past two weeks — signed-REST HMAC mismatch (§3.1), liquidation REST normaliser (§3.2), correlation gate fail-open (§3.3), webhook HMAC missing timestamp (§3.4), WS reconnect-counter no-op (§3.5), alert-queue full/put race (§3.6), rate-limiter bucket-leak + lock-scope (§3.7).
- **P1 (17):** +1 today — shared HMM regime detector overwritten on each per-symbol fit (§5.4 of the code review). Net effect: at any given time the detector is parametrised by whichever symbol last triggered a first-time fit; every other symbol's predictions are stale.
- **P2 (22):** +3 today — confidence saturates at threshold not at full strength (§5.5), entry/exit calculator min/max-vs-most-recent comment drift (§5.6), `signal_generator.py:139` division by 1.0 (§5.7).

**Implications for documentation:** none of the review items require *new* docs. Two of them suggest *updates* to existing docs once fixed:

- `risk/correlation_analyzer` fail-open semantics — if/when fixed, `docs/risk/risk-gate.md` §7 should gain a one-sentence clarification: "If correlation cannot be computed due to insufficient price history, the candidate is rejected with `correlation_insufficient_data`." Queue this behind the code fix.
- The newly-flagged P1 in `signal_generator.py` (shared HMM detector across symbols) is **not** described in `docs/ml/ml-overview.md`; the doc currently implies per-symbol model isolation. Once the code fix lands (per-symbol detector or detector cache), the doc should explicitly state per-symbol semantics. Queue this behind the code fix.

### 5e. New doc-update artifacts since 2026-04-21

| Path | Status |
| --- | --- |
| `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-04-21.md` | Untracked carryover. |
| `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-05-01.md` (this file) | Untracked, new today. |

**Cumulative:** Three doc-update reports (`2026-04-19`, `2026-04-21`, `2026-05-01`) are now untracked under `archive/doc_update_reports/`. The cadence skipped runs on Apr 22–30; this is the first run after the validation window closed.

### 5f. Other untracked items still on disk (carryover)

Re-checked on 2026-05-01, status table below. Nothing has moved since 2026-04-21.

| Path | Still untracked? | Recommended disposition (carryover) |
| --- | --- | --- |
| `research/funding-data-vendor-comparison.md`, `research/okx_vs_bybit_oi.md`, `research/regime_features_research.md` | yes | Research artifacts — fine to stay local. |
| `incidents/2026-04-18_*.md` | yes | Canonical coverage already in `docs/runbooks/incident-binance-ws-disconnect-2026-04-18.md`. |
| `manus_upload/*_SKILL.md` (7 files), `crypto_futures_dev/SKILL.md`, `tasks/QA-BILLING-Stripe-Connector-Smoke-Test.md` | yes | Collaborator uploads; not canonical. |
| `tests/test_billing_*.py` (3 files) | yes | Source-control hygiene — not a doc item. |
| `Stable Dashboard.pdf`, `fss4.pdf`, `ps-form-1583-june-2024.pdf` | yes | Binary artifacts unrelated to engine docs. |

### 5g. Features that need new documentation

Only one as of this run: the **two new top-level artifacts** (`architecture/architecture.md` and `mvp-readiness-checklist.md`) need a place in the documentation map. Specific recommendations are in §5b. Engine code itself: still nothing net-new since 2026-04-19; nothing else to document.

---

## 6. Recommended next actions — priority-ordered

| # | Action | Owner | Blocker | Effort | Age |
| - | - | - | - | - | - |
| 1 | **Update README.md status banner** to reflect the post-validation state (validation closed 2026-04-30). Add a one-line cross-link to `architecture/architecture.md` and `mvp-readiness-checklist.md`. (§3) | Repo maintainer | None | ~10 min | **NEW — became actionable today** |
| 2 | **Reconcile the two numeric disagreements** between `README.md` and `mvp-readiness-checklist.md` — daily-loss limit (5% vs. 2%) and max concurrent positions (3 vs. 5). Verify against `coinscope_trading_engine/config.py` and `risk/exposure_tracker.py`, then pick one canonical value in each doc. (§5b) | Risk owner | None | ~15 min | **NEW** |
| 3 | **Decide where `architecture/architecture.md` and `mvp-readiness-checklist.md` belong** in the documentation tree. Recommend Option A (move under `docs/architecture/` as `architecture-v4-target.md` and `docs/risk/mvp-readiness-checklist.md`, label as target architecture, cross-link). Add to `docs/README.md` index. (§5b) | Docs owner | Maintainer decision on canonical-vs-target | ~30 min | **NEW** |
| 4 | **Source the unsourced numerics** in `architecture/architecture.md` — 162 features, 98 paths, 16 pages, 133 events/sec — or remove them. (§5b) | Architecture owner | None | ~30 min | **NEW** |
| 5 | Open the pure-docs PR rewriting `docs/api/backend-endpoints.md` to match `coinscope_trading_engine/api.py` (§4d outline). Include billing router and port-8002 billing-service endpoints. Reconcile with the "98 paths" claim from §4c. | Docs owner | None | ~1 hr | **Outstanding 12 days** (since 2026-04-19) |
| 6 | Decide whether `/ready`, `/orders`, `/kill-switch`, `/symbols`, `/depth/{symbol}`, `/metrics` stay as "planned / post-validation" or are removed. Record as ADR-0004 if kept. | Engine lead | None | ~30 min | Outstanding 12 days |
| 7 | Add terminology cross-link between the 0–12 references (`glossary.md`, `component-map.md`, `data-flow.md`) and `docs/ml/confidence_scoring_baseline.md`. | Docs owner | None | ~15 min | Outstanding 10 days (since 2026-04-21) |
| 8 | Queue: after the §3.3 fail-closed fix in `risk/correlation_analyzer.py` lands (post-validation), add a one-sentence clarification to `docs/risk/risk-gate.md` about the `correlation_insufficient_data` rejection reason. | Risk owner | Engine fix (post-freeze) | ~10 min | Outstanding 10 days |
| 9 | Queue: after the §5.4 per-symbol-isolation fix in `signal_generator.py` lands, update `docs/ml/ml-overview.md` to state per-symbol detector semantics explicitly. | ML owner | Engine fix (post-freeze) | ~10 min | **NEW** |
| 10 | Commit or discard the untracked report artifacts (`CODE_REVIEW_2026-04-19.md` … `CODE_REVIEW_2026-05-01.md`, `DOC_UPDATE_REPORT_2026-04-19.md`, `DOC_UPDATE_REPORT_2026-04-21.md`, `DOC_UPDATE_REPORT_2026-05-01.md`). | Repo maintainer | None | ~5 min | Outstanding (growing) |
| 11 | Audit and either remove or commit the remaining untracked files on disk (`research/`, `incidents/`, `tests/test_billing_*.py`, `tasks/`, `manus_upload/`). | Repo maintainer | None | ~30 min | Outstanding 12 days |

The freeze is over; **Items 1, 2, 3, and 5 should land in this week's work**. The rest can be sequenced behind whatever post-validation engine work the maintainer decides to do first.

---

## 7. What this run changed

- **Wrote** this report to `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-05-01.md`, matching the convention established by the prior scheduled runs.
- **Did not** modify `CoinScopeAI-Context.md`, `README.md`, or any file under `docs/`. All edits are pending maintainer review per the cadence convention.
- **Surfaced two NEW canonical-grade artifacts** (`architecture/architecture.md`, `mvp-readiness-checklist.md`) that landed during the freeze without being threaded into the documentation map. Recommended placement and reconciliation work is itemised in §5b and §6.

---

*End of report. Next scheduled run: per cadence configuration. If the engine begins changing again post-validation, expect this file to grow rather than shrink.*

# DOC_UPDATE_REPORT — 2026-04-21

**Run type:** Scheduled (`documentation-update`, autonomous mode)
**Author:** Scoopy (Claude)
**Scope:** CoinScopeAI-Context.md · README.md · docs/api/* · new-feature log since the 2026-04-19 run
**Branch:** `restructure/2026-04-18-tier1-docs` (unchanged since last run — still ahead of `main`; working tree has only the three untracked markdown artifacts listed below)
**Mode notes:** Engine remains under the 2026-04-10 → 2026-04-30 testnet-validation code freeze. Per the convention established by the six prior runs in this folder, this report is report-only and does not modify canonical docs. Any rewrites recommended below should go through a pure-docs PR against `restructure/2026-04-18-tier1-docs` with CODEOWNERS sign-off.

---

## 1. Executive Summary

- **Nothing has landed in git since the 2026-04-19 run.** `git log --since="2026-04-19"` returns zero commits. `HEAD` is still `59416a2` (Tier-1 restructure). The validation freeze is holding.
- Three artifacts are untracked in the working tree — all are automated-report outputs, none are canonical docs:
  - `CODE_REVIEW_2026-04-19.md` (untracked since the prior run)
  - `CODE_REVIEW_2026-04-21.md` (new since the prior run — today's automated code review)
  - `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-04-19.md` (the prior report — still untracked)
- **Documentation status is unchanged from 2026-04-19:**
  - `CoinScopeAI-Context.md` — retired in `archive/historical_reports/`, no action.
  - `README.md` — current, no action.
  - `docs/api/api-overview.md` — current, no action.
  - `docs/api/backend-endpoints.md` — **still drifted** relative to `coinscope_trading_engine/api.py`. The rewrite recommended in the 2026-04-19 report (§4c) has not been opened.
- Nothing ships this week that is net-new and undocumented. Today's `CODE_REVIEW_2026-04-21.md` is a verification pass over the same engine state reviewed on 2026-04-19 and includes a §6 "corrections to the 2026-04-19 review" block; those corrections only affect severity reclassification, not documentation.
- One new observation this run: the `0–12 confluence` terminology across `docs/onboarding/glossary.md` and `docs/architecture/*.md` is partially clarified in `docs/ml/confidence_scoring_baseline.md` but not cross-linked from the other two — minor, flagged in §5.

Overall grade: **documentation remains broadly current.** The one material item — the API-endpoint reference — has now been outstanding for two consecutive scheduled runs; elevating it from "recommended" to "overdue".

---

## 2. CoinScopeAI-Context.md — Status

**File:** `archive/historical_reports/CoinScopeAI-Context.md` · 412 lines · last on-disk touch 2026-04-18 23:32 (unchanged).

- **Status: still retired.** Resides in `archive/historical_reports/`, indexed by `archive/README.md`, not linked from the root `README.md` or any doc in the live `docs/` tree. Its former content continues to be covered by the post-restructure `docs/` tree plus the rewritten root README (mapping reproduced in the 2026-04-19 report, §2).
- **Recommendation:** no action. Leave in archive. Do not revive.

---

## 3. README.md — Status

**File:** `/README.md` · 199 lines · last touch 2026-04-19 (commit `59416a2`, unchanged).

Re-verified against the tree on 2026-04-21:

- **"What this repo is" directory list** — still matches `ls` output (top-level dirs: `coinscope_trading_engine/`, `billing/`, `ml/`, `dashboard/`, `data/`, `tests/`, `scripts/`, `incidents/`, `docs/`, `archive/`). Plus: `research/`, `tasks/`, `manus_upload/`, `crypto_futures_dev/`, `market_scanner_skill/`, `coinscopeai-skills/`, `skills/`, `testnet_trader/`, `infra/`, `docker/`, `manus_setup/` are on disk but, as noted in the 2026-04-19 report §5c, are collaborator uploads / research artifacts rather than canonical engine surfaces; the README intentionally does not enumerate them.
- **Key-endpoints table (21 endpoints, port 8001)** — still matches `coinscope_trading_engine/api.py` exactly (re-verified in §4 below).
- **Risk thresholds, tech stack, module-status table, documentation map** — all still accurate, no code changes since last verification.
- **Validation freeze window (2026-04-10 → 2026-04-30)** — still in force, 9 days remaining.

**Recommendation:** no edits.

---

## 4. API endpoint documentation — **still drifted (carryover)**

### 4a. `docs/api/api-overview.md` — accurate

No changes since last run. Base URL, auth scheme, error envelope, versioning, CORS, timeouts, observability — all still correct. No edits recommended.

### 4b. `docs/api/backend-endpoints.md` — **drifted**

Re-verified on 2026-04-21 by comparing `grep '^@app\.(get\|post)' coinscope_trading_engine/api.py` against the doc. The drift is unchanged from the 2026-04-19 report:

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

**Plus the mounted billing router** (`APIRouter(prefix="/billing", tags=["Billing"])` in `coinscope_trading_engine/billing/stripe_gateway.py`, mounted via `app.include_router(billing_router)` at `api.py:218`):

| Method | Path |
| --- | --- |
| GET | `/billing/plans` |
| GET | `/billing/subscription` |
| POST | `/billing/checkout` |
| POST | `/billing/portal` |
| POST | `/billing/webhook` |

**Endpoints described in the doc that do not exist in code today** (carried from prior report): `GET /ready`, `GET /scan` (code uses POST), `GET /regime/{symbol}` (code uses GET /regime with no path param), `GET /risk-gate` (split across `/exposure` + `/circuit-breaker`), `GET /orders`, `POST /kill-switch` (split across `/circuit-breaker/{trip,reset}`), `GET /symbols`, `GET /depth/{symbol}`, `GET /billing/me`, and the doc's `POST /billing/portal` description does not match the router path convention (router prefix is `/billing` so the actual path is `/billing/portal`; the doc's path is fine but adjacent endpoints in the same section use inconsistent prefix treatment). `GET /metrics` is served by `metrics_exporter.py`, not FastAPI.

**Endpoints shipping but not documented** (carried from prior report): `GET /config`, `GET /signals`, `GET /exposure`, `GET /circuit-breaker`, `POST /circuit-breaker/trip`, `GET /sentiment`, `GET /anomaly`, `GET /correlation`, `GET /performance/equity`, `GET /scale`, `POST /scale/check`, `GET /validate`.

The "**21 endpoints total** as of 2026-04-18" footer in the doc numerically matches the engine count — but the mapping from number to list is wrong because five of the enumerated 19 items don't exist and 12 shipping endpoints are missing. The footer is a false-agreement artifact.

### 4c. Recommended rewrite (unchanged from 2026-04-19 §4c)

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

### 4d. Billing service (port 8002) — unchanged

Coverage gap for `billing/webhook_handler.py`, `billing/customer_portal.py`, and `billing/stripe_checkout.py` endpoints is unchanged from the 2026-04-18 / 2026-04-19 reports. Fold into the same PR as §4c.

---

## 5. New features / activity — week of Apr 19–21, 2026

### 5a. Commits

Zero commits since the prior scheduled run. Full git log since the last report:

| SHA | Date | Subject |
| --- | --- | --- |
| _(none)_ | — | — |

`HEAD` is still `59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)`.

### 5b. Untracked artifacts added since 2026-04-19

| Path | Type | Notes |
| --- | --- | --- |
| `CODE_REVIEW_2026-04-21.md` | Report | Today's automated code review. Contents reviewed — see §5c. |
| `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-04-19.md` | Report | Still untracked. Per the convention of the five prior runs, these files live in the archive subfolder but are not committed until someone bundles them into a hygiene PR. |

### 5c. What's in `CODE_REVIEW_2026-04-21.md`

It's a verification pass over the same engine files reviewed on 2026-04-19 (no source changes), and it recharacterizes two P0 items from the 2026-04-19 review that did not hold up on re-inspection. The severity tally in today's file:

- **P0 (4):** `risk/correlation_analyzer.py` fail-open (confirmed, but via `None → 0.0` coercion + `continue` on missing data, not a try/except as originally claimed); `data/binance_websocket.py:247` reconnect-counter no-op; `alerts/webhook_dispatcher.py` HMAC does not cover timestamp; `alerts/alert_queue.py::_enqueue` full-check / put race.
- **P1 (11):** RSI on thin data, Kelly falsy-guard, over-broad exception catches, indicator recompute cost, `scanner/` vs `scanners/` duplication, `MAX_RAW_SCORE` vs docs mismatch, etc.
- **P2 (14):** hygiene items (datetime.utcnow deprecation, duplicated telegram modules, magic numbers, etc.).

**Implications for documentation:** none of the review items require *new* docs. Two of them suggest *updates* to existing docs once fixed:
- `risk/correlation_analyzer` fail-open semantics are not currently spelled out in `docs/risk/risk-gate.md` (that doc describes the policy, not the code's handling of insufficient data). If the fix lands as recommended in the code review (fail-closed on `None`), `docs/risk/risk-gate.md` §7 should gain a one-sentence clarification: "If correlation cannot be computed due to insufficient price history, the candidate is rejected with `correlation_insufficient_data`." Queue this behind the code fix.
- The `MAX_RAW_SCORE = 300.0` vs "0–12 confluence" terminology is already reconciled in `docs/ml/confidence_scoring_baseline.md` (see §6 below), but `docs/onboarding/glossary.md` and `docs/architecture/component-map.md` still describe the 0–12 as the authoritative engine value. Suggest a one-line cross-link from each of those files to `docs/ml/confidence_scoring_baseline.md`.

None of the above is urgent; all are freeze-compatible pure-docs edits and can be bundled with the API-reference rewrite.

### 5d. On-disk untracked files from the prior-run inventory

Re-checked on 2026-04-21, status table below. Nothing has moved.

| Path | Still untracked? | Recommended disposition (carryover) |
| --- | --- | --- |
| `research/funding-data-vendor-comparison.md`, `research/okx_vs_bybit_oi.md`, `research/regime_features_research.md`, `research/regime_features_matrix.xlsx` | yes | Research artifacts — fine to stay local. |
| `incidents/2026-04-18_EXECUTION_duplicate_orders_retry.md`, `incidents/2026-04-18_dashboard_redis_drift.md` | yes | Canonical coverage is already in `docs/runbooks/incident-binance-ws-disconnect-2026-04-18.md`. |
| `manus_upload/*_SKILL.md` (7 files), `crypto_futures_dev/SKILL.md`, `tasks/QA-BILLING-Stripe-Connector-Smoke-Test.md` | yes | Collaborator uploads; not canonical. |
| `tests/test_billing_webhook.py`, `tests/test_billing_portal.py`, `tests/test_billing_schema.py` | yes | These exist on disk but are not part of the restructure commit. Worth tracking — but that's a source-control hygiene item, not a doc item. |

### 5e. Features that need new documentation

None. Still nothing net-new since 2026-04-19. The engine codebase and its feature surface are static under the freeze.

---

## 6. New observation this run — minor terminology cross-link

`docs/ml/confidence_scoring_baseline.md` (line 39) already clarifies the relationship:

> Scale: 0.0 – 100.0 (NOT 0–12 — the 0–12 value the scanner/dashboard shows is a dashboard-side roll-up; the authoritative engine value is the 0–100 float.)

But the two other authoritative references still describe the 0–12 integer as the engine's output without this caveat:

- `docs/onboarding/glossary.md:31-33` — "Scorer. The multi-factor model that produces a 0–12 confluence score per symbol." and "Confluence score. The 0–12 integer the scorer emits."
- `docs/architecture/component-map.md:57` — "The multi-factor confluence model that emits a 0–12 score per symbol."
- `docs/architecture/data-flow.md:29, 96` — "confluence score 0–12" and "A 0–12 integer confluence score."

New readers hitting the onboarding glossary or the architecture diagrams first will form the wrong mental model and then be surprised by §3.9 of today's code review.

**Recommendation:** add a one-liner parenthetical to each of the four call-sites above: `(see confidence-scoring-baseline.md — the 0–12 is a dashboard roll-up; the engine emits a 0–100 float.)`. Alternatively, leave the short-form 0–12 in those files and add a single "Terminology note" box at the top of `docs/architecture/component-map.md` referencing the baseline doc.

Estimated effort: 15 minutes. Fold into the API-reference PR.

---

## 7. Recommended next actions

| # | Action | Owner | Blocker | Effort | Age |
| - | - | - | - | - | - |
| 1 | Open the pure-docs PR rewriting `docs/api/backend-endpoints.md` to match `coinscope_trading_engine/api.py` (§4c outline). Include billing router and port-8002 billing-service endpoints. | Docs owner | None | ~1 hr | **Outstanding since 2026-04-19** |
| 2 | Decide whether `/ready`, `/orders`, `/kill-switch`, `/symbols`, `/depth/{symbol}`, `/metrics` stay as "planned / post-validation" or are removed. Record as ADR-0004 if kept. | Engine lead | None | ~30 min | Outstanding since 2026-04-19 |
| 3 | Add terminology cross-link between the 0–12 references (glossary.md, component-map.md, data-flow.md) and `docs/ml/confidence_scoring_baseline.md` (§6). | Docs owner | None | ~15 min | **New this run** |
| 4 | Queue: after the §3.1 fail-closed fix in `risk/correlation_analyzer.py` lands (post-validation), add a one-sentence clarification to `docs/risk/risk-gate.md` about the `correlation_insufficient_data` rejection reason. | Risk owner | Engine fix (post-freeze) | ~10 min | New this run |
| 5 | Commit or discard the untracked report artifacts (`CODE_REVIEW_2026-04-19.md`, `CODE_REVIEW_2026-04-21.md`, `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-04-19.md`, and this report). | Repo maintainer | None | ~5 min | New this run |
| 6 | Audit and either remove or commit the remaining untracked files on disk (`research/`, `incidents/`, `tests/test_billing_*.py`, `tasks/`, `manus_upload/`). | Repo maintainer | None | ~30 min | Outstanding since 2026-04-19 |
| 7 | After validation window closes (2026-04-30), re-run this same scheduled report and re-open any drift items deferred during the freeze. | Automation | 2026-04-30 | Automatic | Recurring |

---

## 8. What this run changed

- **Wrote** this report to `archive/doc_update_reports/DOC_UPDATE_REPORT_2026-04-21.md`, matching the convention established by the six prior scheduled runs.
- **Wrote** an identical copy to the session outputs folder for immediate visibility.
- **No other files were modified.** No canonical docs, no engine code, no `.env*`, no billing material.
- **No git operations** (add / commit / push) were performed.

---

*End of report.*

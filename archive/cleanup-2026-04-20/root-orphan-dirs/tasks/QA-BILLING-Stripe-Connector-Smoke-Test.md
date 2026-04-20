# [QA] BILLING — Stripe Connector Smoke Test

**Type:** QA
**Area:** BILLING
**Domain (Notion):** Infrastructure
**Priority:** Medium
**Status:** Backlog
**Environment:** Staging (Stripe Test Mode only — `pk_test_…` / `sk_test_…`)
**Sprint/Cycle:** Backlog
**Review Required:** Yes
**Owner:** _(unassigned)_
**Linked Linear issue:** COI-39 (Stripe Billing Integration — Done) — this is the post-integration validation

---

## Summary

One-shot, read-only smoke test that validates the Stripe billing surface in **two parts**:

1. **Connector health** — the Stripe MCP is authenticated, reachable, and returning expected data on a standard set of read endpoints.
2. **CoinScopeAI plans** — the four canonical subscription tiers (Starter / Pro / Elite / Team) and their monthly + annual prices exist in Stripe and match the values published on the dashboard and landing page.

No customers, no subscriptions, no payment links, no charges are created during this test. Every call is a `list_*` / `retrieve_*`.

---

## Why now

COI-39 shipped the Stripe integration, and the primary dashboard (`coinscopedash-tltanhwx.manus.space`) currently renders pricing from the Stripe side. Before the 30-day testnet validation (COI-41) reaches any customer-facing test, we need a deterministic check that:

- The connector has not silently lost credentials.
- The four-tier pricing on the live dashboard matches what Stripe actually serves.
- Nothing in test mode has drifted from the canonical pricing model (Starter $19 / Pro $49 / Elite $99 / Team ~$299, annual = 20% discount).

This is a **standing smoke test** — the same script should be safe to re-run any day without side effects.

---

## Pre-requisites

- [ ] Stripe MCP is connected in the operator's Claude/Cowork session (test-mode credentials).
- [ ] Access to the canonical pricing table in `project_current_state.md` memory (source of truth for expected values).
- [ ] No prohibited actions: no refunds, no subscription cancels, no account setting changes.

---

## Test Plan

All steps are read-only. Each step has an explicit pass criterion.

### Part A — Connector health (Stripe MCP)

| # | Check | Tool | Pass criterion |
|---|-------|------|----------------|
| A1 | Account identity | `get_stripe_account_info` | Returns live account object; `livemode` is `false`; account ID matches the test account in `.env`. |
| A2 | Balance reachable | `retrieve_balance` | Call returns a 200/object without error. Exact balance is not asserted. |
| A3 | Customers listable | `list_customers` (limit 1) | Returns an array (may be empty). No auth error. |
| A4 | Products listable | `list_products` (limit 20, `active=true`) | Returns at least 4 active products (one per tier). |
| A5 | Prices listable | `list_prices` (limit 50, `active=true`) | Returns at least 8 active prices (monthly + annual × 4 tiers, Team annual may be custom). |
| A6 | Invoices listable | `list_invoices` (limit 1) | Returns an array without error. |
| A7 | Payment intents listable | `list_payment_intents` (limit 1) | Returns an array without error. |

**Exit A:** All 7 calls succeed. Any failure → log the error, open an INCIDENT task, stop Part B.

### Part B — CoinScopeAI plan verification

| # | Check | Expected value |
|---|-------|----------------|
| B1 | Starter product exists and is active | Product name contains "Starter" |
| B2 | Starter monthly price | `unit_amount = 1900`, `currency = usd`, `recurring.interval = month` |
| B3 | Starter annual price | `unit_amount = 19000`, `recurring.interval = year` |
| B4 | Pro product exists and is active | Product name contains "Pro" |
| B5 | Pro monthly price | `unit_amount = 4900`, `recurring.interval = month` |
| B6 | Pro annual price | `unit_amount = 49000`, `recurring.interval = year` (flagged "Most Popular" on landing) |
| B7 | Elite product exists and is active | Product name contains "Elite" |
| B8 | Elite monthly price | `unit_amount = 9900`, `recurring.interval = month` |
| B9 | Elite annual price | `unit_amount = 99000`, `recurring.interval = year` |
| B10 | Team product exists and is active | Product name contains "Team" |
| B11 | Team monthly price | `unit_amount ≈ 29900`, `recurring.interval = month` (±1 tier variation acceptable; flag if different and stop) |
| B12 | Team annual price | Either a published annual price OR documented as "Custom / contact sales" in product metadata |

**Annual discount sanity:** for Starter/Pro/Elite, assert `annual_amount ≈ monthly_amount × 12 × 0.80` (±$1 rounding tolerance). This enforces the 20% annual-discount rule.

---

## Pass / Fail criteria

- **PASS** — All A1–A7 succeed AND all B1–B11 match. B12 may be "Custom" without failing the test as long as it's documented.
- **FAIL (connector)** — any A step errors. Smoke test is aborted; file an INCIDENT.
- **FAIL (pricing drift)** — any B1–B11 mismatch. Task goes to "In Review" with a diff of expected vs. actual.
- **WARN** — Part A passes, Part B passes, but annual-discount check is off by more than $1. Does not block; log for follow-up.

---

## Deliverables / Artifacts

1. A run report saved to `/CoinScopeAI/qa-reports/stripe-smoke-YYYY-MM-DD.md` containing:
   - Timestamp (UTC+3)
   - Account ID (last 4 chars only)
   - Table of A1–A7 results (pass/fail + raw error if any)
   - Table of B1–B12 expected vs. actual
   - Overall verdict: PASS / WARN / FAIL
2. Task updated in Notion Tasks DB with status transition and the run report link.
3. If FAIL, a linked follow-up task `[FIX] BILLING — <specific failure>` created under the same Project relation.

---

## Out of scope

- Creating customers, subscriptions, payment links, or invoices.
- Any write operation in Stripe (refunds, cancellations, dispute updates).
- Anything in live mode.
- Dashboard UI validation — that's a separate `[QA] DASHBOARD — Billing Page Render` task.
- Changes to the canonical pricing model — requires Mohammed's approval (see memory).

---

## Acceptance Criteria (for closing the task)

- [ ] Part A executed; results tabled; all 7 endpoints green.
- [ ] Part B executed; all 4 tiers verified; pricing matches canonical table.
- [ ] Annual discount math validated to within $1.
- [ ] Run report file committed to `/CoinScopeAI/qa-reports/`.
- [ ] Notion task status moved to "Done" (PASS) or "In Review" (WARN / FAIL).
- [ ] If FAIL, follow-up `[FIX]` task created and linked.

---

## Notes for whoever runs this

- Use Stripe MCP read tools only: `get_stripe_account_info`, `retrieve_balance`, `list_customers`, `list_products`, `list_prices`, `list_invoices`, `list_payment_intents`.
- Do **not** use `create_*`, `update_*`, `cancel_*`, `finalize_invoice`, or `create_refund`.
- Expected to run in under 2 minutes.
- Safe to re-run daily as a standing check during the 30-day validation.

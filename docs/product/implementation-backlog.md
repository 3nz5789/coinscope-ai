# Implementation Backlog

**Status:** current
**Audience:** anyone asking "why isn't X done?" or planning post-validation work
**Related:** [`../architecture/future-state-roadmap.md`](../architecture/future-state-roadmap.md), [`../decisions/README.md`](../decisions/README.md), [`../risk/risk-framework.md`](../risk/risk-framework.md)

This is the canonical list of known, accepted-to-build items that are deliberately **not** being done during validation (2026-04-10 → 2026-04-30). Each item has a reason it's deferred, a rough shape of the work, and a rough priority for the post-validation window.

Items are grouped by theme, not strictly ranked. Priority within a theme is indicative.

## Legend

- **P0** — starts the week of 2026-05-01 if nothing blocks.
- **P1** — first month post-validation.
- **P2** — quarter post-validation.
- **P3** — on the radar but not scheduled.

## Housekeeping and refactor

| Item | Priority | Notes |
| --- | --- | --- |
| Merge `billing_server.py` (root) and `coinscope_trading_engine/billing/` package | P0 | Pick one. The in-package version is the more-tested target. Ensure no deploy config references the root file after the merge. |
| Consolidate `scanner/` vs `scanners/` modules | P1 | Same story — one canonical, archive the other. Rename imports in one pass. |
| Extract typed `Adapter` protocol from the Binance adapter shape | P1 | Triggered by the second adapter (Bybit). See [`../ops/exchange-integrations.md`](../ops/exchange-integrations.md). |
| Remove commented/stub `BYBIT_*`, `OKX_*`, `HYPERLIQUID_*` env placeholders | P2 | They were aspirational; they're confusing. Keep only what an adapter actually consumes. |
| Migrate billing DB from SQLite to Postgres by default | P2 | SQLite is fine for single-node; Postgres is required if we ever split API and worker across hosts. |

## Risk and sizing

| Item | Priority | Notes |
| --- | --- | --- |
| Revisit `KELLY_FRACTION = 0.25` against real validation-era P&L | P0 | WFV over the validation window. Expected outcome: confirm or adjust by ≤ one step (e.g., to 0.20 or 0.30). |
| Per-symbol volatility clamp as an additional sizing step | P1 | Can only reduce size; safe to add. Motivated by a few outlier-volatility symbols during validation. |
| Unified regime service combining HMM + v3 into one module | P1 | Today, consumers reach into two detectors. A service layer doesn't change semantics but removes a whole class of drift risk. |
| Cross-detector disagreement monitor | P1 | HMM-vs-v3 divergence tracker with alert when wide-divergence persists. |
| Trailing-stop order type in the executor | P2 | Binance supports it; we don't use it yet. Worth experimenting post-validation. |
| Post-trade attribution analysis (per-factor edge contribution) | P2 | Requires journal schema addition. |

## Observability

| Item | Priority | Notes |
| --- | --- | --- |
| Regime-distribution drift alert | P1 | Detects "HMM spending 90% of the week in chop" patterns. |
| Latency benchmark for hot path | P2 | Formalize the informal latency budgets in [`../architecture/data-flow.md`](../architecture/data-flow.md). |
| Dashboard for breaker trip history | P2 | Today it's a journal query; a rendered view is nice-to-have. |

## Exchange coverage

| Item | Priority | Notes |
| --- | --- | --- |
| Bybit perpetuals adapter | P1 | Second adapter. Forces the typed `Adapter` protocol. Testnet first, per the rules in [`../ops/exchange-integrations.md`](../ops/exchange-integrations.md). |
| OKX perpetuals adapter | P2 | Third adapter. Signature scheme is different; useful stress test for the protocol. |
| Hyperliquid adapter | P3 | On-chain account model; larger scope than the CEX adapters. |
| Mainnet Binance cutover spec | P0 | Doc that does not exist yet. Captures the sequence, thresholds, and rollback plan for the first week of mainnet. |
| Starting-equity floor for mainnet (`MAX_EQUITY_AT_RISK_USD`) | P0 | Hard cap on mainnet exposure during the scale-up period. |

## Billing and entitlements

| Item | Priority | Notes |
| --- | --- | --- |
| Stripe dunning behavior documented in operator runbook | P1 | What does the operator see when a customer's card fails? Currently inferred; should be written down. |
| Entitlement tier matrix in one place | P1 | Today the mapping lives in `billing/entitlements.py`. A markdown mirror for humans. |
| Admin "re-sync with Stripe" command | P2 | Rebuild the local mirror from Stripe API. Useful after a webhook secret rotation. |

## ML

| Item | Priority | Notes |
| --- | --- | --- |
| Retrain cadence and procedure | P0 | Validation is a frozen window; retraining resumes after. The procedure — data window, feature drift checks, re-deploy — needs writing down. |
| Alpha-decay auto-pause (optional, gated) | P2 | Today alpha-decay is advisory. A gated auto-pause is a policy question, not a code question. |
| Regime re-labeling on training distribution shift | P2 | If the HMM drifts meaningfully, we need a procedure, not a one-off. |

## API and SDK

| Item | Priority | Notes |
| --- | --- | --- |
| Pagination on `/journal` | P1 | Current limit-based API is adequate for the dashboard but awkward for bulk pulls. |
| Dashboard SDK package (typed client) | P2 | The dashboard currently hand-writes fetch calls. A generated client from OpenAPI would catch schema drift at build time. |
| Rate limiting on public endpoints | P2 | Not a concern today; relevant if we expose a public API. |

## Testing

| Item | Priority | Notes |
| --- | --- | --- |
| Fixture-over-regimes test for the full pipeline | P1 | End-to-end replay over a diverse set of market conditions. |
| Replay suite for every incident in `docs/incidents/` | P1 | If we've seen it once, we should have a test for it. |
| Performance regression test (hot-path latency) | P2 | Requires an infra bench; tied to the latency-benchmark item above. |

## Explicitly not in scope — will not be built

These have come up in conversation and have been declined. Listed here so they stop getting re-proposed.

- **Retail copy-trading features.** The engine is for the operator and any future directly-signed customers. It is not a social-trading product.
- **A training UI for ML artifacts.** Training is offline and scripted. Writing a UI around a workflow that is run once a quarter is ceremony.
- **Kubernetes deployment.** Single VPS is the target. K8s is out of scope until there's a concrete reason it's needed.
- **A mobile app.** The dashboard is responsive enough. A native app is not where the leverage is.
- **LLM in the hot path.** See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).
- **Custom-built charting.** TradingView is the standard; embedding beats rebuilding.
- **A plugin system for user strategies.** Plugin APIs are a long-term commitment. We are not ready for that.

## How to add to this backlog

1. Confirm the item isn't already here under a different name.
2. Add it under the right theme table with priority and a one-sentence note.
3. If the item is complex, open a companion doc at `docs/product/<slug>.md` and link to it.
4. If the item represents a policy decision (not just an engineering task), consider whether it deserves an ADR instead.

This backlog is re-read at the start of every post-validation planning cycle. Items that drift from P1 to P3 three cycles in a row should be moved to "not in scope" or explicitly reopened with a reason.

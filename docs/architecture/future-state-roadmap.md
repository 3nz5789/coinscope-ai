# Future-State Roadmap

**Status:** planned
**Audience:** reviewers, contributors, and stakeholders interested in direction (not commitments)
**Related:** [`system-overview.md`](system-overview.md), [`component-map.md`](component-map.md), [`../product/implementation-backlog.md`](../product/implementation-backlog.md)

This doc describes where CoinScopeAI may go **after the validation phase ends on 2026-04-30**. Nothing here is a commitment. It exists to give reviewers and new contributors a sense of the shape of the system we are trending toward, so they can design changes that don't paint us into a corner.

Everything labeled `planned` below is aspirational until it has code and a `current`-status doc.

## Post-validation horizon (weeks 1–4 after 2026-04-30)

### 1. Housekeeping refactors

These are the `coinscope_trading_engine/` internal reorganizations that were deferred for the validation freeze. They are mechanical and behavior-preserving.

- Collapse `core/` vs. root-level duplication into a single import tree.
- Merge `scanner/` and `scanners/` into one subpackage.
- Flatten or subpackage the loose top-level `.py` modules (`risk_gate.py`, `kelly_position_sizer.py`, `scorer.py`, `binance_*.py`) into explicit subpackages (`risk/`, `sizing/`, `signal/`, `adapters/binance/`).
- Resolve the `billing_server.py` vs. `billing/` duplication. One authoritative path.

None of these should change behavior. Each lands with tests that existed before the move.

### 2. Mainnet readiness, not cutover

Before flipping `BINANCE_TESTNET=false`, the following must exist:

- A mainnet cutover runbook (not written).
- A tiered-scale ramp policy (start at 1% of target notional, scale up gated on journal KPIs).
- A kill-switch drill documented and performed on mainnet configs before any real notional.
- A withdrawal-blocked API key policy — trading-only keys, never withdraw-enabled.

Mainnet cutover itself is a decision for after the runbook is reviewed, not something the validation phase alone unlocks.

### 3. Observability upgrade

- Prometheus scrape targets move from local-compose-only to a hosted Prometheus.
- Grafana dashboards with board definitions checked into the repo (`observability/dashboards/*.json`).
- SLOs defined for: adapter uptime, gate decision latency, journal write durability, order-ack latency.
- Paging rules wired to operator contact, with runbooks in `docs/runbooks/`.

## Medium horizon (months 2–4 after validation)

### 4. Multi-exchange

Planned adapters in priority order:

1. **Bybit** perpetuals. Closest API model to Binance; lowest integration lift.
2. **OKX** perpetuals.
3. **Hyperliquid.** Different account model (on-chain); larger surface-area change.

The adapter contract will be formalized into a protocol (typed `Adapter` interface) before the second adapter lands. Doing this now would be premature — you factor out the interface *from* the second implementation, not *before* it.

### 5. Regime system consolidation

The HMM (bull/bear/chop) and v3 classifier (Trending/Mean-Reverting/Volatile/Quiet) coexist today for legitimate reasons — different consumers, different histories. The plan is not "pick one" but "make the seams explicit":

- A single regime service that exposes both taxonomies with a clear contract per consumer.
- Training-data pipelines that refresh both models on the same cadence.
- A compatibility layer so Kelly multiplier lookups do not need to know whether the multiplier came from an HMM state or a v3 label.

### 6. Stripe billing hardening

- Webhook idempotency verified under replay.
- Entitlements service split from the webhook handler (the current coupling creates the `billing_server.py` vs. `billing/` drift).
- A clean customer-portal flow for subscription upgrades and cancellations.

## Long horizon (month 4+ after validation, speculative)

### 7. Strategy diversification

Today the engine runs one scoring model across all symbols. Candidates for diversification:

- A basis / carry strategy that trades funding-rate extremes.
- A liquidation-cascade mean-reversion strategy.
- A cross-exchange arbitrage strategy (unlocked by #4 above).

Each would be a separate named strategy with its own risk budget envelope inside the overall heat cap.

### 8. Post-trade analytics

- Per-factor attribution: which factors contributed to winning vs. losing trades.
- Alpha-decay tracking per strategy, visible to the operator before it becomes a problem.
- A dashboard view for "why did the engine reject this trade?" — joining journal entries into a readable narrative.

### 9. Mobile and alert surfaces

- Expanded Telegram alerting with structured deep-links into the dashboard.
- A mobile-friendly dashboard view for at-a-glance monitoring.
- On-call-style paging for serious incidents (breaker trips, adapter down beyond a grace window).

## What will **not** be built

These are out of scope even in the long horizon:

- **Retail-facing copy-trading.** The engine is a single-operator tool.
- **A user-facing ML training UI.** Training stays offline in `ml/`.
- **Kubernetes.** Docker Compose on a VPS is sufficient for the foreseeable operator shape.
- **A mobile app.** Web-responsive is enough.
- **LLMs on the hot path.** See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).

## How to use this doc

- **When reviewing a PR,** check that the change doesn't foreclose a direction listed here. A PR that hard-codes "Binance" into the risk gate, for example, makes #4 harder.
- **When designing a change,** prefer paths that make these directions easier or cheaper, even if you don't implement them.
- **When scoping a feature,** ask whether it belongs in the backlog ([`../product/implementation-backlog.md`](../product/implementation-backlog.md)) or whether the validation freeze makes it a non-starter for now.

This doc is updated as directions crystallize. When a `planned` item moves to `current`, it earns its own doc and is removed from this page.

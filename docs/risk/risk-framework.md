# Risk Framework

**Status:** current
**Audience:** required reading for anyone touching `risk/`, `execution/`, or position sizing
**Related:** [`risk-gate.md`](risk-gate.md), [`position-sizing.md`](position-sizing.md), [`failsafes-and-kill-switches.md`](failsafes-and-kill-switches.md), [`../backend/configuration.md`](../backend/configuration.md)

The risk framework is what turns a machine learning system into a trading engine. If the engine is the car, the risk framework is the brakes, the seat belts, and the governor — not a feature, the floor.

This doc states the philosophy. The neighboring docs cover the mechanics (gate, sizer, failsafes).

## The one principle

**Capital preservation first, profit generation second.** The engine's purpose is to compound slowly without destroying equity in a single bad regime. Every choice in this framework is a consequence of that ordering.

If a PR makes the engine more profitable on average but widens the worst-case loss by more than a token amount, the PR is wrong by construction — no matter how clean the code is.

## Invariants

These are properties the engine must never violate. Violations are incidents, not bugs.

1. **No trade bypasses the gate.** Every order placed by the executor was first sized by the Kelly sizer, which was called only after the gate returned accept.
2. **No size exceeds the hard cap.** The 2% per-trade cap is a hard ceiling, not a default. It cannot be overridden without a code change that goes through `risk/` review.
3. **A tripped breaker stops new entries.** Existing positions may continue to run, but no new entries until the breaker resets.
4. **The kill switch, when engaged, prevents new entries and cancels working orders.** It does not unwind existing positions automatically — that is always a human call.
5. **Every gate decision is journaled with a reason.** Rejections are as important as accepts for reconstruction.
6. **If the engine is in an uncertain state, it halts.** Halting is never wrong; guessing is.

These are not tunables. They are properties.

## Thresholds — the validation-era numbers

All values are locked between 2026-04-10 and 2026-04-30. Env-var names and the authoritative defaults live in [`../backend/configuration.md`](../backend/configuration.md).

| What | Value | Variable |
| --- | --- | --- |
| Max drawdown (peak-to-trough) | 10% | `MAX_DRAWDOWN_PCT` |
| Daily loss budget | 5% | `MAX_DAILY_LOSS_PCT` |
| Per-trade size cap | 2% of equity | `KELLY_HARD_CAP_PCT` |
| Fractional Kelly factor | 0.25 | `KELLY_FRACTION` |
| Portfolio heat cap | 80% | `POSITION_HEAT_CAP_PCT` |
| Max open positions | 5 | `MAX_OPEN_POSITIONS` |
| Max leverage per trade | 10x | `MAX_LEVERAGE` |
| Consecutive losses → breaker | 4 | `CONSECUTIVE_LOSSES_BREAKER` |
| Breaker reset window | 24 hours | `CIRCUIT_BREAKER_RESET_HOURS` |
| ATR stop multiplier | 1.5 × ATR | `ATR_STOP_MULTIPLIER` |
| Risk:reward ratio | 2:1 | `RR_RATIO` |
| Regime multipliers | bull 1.0, chop 0.5, bear 0.3 | `REGIME_MULT_*` |

## Layered defenses

The framework is deliberately redundant. A single number has to survive a single review; a layered system has to survive an entire review.

### Layer 1 — Signal quality

Low-quality candidates never reach the gate. The scorer has a per-regime floor, and symbols below the floor are dropped. The floor rises in volatile regimes.

### Layer 2 — Pre-trade gate

Every candidate passes through the risk gate ([`risk-gate.md`](risk-gate.md)). The gate checks regime alignment, heat, correlation, daily loss, breaker state, and kill switch. A rejection at this layer is the cheapest and most common form of protection.

### Layer 3 — Sizing discipline

Even an accepted candidate is subject to Kelly-fractional sizing with a hard cap ([`position-sizing.md`](position-sizing.md)). If the model is over-confident, the sizer clips to 2%. If the regime is bear, the multiplier shrinks size further.

### Layer 4 — Execution guardrails

Pre-trade slippage estimates against current depth. ATR-based stops and 2:1 RR take-profits are submitted alongside the entry. Order client IDs are deterministic so the journal can reconcile against the exchange.

### Layer 5 — Circuit breakers

Automatic halts for daily loss, max drawdown, and consecutive-loss streaks ([`failsafes-and-kill-switches.md`](failsafes-and-kill-switches.md)). A tripped breaker blocks the executor until the reset window elapses.

### Layer 6 — Kill switch

A manual halt operated by the human running the system. Engaging it is not a failure — it is a feature. Daily-ops practice includes exercising it.

## Regime awareness

Risk behavior changes with regime. The HMM detector supplies the multiplier table that the Kelly sizer reads; the v3 classifier informs per-regime scoring floors. See [`../ml/regime-detection.md`](../ml/regime-detection.md) for how the two systems coexist.

Briefly:

- **Bull (HMM).** Full regime multiplier (1.0). The engine is willing to express its best read on trend continuation.
- **Chop (HMM).** Half multiplier (0.5). Expected edge is smaller; size accordingly.
- **Bear (HMM).** 30% multiplier (0.3). The engine still trades, but very small, because bear regimes are where catastrophic drawdowns happen historically.
- **Volatile (v3).** Higher scoring floor. Fewer but higher-confidence candidates.
- **Quiet (v3).** Normal floor but tighter slippage tolerances.

## What this framework is not

- **It is not a profit framework.** Nothing here promises profit. Every threshold is a ceiling or a floor, never a target.
- **It is not a substitute for monitoring.** A running engine without an attentive operator is a bad idea even with every layer above in place.
- **It is not an excuse to skip review.** Every layer listed is code. Code rots. The layers hold because the team re-reads them and tests them.

## Reviewer expectations

When reviewing a PR that touches risk:

- **Two reviewers**, per [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).
- **Tests first.** The diff should include tests that fail on `main` and pass on the branch. If it doesn't, reject the review.
- **Ask: does this widen any worst case?** If yes and the worst case isn't justified in the PR description, reject.
- **Ask: does this violate an invariant above?** If yes, reject. Invariants are not soft.

## When to open an incident vs. a bug

| Observation | Response |
| --- | --- |
| Gate rejected a bad trade. | Normal operation. |
| Sizer clipped a size. | Normal operation. |
| Breaker tripped. | Expected under documented conditions. Investigate if unexpected. |
| Kill switch engaged manually. | Normal operation. |
| Order placed without a gate decision in the journal. | **Incident.** Violates invariant 1. |
| Order placed larger than 2% of equity. | **Incident.** Violates invariant 2. |
| New entry after a tripped breaker, before reset. | **Incident.** Violates invariant 3. |
| Journal missing a rejection. | **Incident.** Violates invariant 5. |

Incidents follow the runbook in [`../runbooks/troubleshooting.md`](../runbooks/troubleshooting.md). The 2026-04-18 write-up is the current template.

## Reading order for deeper dives

1. [`risk-gate.md`](risk-gate.md) — what the gate actually checks.
2. [`position-sizing.md`](position-sizing.md) — the Kelly pipeline.
3. [`failsafes-and-kill-switches.md`](failsafes-and-kill-switches.md) — breakers and manual halts.
4. [`../ml/regime-detection.md`](../ml/regime-detection.md) — how the regime multipliers are chosen.

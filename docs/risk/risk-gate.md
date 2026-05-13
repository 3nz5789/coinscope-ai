# Risk Gate

**Status:** current — P0 validation phase
**Audience:** developers reviewing or modifying [`risk_management/risk_gate.py`](../../risk_management/risk_gate.py) or [`services/paper_trading/safety.py`](../../services/paper_trading/safety.py)
**Related:** [`risk-framework.md`](risk-framework.md) · [`position-sizing.md`](position-sizing.md) · [`failsafes-and-kill-switches.md`](failsafes-and-kill-switches.md) · [`../api/engine-api-contract.md`](../api/engine-api-contract.md) · [`../runbooks/operator-workflow.md`](../runbooks/operator-workflow.md)

The risk gate is the single entry point for the question "should this trade happen?" Every candidate that leaves the scanner passes through it. Nothing else decides whether to trade — not the scorer, not the executor, not the LLM, not the dashboard.

> **On-main implementation note.** The risk-gate contract below describes the *intended* gate API. The current on-main implementation is split across two layers: the scan-time risk gate at [`risk_management/risk_gate.py`](../../risk_management/risk_gate.py) (invoked from [`engine/core/master_orchestrator.py`](../../engine/core/master_orchestrator.py)) and the submission-time fail-closed safety gate at [`services/paper_trading/safety.py`](../../services/paper_trading/safety.py) (the 4-layer `SafetyGate.validate_order` path). The split is intentional — the orchestrator gate is candidate-shaped; the safety gate is order-shaped. Both call kill-switch first and breaker-state second.

## Contract

```
def evaluate(candidate: Candidate, state: EngineState) -> GateDecision
```

**Inputs:** a scored candidate (symbol, side, score, factors) and the current engine state (open positions, heat, daily pnl, breaker state, kill switch).

**Output:** a structured decision — `accept` with a sizing plan, or `reject` with a machine-readable reason code.

**Side effects:** exactly one journal write per call. The journal entry contains the full decision payload.

## Checks, in order

The gate short-circuits on the first failing check. Order matters — cheaper checks come first.

### 1. Kill switch

If the kill switch is engaged, reject immediately with reason `kill_switch_engaged` (or, in `safety.py`, `KILL_SWITCH_ACTIVE`). No other checks run.

### 2. Circuit breaker state

If any circuit breaker is tripped and not yet past its reset window, reject with `breaker_tripped`. Details include which breaker and when it resets. The on-main `safety.py` path expresses this via the auto-activation of the kill switch when hardcoded daily-loss or drawdown thresholds are breached — see [`failsafes-and-kill-switches.md`](failsafes-and-kill-switches.md) for the three breaker classes.

### 3. Freshness

If the input data is stale past `GATE_MAX_DATA_AGE_SECONDS`, reject with `stale_data`. This catches gap windows during adapter reconnects.

### 4. Daily loss budget

If cumulative daily P&L is at or below `-MAX_DAILY_LOSS_PCT`, reject with `daily_loss_budget_spent`. The budget resets at 00:00 UTC.

### 5. Max open positions

If `len(open_positions) >= MAX_OPEN_POSITIONS`, reject with `max_positions`.

### 6. Regime alignment

Long candidate in HMM-bear? Short candidate in HMM-bull? Reject with `regime_misaligned`, unless the symbol is on the explicit override list (empty during validation).

### 7. Correlation cap

If the candidate's correlation to the current portfolio exceeds `CORRELATION_CAP`, reject with `correlation_exceeded`.

### 8. Heat check (pre-sizing)

Estimate the candidate's heat contribution at the hard-cap size (2%). If total heat after this notional would exceed `POSITION_HEAT_CAP_PCT` (80%), reject with `heat_cap_exceeded`. The check runs at the cap size — if the cap fits, a smaller sized trade will also fit. The on-main `GET /exposure` endpoint surfaces `is_over_exposed` and `total_exposure_pct` for operator-side verification (see [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Risk).

### 9. Leverage check

If the resulting position would require more than `MAX_LEVERAGE` (10×) for the exchange's margin calculation, reject with `leverage_exceeded`.

### 10. Entitlement check (billing-aware endpoints only)

If the request came via an entitled endpoint and the caller lacks entitlement, reject with `not_entitled`. This does not affect the engine's own internal calls.

### 11. Sizing call

If all above passed, call the Kelly sizer ([`position-sizing.md`](position-sizing.md), implementation at [`risk_management/kelly_position_sizer.py`](../../risk_management/kelly_position_sizer.py)). If the sizer returns a size below the minimum tradable quantity for the symbol, reject with `size_below_minimum`.

### 12. Slippage estimate

Run a pre-trade slippage estimate using current depth. If expected slippage consumes more than the configured fraction of expected edge, reject with `slippage_exceeds_edge`.

### 13. Accept

Return `accept` with the sized plan: symbol, side, size, stop, take-profit, stop-distance in ATR units, and the gate payload for journaling.

## Decision object

```json
{
  "outcome": "accept" | "rejected",
  "reason": "kill_switch_engaged" | "breaker_tripped" | "stale_data" |
            "daily_loss_budget_spent" | "max_positions" |
            "regime_misaligned" | "correlation_exceeded" |
            "heat_cap_exceeded" | "leverage_exceeded" |
            "not_entitled" | "size_below_minimum" |
            "slippage_exceeds_edge" | null,
  "details": { "...structured context..." },
  "plan": {
    "symbol": "BTCUSDT",
    "side": "long",
    "size_base": 0.001,
    "size_pct_equity": 1.4,
    "stop_price": 63800.0,
    "tp_price": 64700.0,
    "atr_stops": 1.5
  } | null
}
```

On `rejected`, `plan` is null. On `accept`, `reason` is null.

The `safety.py::SafetyGate.validate_order` shape is similar but uses a `RejectionReason` enum — see the source for the exact rejection-code mapping.

## What the gate explicitly does not do

- **It does not originate signals.** Scanner and scorer produce candidates; the gate only judges them.
- **It does not place orders.** The executor consumes the `accept` decision and handles the exchange calls.
- **It does not learn.** There are no adaptive thresholds in the gate itself. If a threshold needs to change, that is a PR with tests, not a runtime behavior.
- **It does not call the LLM.** The LLM is off the hot path by design (see the [decisions/](../decisions/) directory for the supporting ADR when it lands; the contract is "LLM advises operators between sessions, never gates a trade").

## Journaling

Every call writes one `gate_decision` event to the journal, with fields:

- `at` — UTC microsecond timestamp.
- `symbol`, `side`, `score`.
- `outcome` — accept / rejected.
- `reason` — for rejections.
- `details` — structured context.
- `plan` — for accepts.

The `GET /circuit-breaker` and `GET /exposure` endpoints surface the current gate-relevant state for the dashboard and operator (see [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Risk). The `GET /journal` and `GET /decisions` endpoints expose the historical decision stream — `GET /decisions` is the gate audit log specifically (see [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Decisions).

## Testing expectations

Every behavior change in the gate ships with tests that cover:

- The positive path (accept on clean inputs).
- Each rejection reason individually.
- Short-circuit ordering (earlier rejections pre-empt later ones).
- Journal entry shape.

**Current on-main coverage.** The submission-time safety gate is covered by [`tests/unit/paper_trading/test_safety.py`](../../tests/unit/paper_trading/test_safety.py) (~360 lines, 7 test classes). The dedicated 65-test invariant suite for the scan-time risk gate lives on branch `test/invariant-failure-modes`; its merge is tracked at [issue #44](https://github.com/3nz5789/CoinScopeAI/issues/44). Until that lands, the safety-gate coverage is the primary code-side proof of the gate contract — see [`../validation/p0-evidence-pack.md`](../validation/p0-evidence-pack.md) §0.1.

## Common review pitfalls

- **"Let's soften this rejection."** Usually wrong. Softening a rejection widens the worst case. If a reason is rejecting too aggressively, the fix is often in the input (scorer factor, freshness) rather than the gate.
- **"Let's add a new override flag."** Every override is future regret. If you need one, it goes behind a hard-coded allow-list, not a config flag.
- **"Let's reorder these checks for performance."** Order is semantic, not cosmetic. Kill switch before everything, breaker next, freshness third. Reordering changes the meaning of rejections.
- **"Let's compute the size before checking heat."** Heat check at the cap size is deliberate — it avoids a sizing round-trip when we already know the cap won't fit.

## Where the gate can fail loudly

- Missing regime artifact at boot. The gate cannot make a regime-alignment decision without both detectors; the engine fails to start.
- Missing breaker state storage. No in-memory default — if state is unrecoverable, the engine starts in breaker-tripped state and requires a manual reset.
- Missing journal writer. The gate refuses to produce any decision if it cannot journal; this is enforced by the shared journal-writer contract.

These are all by design. Silent defaults are not acceptable in this layer.

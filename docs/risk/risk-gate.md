# Risk Gate

**Status:** current
**Audience:** developers reviewing or modifying `coinscope_trading_engine/risk_gate.py`
**Related:** [`risk-framework.md`](risk-framework.md), [`position-sizing.md`](position-sizing.md), [`failsafes-and-kill-switches.md`](failsafes-and-kill-switches.md), [`../api/backend-endpoints.md`](../api/backend-endpoints.md)

The risk gate is the single entry point for the question "should this trade happen?" Every candidate that leaves the scanner passes through it. Nothing else decides whether to trade — not the scorer, not the executor, not the LLM, not the dashboard.

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

If the kill switch is engaged, reject immediately with reason `kill_switch_engaged`. No other checks run.

### 2. Circuit breaker state

If any circuit breaker is tripped and not yet past its reset window, reject with `breaker_tripped`. Details include which breaker and when it resets.

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

Estimate the candidate's heat contribution at the hard-cap size (2%). If total heat after this notional would exceed `POSITION_HEAT_CAP_PCT`, reject with `heat_cap_exceeded`. The check runs at the cap size — if the cap fits, a smaller sized trade will also fit.

### 9. Leverage check

If the resulting position would require more than `MAX_LEVERAGE` for the exchange's margin calculation, reject with `leverage_exceeded`.

### 10. Entitlement check (billing-aware endpoints only)

If the request came via an entitled endpoint and the caller lacks entitlement, reject with `not_entitled`. This does not affect the engine's own internal calls.

### 11. Sizing call

If all above passed, call the Kelly sizer ([`position-sizing.md`](position-sizing.md)). If the sizer returns a size below the minimum tradable quantity for the symbol, reject with `size_below_minimum`.

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

## What the gate explicitly does not do

- **It does not originate signals.** Scanner and scorer produce candidates; the gate only judges them.
- **It does not place orders.** The executor consumes the `accept` decision and handles the exchange calls.
- **It does not learn.** There are no adaptive thresholds in the gate itself. If a threshold needs to change, that is a PR with tests, not a runtime behavior.
- **It does not call the LLM.** See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).

## Journaling

Every call writes one `gate_decision` event to the journal, with fields:

- `at` — UTC microsecond timestamp.
- `symbol`, `side`, `score`.
- `outcome` — accept / rejected.
- `reason` — for rejections.
- `details` — structured context.
- `plan` — for accepts.

The `/risk-gate` API reads this back for the dashboard and operator.

## Testing expectations

Every behavior change in the gate ships with tests that cover:

- The positive path (accept on clean inputs).
- Each rejection reason individually.
- Short-circuit ordering (earlier rejections pre-empt later ones).
- Journal entry shape.

Tests live in `coinscope_trading_engine/tests/test_risk_gate*.py`.

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

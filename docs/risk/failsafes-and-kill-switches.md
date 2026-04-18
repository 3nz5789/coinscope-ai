# Failsafes and Kill Switches

**Status:** current
**Audience:** developers and operators
**Related:** [`risk-framework.md`](risk-framework.md), [`risk-gate.md`](risk-gate.md), [`../runbooks/daily-ops.md`](../runbooks/daily-ops.md), [`../runbooks/troubleshooting.md`](../runbooks/troubleshooting.md)

The engine has two classes of halt: automatic circuit breakers and a manual kill switch. This doc covers both — when each trips, how it resets, what the operator sees, and what the rules are around overriding.

## Circuit breakers

Circuit breakers trip automatically when a measurable risk boundary is crossed. They are not warnings. A tripped breaker blocks the executor outright.

### Breaker 1 — Daily loss

**Trip condition:** cumulative daily P&L ≤ `-MAX_DAILY_LOSS_PCT` of equity (default 5%).

**Reset:** at 00:00 UTC the next day, automatically.

**What the operator sees:** the `/risk-gate` endpoint reports `breaker.state = "tripped"` with reason `daily_loss`. New candidates are rejected with reason `breaker_tripped`. Telegram alert fires (if configured).

**What the operator should do:** nothing automatic. The breaker is doing its job. Read the journal for the day, identify the culprit trades, decide whether the strategy or a specific symbol is the problem. Wait for the UTC rollover.

### Breaker 2 — Max drawdown

**Trip condition:** peak-to-trough drawdown from the all-time equity high reaches `MAX_DRAWDOWN_PCT` (default 10%).

**Reset:** **does not auto-reset.** A max-drawdown trip is an incident, not a normal event. It requires operator acknowledgment via `POST /circuit-breaker/reset` with a written reason.

**What the operator should do:** open an incident. Review the 30-day journal. Decide whether to resume, scale down, or pause pending strategy review. Reset only after a deliberate decision, not by reflex.

### Breaker 3 — Consecutive losses

**Trip condition:** `CONSECUTIVE_LOSSES_BREAKER` losing closed trades in a row (default 4). "Closed" means either stopped out, taken profit, or manually closed.

**Reset:** after `CIRCUIT_BREAKER_RESET_HOURS` (default 24 hours), automatically.

**Why it exists:** consecutive losses often indicate a regime shift the detectors haven't caught yet. Pausing for a day gives the detectors time to refresh and the market time to clarify.

### Breaker state machine

```
            ┌──────────┐
            │    ok    │
            └────┬─────┘
                 │ trip condition met
                 ▼
            ┌──────────┐
            │ tripped  │───── new entries: rejected
            └────┬─────┘       working orders: retained
                 │               existing positions: retained
                 │ reset window elapsed OR operator reset
                 ▼
            ┌──────────┐
            │    ok    │
            └──────────┘
```

A tripped breaker does not unwind positions. It does not cancel working stops or take-profits — those continue to protect existing positions. It only stops new entries.

## Kill switch

The kill switch is a single Boolean the operator toggles manually. It is not triggered by any automatic condition.

**Trip condition:** operator calls `POST /kill-switch` with `engage: true`.

**Effect:**

- The gate short-circuits every candidate with reason `kill_switch_engaged`.
- The executor cancels working orders.
- Existing positions remain open, with their stops and take-profits intact. Unwinding is a separate operator decision.

**Reset:** operator calls `POST /kill-switch` with `engage: false`. A reason string is recorded in the journal.

**When to engage:**

- Before a maintenance window or deploy.
- During a market event you don't want the engine trading through (major protocol upgrade, exchange outage rumors).
- When you feel uncertain. Uncertainty is a valid reason.

## Journaling and observability

Every breaker trip, breaker reset, and kill-switch toggle writes a journal event. The `/journal` endpoint surfaces them with `event_type` of `breaker_trip` or `kill_switch`.

Prometheus metrics:

- `engine_circuit_breaker_trips_total{breaker="daily_loss|max_drawdown|consecutive_losses"}`
- `engine_circuit_breaker_state{breaker="..."}` — 0 for ok, 1 for tripped.
- `engine_kill_switch_engaged` — 0 or 1.

Telegram alerts (when configured) fire on trips and on kill-switch toggles. See [`../ops/telegram-alerts.md`](../ops/telegram-alerts.md).

## Hard rules for operators

1. **Never override a max-drawdown trip without reading the journal.** The journal tells you whether the trip was a single bad trade or a cumulative pattern. These demand different responses.
2. **Do not reset a breaker "just to see if it works."** Resetting resumes trading. If you want to verify the reset path, do it with the kill switch engaged.
3. **Never bypass the breaker by restarting the engine.** Breaker state is persisted. A restart does not clear it.
4. **Do not disable a breaker in config.** Breakers are features, not annoyances. If a breaker is firing too often, the symptom is the strategy, not the breaker.

## Hard rules for developers

1. **Every breaker trip writes a journal entry before taking effect.** Non-negotiable.
2. **Breaker state is persisted.** In-memory-only state would be lost on restart, which is worse than any reset policy.
3. **Kill-switch evaluation is always first in the gate.** This ordering is semantic. Moving it breaks the "immediate halt" property.
4. **No developer adds an "admin override" path.** The mechanism for resuming is the same for every operator: the reset endpoints. Overrides are how this class of system gets in trouble.

## Where to look when a breaker trips unexpectedly

1. `GET /journal?event_type=gate_decision&limit=200` — the last 200 gate decisions. Look for a run of rejections or a sudden regime flip.
2. `GET /journal?event_type=pnl_update&limit=50` — the last 50 P&L updates. Identify which trades drove the loss.
3. `GET /risk-gate` — the current breaker state and reason.
4. `/metrics` scrape — the counter should have incremented exactly once at the trip.
5. [`../runbooks/troubleshooting.md`](../runbooks/troubleshooting.md) — known failure modes.

## Design rationale

These failsafes are redundant by design. An operator can engage the kill switch; a breaker can trip automatically; the gate can reject a specific candidate. Any one of them is sufficient to prevent the worst case; the combination is robust to a failure in any single layer.

We accept the operational cost — occasional missed upside during a trip — in exchange for the worst-case bound. Over the long horizon, avoiding the left tail is what compounds.

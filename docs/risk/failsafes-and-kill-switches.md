# Failsafes and Kill Switches

**Status:** current — P0 validation phase
**Audience:** developers and operators
**Related:** [`risk-framework.md`](risk-framework.md) · [`risk-gate.md`](risk-gate.md) · [`position-sizing.md`](position-sizing.md) · [`../runbooks/operator-workflow.md`](../runbooks/operator-workflow.md) · [`../api/engine-api-contract.md`](../api/engine-api-contract.md) · [`../monitoring/slo-alerts-dashboard.md`](../monitoring/slo-alerts-dashboard.md)

> **Operator routing:** if you arrived here because a breaker tripped or you're deciding whether to engage the kill switch, the procedure that wraps this doc is [`operator-workflow.md`](../runbooks/operator-workflow.md) §Steps 2 and 8. This file is the *mechanics* (what each breaker does); the workflow is the *procedure* (what you do, in what order). Use both.

The engine has two classes of halt: automatic circuit breakers and a manual kill switch. This doc covers both — when each trips, how it resets, what the operator sees, and what the rules are around overriding.

The on-main implementation lives in [`services/paper_trading/safety.py`](../../services/paper_trading/safety.py) (the `KillSwitch` and `SafetyGate` classes). Code-side proof: [`tests/unit/paper_trading/test_safety.py`](../../tests/unit/paper_trading/test_safety.py) (7 test classes covering activation, deactivation, persistence, and the gate's rejection paths).

## Circuit breakers

Circuit breakers trip automatically when a measurable risk boundary is crossed. They are not warnings. A tripped breaker blocks the executor outright.

### Breaker 1 — Daily loss

**Trip condition:** cumulative daily P&L ≤ `-MAX_DAILY_LOSS_PCT` of equity (default 5%).

**Reset:** at 00:00 UTC the next day, automatically.

**What the operator sees:** `GET /circuit-breaker` reports `state = "OPEN"`. `GET /exposure` reports `daily_loss_pct` at or below the threshold. New candidates are rejected with reason `breaker_tripped` (or `DAILY_LOSS_LIMIT` in the `safety.py` rejection-reason enum). Telegram alert fires (per [`../monitoring/slo-alerts-dashboard.md`](../monitoring/slo-alerts-dashboard.md)).

**What the operator should do:** nothing automatic. The breaker is doing its job. Read the journal (`GET /journal?event_type=breaker_trip`) for the day, identify the culprit trades, decide whether the strategy or a specific symbol is the problem. Wait for the UTC rollover.

### Breaker 2 — Max drawdown

**Trip condition:** peak-to-trough drawdown from the all-time equity high reaches `MAX_DRAWDOWN_PCT` (default 10%).

**Reset:** **does not auto-reset.** A max-drawdown trip is an incident, not a normal event. It requires operator acknowledgment via `POST /circuit-breaker/reset` (the endpoint takes no parameters — see [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Risk for the request shape). The reset reason is operator-log practice: write it in your session log before calling the endpoint so the journal and the log together reconstruct the decision later.

**What the operator should do:** open an incident. Review the 30-day journal. Decide whether to resume, scale down, or pause pending strategy review. Reset only after a deliberate decision, not by reflex.

### Breaker 3 — Consecutive losses

**Trip condition:** `CONSECUTIVE_LOSSES_BREAKER` losing closed trades in a row (default 4). "Closed" means either stopped out, taken profit, or manually closed.

**Reset:** after `CIRCUIT_BREAKER_RESET_HOURS` (default 24 hours), automatically.

**Why it exists:** consecutive losses often indicate a regime shift the detectors haven't caught yet. Pausing for a day gives the detectors time to refresh and the market time to clarify.

### Breaker state machine

```
            ┌──────────┐
            │  CLOSED  │
            └────┬─────┘
                 │ trip condition met
                 ▼
            ┌──────────┐
            │   OPEN   │───── new entries: rejected
            └────┬─────┘       working orders: cancelled
                 │               existing positions: retained (stops/TPs intact)
                 │ reset window elapsed OR POST /circuit-breaker/reset
                 ▼
            ┌──────────┐
            │  CLOSED  │
            └──────────┘
```

State enum (per [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Risk `GET /circuit-breaker`): `CLOSED` (trading allowed) · `OPEN` (halted) · `COOLDOWN`.

A tripped breaker does cancel **working orders and brackets** (the `POST /circuit-breaker/trip` response includes a `cancellations` map listing what was cancelled), but it does not unwind **existing positions** — those continue under their submitted stops and take-profits.

## Kill switch

The kill switch is a manual halt toggled by the operator. It is not triggered by any automatic condition — though the safety-gate code at [`services/paper_trading/safety.py`](../../services/paper_trading/safety.py) does auto-activate the kill switch when hardcoded daily-loss or max-drawdown thresholds are breached (defense in depth).

### Two activation paths

**API path** — for use when the engine is reachable:
```bash
curl -X POST https://api.coinscope.ai/circuit-breaker/trip \
  -H "Content-Type: application/json" \
  -d '{"reason": "Operator kill switch — <describe the reason>"}'
```
The reason string is required by the API contract and lands in the journal. See [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Risk `POST /circuit-breaker/trip` for the response shape (which includes the `cancellations` map showing every working order and bracket that was cancelled).

**CLI path** — file-based, works even when the engine API is down:
```bash
python -m services.paper_trading.kill --reason "<reason>"
```
The CLI prompts for a `KILL`-string confirmation before writing the persistent flag at `/tmp/coinscopeai_kill_switch.flag`. The flag is read on every safety-gate evaluation; an existing flag persists across engine restarts.

### Effect

- The gate short-circuits every candidate with reason `kill_switch_engaged` / `KILL_SWITCH_ACTIVE`.
- The executor cancels working orders and brackets (API path) or the next engine evaluation refuses new submissions (CLI path).
- Existing positions remain open, with their stops and take-profits intact. Unwinding is a separate operator decision.

### Reset

**API path:** `POST /circuit-breaker/reset`. **Read `/journal` and verify a real breach caused the trip before calling this** — per the contract invariant noted in [`../api/engine-api-contract.md`](../api/engine-api-contract.md) §Risk.

**CLI path:**
```bash
python -m services.paper_trading.kill --deactivate
```
The CLI prompts for both a reason and a `CONFIRM` string before removing the persistent flag. The reason is passed to `KillSwitch.deactivate(reason: str)` — the parameter is required (positional, non-empty). A programmatic caller that omits the reason raises `TypeError`; an empty or whitespace-only reason raises `ValueError`. The reason is logged at WARN level for audit reconstruction.

The required-argument shape exists deliberately. A future refactor that introduces a programmatic `ks.deactivate()` call fails at runtime instead of silently disabling the safety layer — the deactivate-path contract is now enforced by the signature and the test harness, not just by the CLI prompt.

### When to engage

- Before a maintenance window or deploy.
- During a market event you don't want the engine trading through (major protocol upgrade, exchange outage rumors).
- When you feel uncertain. Uncertainty is a valid reason.

## Journaling and observability

Every breaker trip, breaker reset, and kill-switch toggle writes a journal event. The `GET /journal` endpoint surfaces them with `event_type` of `breaker_trip` or `kill_switch`. The `GET /decisions` endpoint exposes the gate's full decision stream.

Prometheus metrics (see [`../monitoring/slo-alerts-dashboard.md`](../monitoring/slo-alerts-dashboard.md) for the full SLO mapping):

- `engine_circuit_breaker_trips_total{breaker="daily_loss|max_drawdown|consecutive_losses"}`
- `engine_circuit_breaker_state{breaker="..."}` — 0 for `CLOSED`, 1 for `OPEN`, 0.5 for `COOLDOWN`.
- `engine_kill_switch_engaged` — 0 or 1.

Telegram alerts fire on trips and on kill-switch toggles. See [`../monitoring/slo-alerts-dashboard.md`](../monitoring/slo-alerts-dashboard.md) for the 12 alert rules and routing.

## Hard rules for operators

1. **Never override a max-drawdown trip without reading the journal.** The journal tells you whether the trip was a single bad trade or a cumulative pattern. These demand different responses.
2. **Do not reset a breaker "just to see if it works."** Resetting resumes trading. If you want to verify the reset path, do it in a staging environment, not production.
3. **Never bypass the breaker by restarting the engine.** Breaker state is persisted. The kill-switch flag at `/tmp/coinscopeai_kill_switch.flag` survives restarts; the breaker state in the engine likewise persists.
4. **Do not disable a breaker in config.** Breakers are features, not annoyances. If a breaker is firing too often, the symptom is the strategy, not the breaker.

## Hard rules for developers

1. **Every breaker trip writes a journal entry before taking effect.** Non-negotiable.
2. **Breaker state is persisted.** In-memory-only state would be lost on restart, which is worse than any reset policy. The kill-switch flag is intentionally file-based for this reason.
3. **Kill-switch evaluation is always first in the gate.** This ordering is semantic. Moving it breaks the "immediate halt" property. The on-main implementation enforces this at [`services/paper_trading/safety.py::SafetyGate._validate_locked`](../../services/paper_trading/safety.py) Layer 1.
4. **No developer adds an "admin override" path.** The mechanism for resuming is the same for every operator: the reset endpoints / CLI. Overrides are how this class of system gets in trouble.

## Where to look when a breaker trips unexpectedly

1. `GET /journal?event_type=breaker_trip&limit=10` — recent trips with reasons.
2. `GET /decisions?limit=200` — the last 200 gate decisions. Look for a run of rejections or a sudden regime flip.
3. `GET /journal?event_type=pnl_update&limit=50` — the last 50 P&L updates. Identify which trades drove the loss.
4. `GET /circuit-breaker` — the current breaker state.
5. `GET /exposure` — current daily_pnl_pct, total_exposure_pct, and is_over_exposed.
6. `/metrics` scrape — the trip counter should have incremented exactly once at the trip.
7. [`../runbooks/operator-workflow.md`](../runbooks/operator-workflow.md) §Step 2 and §Step 8 — operator-side procedure.
8. Drive workspace `04 — Development/docs/runbooks/operator-lifecycle.md` Phase 4 (event response) and Phase 7 (incident) — fuller incident response procedure until ported.

## Design rationale

These failsafes are redundant by design. An operator can engage the kill switch; a breaker can trip automatically; the gate can reject a specific candidate; the safety gate at submission time re-checks every limit. Any one of them is sufficient to prevent the worst case; the combination is robust to a failure in any single layer.

We accept the operational cost — occasional missed upside during a trip — in exchange for the worst-case bound. Over the long horizon, avoiding the left tail is what compounds.

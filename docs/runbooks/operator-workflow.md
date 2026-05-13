# Operator Workflow — Trading Session Lifecycle

**Status:** active — P0 validation phase (Binance USDT-M Testnet only)
**Audience:** the operator on shift (currently solo founder during P0; expands at P2)
**Engine API base:** `https://api.coinscope.ai` (prod) · `http://localhost:8001` (local)
**Companion doc:** the wider operator role — onboarding, weekly review, incident response — lives in the Google Drive workspace at `04 — Development/docs/runbooks/operator-lifecycle.md`. This file is its **session-level** counterpart: what an operator does during one trading day, in order.

> **Scope.** Nine steps. Steps 1–2 run together at session start. Steps 3–6 cycle as opportunities arise. Step 7 fires automatically per trade — the operator verifies. Step 8 is continuous. Step 9 happens once at session close.

---

## Pre-conditions

Before starting, all of these must be true:

- Engine is running, CI on `main` is green ([latest release](https://github.com/3nz5789/CoinScopeAI/releases))
- `TESTNET_MODE=true` enforced at the engine — verifiable via Step 1 (see [`docs/api/engine-api-contract.md`](../api/engine-api-contract.md) §Testnet guard)
- Telegram bot `@ScoopyAI_bot` is reachable
- Operator log entry is ready for today's date

Any session run with `TESTNET_MODE=false` is **not a session** — it is a Phase 7 incident.

---

## Why every step is non-negotiable

[`docs/BUG_FIXES_COMPREHENSIVE.md`](../BUG_FIXES_COMPREHENSIVE.md) **BUG-10** is the canonical example. From the bug record:

> `master_orchestrator.py` line 104: `self.mtf_filter` and `self.risk_gate` initialized but never used in `scan_pair()` — every trade bypassed risk controls entirely.

The code fix is in place ([`engine/core/master_orchestrator.py`](../../engine/core/master_orchestrator.py)). The **workflow** is what catches it when code regresses — specifically Step 2 (risk gate check) and Step 4 (signal review with MTF). Skipping either step on a live session reopens the BUG-10 blind spot at the operator layer. The pattern is: code defense + workflow defense, neither alone is sufficient.

---

## Step 1 — Environment check

**Cadence:** Once at session start. Repeat on any infrastructure event (deploy, network blip, container restart).

### What to run

```bash
curl -s https://api.coinscope.ai/health | jq
curl -s https://api.coinscope.ai/config | jq
```

Response shapes: see [`docs/api/engine-api-contract.md`](../api/engine-api-contract.md) §System — `GET /health` (returns `status`, `version`, `uptime_seconds`, `testnet_mode`) and `GET /config` (returns the active thresholds and feature flags).

### What to do with the response

| Outcome | Action |
|---|---|
| `/health` returns 200, `testnet_mode: true`, `version` matches expected baseline | Proceed to Step 2 |
| `testnet_mode: false` | **Halt.** Engine is in an unsafe configuration; route to incident (Phase 7 in the Drive operator-lifecycle.md) |
| `/health` returns non-200 or fails to respond | Restart the engine via `docker compose restart`; if not recoverable, halt |
| `/config` threshold values don't match PCC v2 §8 (max_leverage=10, max_open_positions=5, max_drawdown_pct=10, max_daily_loss_pct=5, position_heat_cap_pct=80) | Halt. Threshold drift is a [`scripts/risk_threshold_guardrail.py`](../../scripts/risk_threshold_guardrail.py) finding — run it before resuming |
| Version drifted from expected | Cross-check `git log --tags` on `main` and the deployment record; an unauthorized deploy is an incident |

---

## Step 2 — Risk gate check

**Cadence:** Once at session start. Re-run before any discretionary intervention (e.g., manual size override consideration).

### What to run

```bash
curl -s https://api.coinscope.ai/circuit-breaker | jq
curl -s https://api.coinscope.ai/exposure | jq
```

Shapes: [`engine-api-contract.md`](../api/engine-api-contract.md) §Risk — `GET /circuit-breaker` returns `state` (one of `CLOSED` / `OPEN` / `COOLDOWN`), `trip_count`, `last_trip`, and the active thresholds. `GET /exposure` returns `balance`, `position_count`, `total_exposure_pct`, `daily_pnl`, `daily_loss_pct`, `is_over_exposed`.

### What to do with the response

| Field | Bad state | Action |
|---|---|---|
| `state` | `OPEN` | **Halt.** Read `/journal?event_type=breaker_trip` for cause. **Do not reset until you can explain why it tripped** — see `POST /circuit-breaker/reset` invariant in the contract. If you can't explain, route to incident. |
| `state` | `COOLDOWN` | Wait. Cooldown auto-expires; do not force-reset. |
| `daily_loss_pct` | < `-0.035` (3.5% loss, warning band before 5% trip) | Reduce position size aggressively; one more loss likely trips. |
| `total_exposure_pct` | > `65` (warning band before 80% cap) | No new entries until existing positions close. `is_over_exposed: true` is the hard line. |
| `is_over_exposed` | `true` | Halt new entries. Address the over-exposure before resuming. |

### Why this is non-negotiable

BUG-10's exact failure mode was: this check existed in code, but `scan_pair()` didn't call it. **The workflow is the operator-side defense.** Do not skip Step 2 even when everything else looks fine — that's precisely when blind spots compound.

---

## Step 3 — Market scan

**Cadence:** On demand. The scanner runs autonomously on a fixed cadence; manual scans on top happen when an operator wants a fresh read or is evaluating a specific symbol.

### What to run

```bash
# On-demand scan (no order placement)
curl -s -X POST https://api.coinscope.ai/scan \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT"], "min_score": 8.0}' | jq

# Read the autonomous scanner's recent signals
curl -s "https://api.coinscope.ai/signals?limit=20&min_score=8.0" | jq
```

Shapes: [`engine-api-contract.md`](../api/engine-api-contract.md) §Signals.

### What to do with the response

| Outcome | Action |
|---|---|
| No signals at the alert threshold (≥ 8.0 score) | Nothing to act on. Wait for the next autonomous scan |
| Signals present, `mtf_confirmed: true` | Go to Step 4 to review each before sizing |
| Signal with `mtf_confirmed: false` | Skip — multi-timeframe filter explicitly disqualified |
| Scan returns 423 (Locked) | Breaker tripped between Step 2 and now. Re-run Step 2 |
| Scan returns 403 | `TESTNET_MODE=false` — Step 1 condition violated mid-session. Halt |

The alert score threshold of **≥ 8.0** is canonical (release notes, [`coinscopeai-ops-secrets`](skill) §1).

---

## Step 4 — Signal review

**Cadence:** For each candidate from Step 3 before any sizing.

### Four dimensions to check

| Dimension | Source | Acceptable range |
|---|---|---|
| Regime label | `GET /regime?symbol={SYMBOL}` — see [`engine-api-contract.md`](../api/engine-api-contract.md) §Intelligence | `Trending` or `Mean-Reverting` are clean. `Volatile` and `Quiet` apply a Kelly multiplier (0.3× per release notes) but do not auto-disqualify |
| Multi-timeframe confirmation | `mtf_confirmed` field in scan output | Must be `true` |
| Funding rate | Scan payload | If `\|funding_rate_pct\| > 0.05%` per 8h, the position is paying carry that may exceed the signal's edge |
| Open-interest delta | Scan payload | OI delta > +5% in 1h on a long entry is good confluence. Sharp OI decline indicates the move is dying |

### What to do

| Outcome | Action |
|---|---|
| All four check out | Proceed to Step 5 |
| Regime is `Volatile` / `Quiet` | Proceed with reduced size (the position-size endpoint will apply the multiplier; do not override) |
| `mtf_confirmed: false` | Skip the signal |
| Funding rate strongly against | Skip, or use shortest expected hold time only |
| OI dying on a long (or rising on a short) | Use tighter trailing stop and smaller size, or skip |

### Why this is non-negotiable

Same BUG-10 reasoning. The MTF filter and risk gate are now applied in code at scan time; Step 4 is the operator-side sanity layer. The four dimensions each cover a real microstructure factor for USDT-perpetuals — funding rate and OI behavior are the futures-specific items vanilla TA misses. See the `futures-market-researcher` skill for the underlying mechanics.

---

## Step 5 — Position sizing

**Cadence:** Per signal that survived Step 4.

### What to run

```bash
curl -s "https://api.coinscope.ai/position-size?symbol=BTCUSDT&entry=67234.5&stop_loss=66180.0&score=9.2&regime=Trending" | jq
```

Shape: [`engine-api-contract.md`](../api/engine-api-contract.md) §Risk — `GET /position-size`.

### What to do with the response

| Outcome | Action |
|---|---|
| `approved: true`, post-trade `total_exposure_pct < 80` | Proceed to Step 6 with the returned `size_quantity` and `leverage` |
| `approved: false` | Read `rejection_reason`. **Trust the sizer** — reasons map to PCC v2 §8 thresholds, enforced by [`risk_management/kelly_position_sizer.py`](../../risk_management/kelly_position_sizer.py) and re-checked at the safety gate ([`services/paper_trading/safety.py`](../../services/paper_trading/safety.py)). Do not override. If you believe a rejection is wrong, that's a Phase 7 finding |
| Post-trade exposure would breach 80% cap | Wait for an existing position to close |

The safety gate ([`services/paper_trading/safety.py`](../../services/paper_trading/safety.py)) is the last-line check: even if the sizer somehow returned an invalid size, the gate rejects it at submission time. Coverage: [`tests/unit/paper_trading/test_safety.py`](../../tests/unit/paper_trading/test_safety.py).

---

## Step 6 — Trade execution

**Cadence:** Per approved signal from Step 5.

### Constraints (P0, non-negotiable)

- `TESTNET_MODE=true` enforced at the engine (Step 1 confirmed). Engine returns 403 if `false`
- Stop-loss and take-profit must be set on entry — use the bracket endpoint, no naked entries
- No size override beyond what Step 5 returned

### What to run

```bash
curl -s -X POST https://api.coinscope.ai/orders/bracket \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.00265,
    "leverage": 3,
    "stop_loss": 66180.0,
    "take_profit": 69400.0
  }' | jq
```

Shape: [`engine-api-contract.md`](../api/engine-api-contract.md) §Orders — `POST /orders/bracket`. The autonomous scan path can also place orders directly when the scan-loop's `place_order` flag is enabled; for operator-initiated entries, use the bracket endpoint explicitly so the SL/TP are visible in the request.

### What to do with the response

| Outcome | Action |
|---|---|
| Order accepted, status `NEW` or `FILLED` | Proceed to Step 7 |
| Order rejected with Binance error code | Read the code — usually a notional/precision issue. Don't retry without diagnosing |
| 403 | `TESTNET_MODE=false`. Halt and incident |
| 423 | Breaker tripped between Step 5 and Step 6. Re-run Step 2 |

---

## Step 7 — Journal

**Cadence:** Automatic per trade. Operator verifies both stores recorded the event.

### What to verify

After each fill (entry or exit):

```bash
curl -s "https://api.coinscope.ai/journal?event_type=trade_open&limit=1" | jq
```

Shape: [`engine-api-contract.md`](../api/engine-api-contract.md) §Journal. Plus check the **Notion trade journal** at canonical DB `43a542f4-b58d-4b1a-8979-043e72e9a6dd` (per `coinscopeai-ops-secrets` skill §1) — the row should appear within seconds.

### What to do with the response

| Outcome | Action |
|---|---|
| Both stores have the event with matching fields | Done |
| Engine journal has it, Notion doesn't | Notion sync issue (usually rate limit or token). Note in operator log; investigate post-session |
| Engine journal doesn't have it but the fill is real | **This is a Phase 7 incident.** The engine took an action without journaling — every downstream depends on the journal being authoritative |

---

## Step 8 — Monitoring

**Cadence:** Continuous. At minimum, an explicit gate check every hour during an active session.

### Hourly check

```bash
curl -s https://api.coinscope.ai/circuit-breaker | jq '.state, .trip_count'
curl -s https://api.coinscope.ai/exposure | jq '.daily_loss_pct, .total_exposure_pct, .is_over_exposed'
```

### Passive monitoring surfaces

- **Telegram `@ScoopyAI_bot`** — all score ≥ 8.0 signal alerts, all breaker trips, all kill-switch toggles. Telegram silence is not "all clear" — cross-check via the hourly check above
- **Dashboard at `app.coinscope.ai`** — same data, visual
- **Engine logs** — for unexpected exception traces

### Alert routing

Per [`docs/monitoring/slo-alerts-dashboard.md`](../monitoring/slo-alerts-dashboard.md):

| Trigger | Severity | Response |
|---|---|---|
| Circuit breaker trip | 🔴 CRITICAL | Immediate; incident response, do not auto-resume |
| Daily loss limit (5%) | 🔴 CRITICAL | Immediate; halt new entries until UTC rollover |
| Max drawdown (10%) | 🔴 CRITICAL | Immediate; manual reset only after journal review |
| Daily loss warning (3.5%) | 🟡 WARN | Reduce size; tighten stops |
| Consecutive losses near trip | 🟡 WARN | Halt new entries |
| WebSocket reconnect storm | 🟡 WARN | If repeated, restart WS subprocess |
| Daily P&L digest (21:00 UTC) | ℹ️ INFO | Read; archive into operator log |

### Manual kill switch

If you need to halt all trading immediately and don't want to wait for a breaker to trip:

```bash
# API path — halts trading and cancels working orders + brackets
curl -s -X POST https://api.coinscope.ai/circuit-breaker/trip \
  -H "Content-Type: application/json" \
  -d '{"reason": "Operator kill switch — <write the reason here>"}' | jq

# CLI path (file-based, even if API is down)
python -m services.paper_trading.kill --reason "<reason>"
```

The CLI guards deactivation behind a `CONFIRM`-string prompt; the API equivalent uses `POST /circuit-breaker/reset` and should only be called after journal review. See [issue #47](https://github.com/3nz5789/CoinScopeAI/issues/47) for the in-flight hardening of the deactivate path against programmatic bypass.

---

## Step 9 — Session close

**Cadence:** Once at end of session.

### What to run

```bash
# Performance summary
curl -s https://api.coinscope.ai/performance | jq

# Threshold guardrail — confirms no drift from PCC v2 §8 happened during the session
python3 scripts/risk_threshold_guardrail.py

# Paper-trading health (if running the paper service)
python3 scripts/health_check_paper_trading.py
```

Shape: [`engine-api-contract.md`](../api/engine-api-contract.md) §Journal — `GET /performance`.

### What goes in the operator log

For the day:

- **Trades opened / closed:** counts, symbols, win/loss outcome
- **Breaker trips:** zero is normal. Any non-zero is a Phase 7 follow-up regardless of whether it auto-reset
- **Kill switch toggles:** zero is normal. Any toggle must have a written reason captured at trip time
- **Performance vs. yesterday:** PnL %, drawdown %, consecutive-losses status
- **Anomalies:** anything that didn't match expectations across Steps 1–8

The operator log is the input to the weekly review (Phase 6 in the Drive operator-lifecycle.md) and to any future RCA.

### What to do after

| Outcome | Action |
|---|---|
| Clean session — no breakers, no kill toggles, performance in expected range | Close out. Commit any session-scoped state changes |
| Breaker tripped during session | Phase 7 incident regardless of whether it auto-reset — RCA within 48h |
| Performance unusually outside expected range | Note in operator log with an explicit hypothesis. Recurring pattern → file an investigation issue against Milestone #1 |

---

## Cross-references

| Topic | Where it lives |
|---|---|
| First-day operator onboarding | Drive: `04 — Development/docs/runbooks/operator-lifecycle.md` Phase 1 |
| Incident response & escalation | Drive: same doc, Phase 7 — until a repo-side `docs/runbooks/incident-response.md` is written |
| Weekly review & release decisions | Drive: same doc, Phase 6 |
| What proof exists for each safety property | [`docs/validation/p0-evidence-pack.md`](../validation/p0-evidence-pack.md) §0 |
| API contract (every endpoint shape) | [`docs/api/engine-api-contract.md`](../api/engine-api-contract.md) |
| SLOs and alert rules | [`docs/monitoring/slo-alerts-dashboard.md`](../monitoring/slo-alerts-dashboard.md) |
| Pre-flight bug record (including BUG-10) | [`docs/BUG_FIXES_COMPREHENSIVE.md`](../BUG_FIXES_COMPREHENSIVE.md) |
| Risk thresholds locked at PCC v2 §8 | Will live at `docs/risk/risk-framework.md` once [issue #45](https://github.com/3nz5789/CoinScopeAI/issues/45) merges; for now, see the Drive workspace `05 — Risk Management/risk-framework.md` |

---

## Open items affecting this workflow

Tracked in [Milestone #1 — P0 Graduation](https://github.com/3nz5789/CoinScopeAI/milestone/1):

- [#34](https://github.com/3nz5789/CoinScopeAI/issues/34) duplicate-position rejection — affects Step 5 (a same-symbol same-side entry currently passes safety gate)
- [#39](https://github.com/3nz5789/CoinScopeAI/issues/39) alert-path smoke test — affects Step 8 (the alert routing claims are unproven end-to-end on Telegram + dashboard until the smoke test runs)
- [#40](https://github.com/3nz5789/CoinScopeAI/issues/40) coverage measurement — affects how strongly Step 2 / Step 6 trust the safety gate's test coverage
- [#41](https://github.com/3nz5789/CoinScopeAI/issues/41) BUG-1 through BUG-16 regression audit — affects how confident Step 4 can be that historical bugs won't regress
- [#44](https://github.com/3nz5789/CoinScopeAI/issues/44) invariant suite merge — when merged, Step 2's `/circuit-breaker` interpretation is proven at the dedicated invariant layer
- [#45](https://github.com/3nz5789/CoinScopeAI/issues/45) docs/risk/ port — when merged, Step 2's "PCC v2 §8 thresholds" link becomes a direct repo reference
- [#46](https://github.com/3nz5789/CoinScopeAI/issues/46) walk-forward validator — when merged, Step 4's signal-quality basis is reproducible from this repo
- [#47](https://github.com/3nz5789/CoinScopeAI/issues/47) kill-switch deactivate hardening — when merged, Step 2's interpretation of `kill_switch_active=false` strengthens

Each step works against current on-main reality. For what is and isn't yet proven, cross-check [`docs/validation/p0-evidence-pack.md`](../validation/p0-evidence-pack.md) §0.2.

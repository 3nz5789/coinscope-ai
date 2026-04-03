# Risk Gate Skill — CoinScopeAI
**Skill ID:** `coinscope.risk_gate`
**Version:** 1.0.0
**Platform:** Manus
**Category:** Risk Management

---

## Overview

Validates a proposed trade against all active circuit breakers before any position is sized or logged. This is a mandatory checkpoint in the full automation workflow — no trade recommendation proceeds without a Risk Gate clearance.

---

## Trigger Phrases

- "Can I take this trade?"
- "Check risk gate"
- "Is it safe to enter?"
- "Validate this trade"
- "Am I within risk limits?"
- "Check my limits"
- "Is the gate open?"
- "Risk check for [pair]"

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `symbol` | string | Yes | Pair being validated |
| `direction` | string | Yes | LONG or SHORT |
| `position_size_usdt` | float | Yes | Proposed position size |
| `risk_amount_usdt` | float | Yes | Dollar amount at risk |

---

## Execution Steps

### Step 1 — Call Validate Endpoint
```
POST http://localhost:8001/validate
Body: {
  "symbol": "{symbol}",
  "direction": "{direction}",
  "position_size_usdt": {size},
  "risk_amount_usdt": {risk}
}
```

Expected response:
```json
{
  "approved": true,
  "checks": {
    "daily_loss": { "status": "PASS", "current": 0.012, "limit": 0.03 },
    "consecutive_losses": { "status": "PASS", "current": 1, "limit": 5 },
    "drawdown": { "status": "PASS", "current": 0.021, "limit": 0.10 },
    "open_positions": { "status": "PASS", "current": 1, "limit": 3 },
    "position_size": { "status": "PASS", "current": 0.045, "limit": 0.03 }
  },
  "blocked_by": null
}
```

### Step 2 — Format Output

**When APPROVED:**
```
✅ RISK GATE — CLEAR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Daily Loss:          1.2% / 3.0% limit   ✅
Consecutive Losses:  1 / 5 limit         ✅
Total Drawdown:      2.1% / 10.0% limit  ✅
Open Positions:      1 / 3 limit         ✅
Per-Trade Risk:      0.45% / 2.0% limit  ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
→ Proceed with BTCUSDT LONG $450 at 5×
```

**When BLOCKED:**
```
🚫 RISK GATE — BLOCKED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Daily Loss: 3.1% — LIMIT REACHED (3.0%)
✅ Consecutive Losses: 2 / 5
✅ Drawdown: 3.1% / 10.0%
✅ Open Positions: 1 / 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
No new trades today. Limit resets at midnight UTC.
To change the limit: update MAX_DAILY_LOSS_PCT in .env
```

---

## Circuit Breaker Definitions

| Breaker | Env Variable | Default | Reset |
|---------|-------------|---------|-------|
| Daily Loss | `MAX_DAILY_LOSS_PCT` | 3% | Midnight UTC |
| Consecutive Losses | `MAX_CONSECUTIVE_LOSSES` | 5 | Manual / after win |
| Total Drawdown | `MAX_DRAWDOWN_PCT` | 10% | Manual reset |
| Open Positions | `MAX_OPEN_POSITIONS` | 3 | When trades close |
| Per-Trade Risk | Hard-coded | 2% of capital | Per trade |

---

## Behaviour Rules

- **Always run Risk Gate before Position Sizer output is final** — call validate in background automatically
- If BLOCKED → do not show position size, do not offer to log trade
- If APPROVED → display check table and proceed with sizing output
- Never suggest ways to override or bypass the Risk Gate

---

## Chaining

- Risk Gate runs automatically as part of the full automation workflow
- If APPROVED → chain to **Trade Journal** to log the entry
- If BLOCKED → stop workflow, explain which breaker, tell trader when it resets

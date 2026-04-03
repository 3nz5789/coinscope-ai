# Position Sizer Skill — CoinScopeAI
**Skill ID:** `coinscope.position_sizer`
**Version:** 1.0.0
**Platform:** Manus
**Category:** Risk Management

---

## Overview

Calculates the recommended position size for a trade using the fractional Kelly Criterion. Takes the signal score, available capital, leverage, and regime as inputs — returns the exact USDT amount, number of contracts, and stop/target levels.

---

## Trigger Phrases

- "How much should I trade?"
- "Size my position"
- "Calculate position size for [pair]"
- "How many contracts?"
- "Kelly sizing for this trade"
- "What's my position size?"
- "How much to risk on this?"
- "Give me entry, stop, and target"
- "Size this up"

---

## Inputs

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | string | Yes | — | Trading pair (e.g. BTCUSDT) |
| `signal_score` | float | Yes | — | FixedScorer score (0–12) |
| `direction` | string | Yes | — | LONG or SHORT |
| `available_capital` | float | No | From engine | USDT balance available for trading |
| `leverage` | integer | No | 5 | Desired leverage (1–10) |
| `entry_price` | float | No | Current market | Entry price estimate |
| `regime` | string | No | From engine | Bull / Bear / Chop |

---

## Execution Steps

### Step 1 — Validate Inputs
- Confirm score ≥ 5.5. If below, respond: "Score too low for position sizing. Minimum threshold is 5.5."
- Cap leverage at 10× testnet / 5× recommended

### Step 2 — Call Scale Endpoint
```
POST http://localhost:8001/scale
Body: {
  "symbol": "{symbol}",
  "score": {signal_score},
  "direction": "{direction}",
  "capital": {available_capital},
  "leverage": {leverage}
}
```

Expected response:
```json
{
  "symbol": "BTCUSDT",
  "position_size_usdt": 450.00,
  "contracts": 0.0054,
  "leverage": 5,
  "kelly_fraction": 0.045,
  "entry_price": 83500.00,
  "stop_loss": 82173.50,
  "take_profit": 86152.00,
  "risk_usdt": 7.17,
  "rr_ratio": 2.01,
  "margin_required": 90.00
}
```

### Step 3 — Apply Regime Adjustment
- Chop regime → multiply `position_size_usdt` by 0.5
- Bull/Bear with confidence < 70% → multiply by 0.75

### Step 4 — Format Output

```
💰 POSITION SIZING — BTCUSDT LONG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signal Score:  9.2/12 (Very Strong)
Regime:        🟢 Bull (84% confidence)
Kelly Used:    25% fraction

POSITION DETAILS
  Size:          $450.00 USDT
  Contracts:     0.0054 BTC
  Leverage:      5×
  Margin Req:    $90.00

LEVELS
  Entry:         ~$83,500
  Stop Loss:     $82,173  (−1.59%)
  Take Profit:   $86,152  (+3.18%)
  R:R Ratio:     2.01:1 ✅

RISK
  Risk Amount:   $7.17 (0.07% of capital)
  Daily Risk Used: 0.07%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Confirm this trade? → I'll validate against Risk Gate and log to Notion.
```

---

## Kelly Fraction Rules

| Signal Score | Kelly Fraction | Max Position % |
|-------------|---------------|----------------|
| 9.0–12.0 | 50% of full Kelly | 3% of capital |
| 7.0–8.9 | 37.5% of full Kelly | 2.5% of capital |
| 5.5–6.9 | 25% of full Kelly | 2% of capital |
| Chop regime | Apply 0.5× multiplier | Half of above |

Hard cap: Never exceed 3% of total capital per trade.

---

## Chaining

After Position Sizer:
1. Automatically call **Risk Gate** to validate the sized position
2. If Risk Gate passes → offer to **log the trade** to Notion Journal
3. If Risk Gate blocked → explain which breaker triggered

---

## Error Handling

| Error | Response |
|-------|---------|
| Score < 5.5 | "Position sizing requires score ≥ 5.5. Current score is too low." |
| Capital not available | "Cannot fetch balance from engine. Enter capital manually." |
| Leverage > 10 | "Leverage capped at 10× for testnet safety. Adjusted to 10×." |

# Regime Detector Skill — CoinScopeAI
**Skill ID:** `coinscope.regime_detector`
**Version:** 1.0.0
**Platform:** Manus
**Category:** Market Intelligence

---

## Overview

Classifies the current market regime for any supported pair using the Hidden Markov Model (HMM) regime detector built into the CoinScopeAI engine. Returns one of three states: **Bull**, **Bear**, or **Chop** — with a confidence percentage and recommended trading stance.

---

## Trigger Phrases

- "What is the current regime?"
- "Is the market bullish?"
- "What regime is BTC in?"
- "Check market mode"
- "Is it a bull or bear market?"
- "What's the HMM saying?"
- "Market conditions for [pair]"
- "What mode are we in?"
- "Is this a trending or ranging market?"

---

## Inputs

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `symbol` | string | No | BTCUSDT | Pair to classify |
| `timeframe` | string | No | 4h | Timeframe for HMM analysis |

---

## Execution Steps

### Step 1 — Health Check
```
GET http://localhost:8001/health
```

### Step 2 — Get Regime
```
GET http://localhost:8001/regime/{symbol}
```

Expected response:
```json
{
  "symbol": "BTCUSDT",
  "regime": "bull",
  "confidence": 0.84,
  "hmm_state": 2,
  "timeframe": "4h",
  "ema_alignment": "bullish_stack",
  "price_vs_ema200": "above",
  "timestamp": 1712140000
}
```

### Step 3 — Format & Respond

Return in this format:

```
📊 REGIME ANALYSIS — BTCUSDT
━━━━━━━━━━━━━━━━━━━━━━━━
Regime:       🟢 BULL
Confidence:   84%
EMA Stack:    Bullish (20 > 50 > 200) ✅
Price vs 200: Above ✅
Timeframe:    4H
━━━━━━━━━━━━━━━━━━━━━━━━
Trading Stance: LONG-biased
→ Accept LONG signals with score ≥ 5.5
→ LONG signals need score ≥ 7.0 for full size
```

### Step 4 — Regime-Based Guidance

| Regime | Confidence | Recommended Action |
|--------|------------|-------------------|
| Bull | ≥ 70% | Accept LONG signals ≥ 5.5. SHORT requires score ≥ 8.0 |
| Bull | < 70% | Treat as transition — tighten stops, reduce size |
| Bear | ≥ 70% | Accept SHORT signals ≥ 5.5. LONG requires score ≥ 8.0 |
| Bear | < 70% | Transition possible — be cautious with new entries |
| Chop | Any | Require score ≥ 8.0 for any trade. Reduce size 50% |

---

## Regime Icons & Meanings

| Regime | Icon | Market Condition | Default Bias |
|--------|------|-----------------|--------------|
| Bull | 🟢 | Uptrend confirmed by HMM + EMA stack | LONG |
| Bear | 🔴 | Downtrend confirmed | SHORT |
| Chop | 🟡 | Range-bound, no clear trend | NEUTRAL / Reduce size |

---

## Chaining

- After Regime → offer to run **Market Scanner** filtered for regime direction
- After Regime + Scanner → offer **Position Sizer** for top signal

---

## Error Handling

| Error | Response |
|-------|---------|
| Engine offline | Prompt to start engine |
| Symbol not supported | "Regime model not yet trained for {symbol}. Try BTCUSDT, ETHUSDT, or SOLUSDT." |
| Confidence < 50% | Flag as "Uncertain — treat as Chop for risk purposes" |

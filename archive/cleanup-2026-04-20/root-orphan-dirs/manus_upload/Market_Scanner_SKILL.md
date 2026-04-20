# Market Scanner Skill — CoinScopeAI
**Skill ID:** `coinscope.market_scanner`
**Version:** 1.0.0
**Platform:** Manus
**Category:** Trading Intelligence / Signal Detection

---

## Overview

This skill triggers a live Binance Futures market scan across configured USDT-perpetual pairs. It calls the CoinScopeAI trading engine (via the `/scan` API endpoint), ranks pairs using the `FixedScorer` (0–12 score), and returns a structured signal table with pair name, signal direction, strength score, and recommended timeframe.

---

## Trigger Phrases

Use this skill when the user says any of the following (or similar):

- "Scan top movers"
- "Find setups"
- "What's setting up now?"
- "Run a scan"
- "Which pairs have signals?"
- "Give me the best setups"
- "What should I trade now?"
- "Any long/short setups?"
- "Scan the market"
- "Top signals right now"

---

## Inputs

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pairs` | string (comma-separated) | No | BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT, TAO/USDT | Pairs to scan |
| `top_n` | integer | No | 5 | Max results to return |
| `min_score` | float | No | 5.5 | Minimum signal strength score (0–12) |
| `signal_filter` | string | No | `ALL` | Filter by `LONG`, `SHORT`, or `ALL` |

---

## Execution Steps

### Step 1 — Validate Inputs
- Confirm the API server is reachable at `http://localhost:8001/health`
- If unreachable, respond: *"CoinScopeAI engine is offline. Please start the engine with `uvicorn api:app --reload --port 8001`"*

### Step 2 — Call Scan Endpoint
Make a GET request to:
```
GET http://localhost:8001/scan?pairs={pairs}
```

Expected response shape:
```json
{
  "signals": [
    {
      "symbol": "BTC/USDT",
      "signal": "LONG",
      "score": 8.5,
      "timeframe": "4h",
      "rsi": 61.2,
      "regime": "bull",
      "confidence": 0.84
    }
  ],
  "active_count": 3,
  "total_scanned": 6,
  "timestamp": 1712140000
}
```

### Step 3 — Filter & Rank Results
1. Filter signals where `signal` is `LONG` or `SHORT` (exclude `NEUTRAL`)
2. Apply `signal_filter` if set (e.g. only `LONG`)
3. Apply `min_score` threshold — drop results below it
4. Sort descending by `score`
5. Take top `top_n` results

### Step 4 — Format Output
Return a structured response in this format:

```
📡 MARKET SCAN — {timestamp}
Scanned: {total_scanned} pairs | Active Signals: {active_count}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RANK | PAIR       | SIGNAL | SCORE | TF  | RSI   | REGIME
  1  | BTC/USDT   | LONG   |  8.5  | 4h  | 61.2  | Bull 🟢
  2  | ETH/USDT   | LONG   |  7.8  | 4h  | 58.4  | Bull 🟢
  3  | SOL/USDT   | SHORT  |  6.2  | 1h  | 38.1  | Bear 🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Score Key: 0–5 Weak | 5.5–7 Moderate | 7.5–9 Strong | 9.5–12 Very Strong
```

### Step 5 — Suggest Follow-Up Actions
After presenting the table, offer:
- "Want me to **size a position** on any of these? (uses Kelly Criterion)"
- "Want to **check regime** for a specific pair?"
- "Want me to **set a Telegram alert** for the top signal?"

---

## Error Handling

| Error | Response |
|---|---|
| Engine offline (connection refused) | Prompt user to start engine |
| No active signals found | "No setups found above score {min_score}. Market may be choppy — try lowering the threshold or checking back in 15 min." |
| Partial data (some pairs missing) | Show available results, note which pairs failed |
| Score = 0 for all pairs | Suggest switching to 1h or 15m timeframe |

---

## Score Interpretation

| Score Range | Label | Action |
|---|---|---|
| 0.0 – 4.9 | Weak / No Signal | Skip |
| 5.0 – 5.9 | Moderate | Watch only |
| 6.0 – 7.4 | Good | Valid setup, confirm with regime |
| 7.5 – 8.9 | Strong | High-priority setup |
| 9.0 – 12.0 | Very Strong | Maximum confidence |

---

## Scoring Breakdown (Reference)

The `FixedScorer` engine calculates a total score (0–12) from 6 graduated sub-scores:

| Sub-Score | Weight | What it Measures |
|---|---|---|
| Momentum | 0–3 | RSI position (30–70 band) |
| Trend | 0–3 | EMA 9/21 alignment |
| Volatility | 0–3 | ATR as % of price |
| Volume | 0–3 | Volume vs 20-bar MA |
| Entry Timing | 0–3 | Pullback depth from EMA |
| Liquidity | 0–3 | Bid-ask spread tightness |

**Long signal:** total score ≥ 5.5
**Short signal:** total score ≤ 6.5 (inverted)

---

## Supported Pairs (Week 1)

| Pair | Volatility | Liquidity | HMM Trained |
|---|---|---|---|
| BTC/USDT | Low | Very High | ✅ |
| ETH/USDT | Low | Very High | ✅ |
| SOL/USDT | Medium | High | ✅ |
| BNB/USDT | Low | High | ⚠️ Validate |
| XRP/USDT | Medium | High | ⚠️ Validate |
| TAO/USDT | High | Medium | ⚠️ Monitor slippage |

---

## Dependencies

- CoinScopeAI engine running at `localhost:8001`
- Python packages: `fastapi`, `uvicorn`, `ccxt`, `numpy`, `pandas`
- Engine files: `master_orchestrator.py`, `scoring_fixed.py`, `pair_monitor.py`, `hmm_regime_detector.py`

---

## Notes for Agent

- Always display timestamp in the output so traders know data freshness
- If `regime` is `chop`, flag the signal as lower-confidence even if score is high
- Do NOT execute trades — this skill is read-only signal detection only
- If the user asks for a scan + entry price + stop loss in one message, chain this skill → Signal Analysis Skill → Position Sizer Skill

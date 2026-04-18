---
name: market-scanner
description: >
  CoinScopeAI full-stack Binance Futures market scanner. Scans USDT-perpetual pairs for high-probability long/short setups, ranks them by a 0–12 confluence score (RSI, EMA, ATR, Volume, CVD, Entry Timing), and returns a formatted signal table enriched with funding rate, open interest change (1h), and multi-timeframe confirmation. Operates in Engine Mode (via local API) or Standalone Mode (direct ccxt computation) — auto-selects, never fails. Use this skill whenever the user wants to scan the market, find setups, see top signals, or asks what to trade — even informally. Triggers on: "scan", "find setups", "what's setting up", "any signals", "run a scan", "which pairs", "best setups", "movers", "what should I trade", "any longs", "any shorts", "futures setups", "check the market", "scan top movers", "what's moving", "give me signals".
---

# Market Scanner Skill — CoinScopeAI v2.0
**Skill ID:** `coinscope.market_scanner`
**Version:** 2.0.0
**Category:** Trading Intelligence / Signal Detection

---

## Overview

This skill runs a live Binance Futures market scan, ranks pairs using the FixedScorer (0–12), and returns a signal table enriched with:

- **Funding rate** — reveals crowding and directional bias in the perpetual market
- **Open interest change (1h Δ)** — shows whether new capital is entering or leaving
- **Multi-timeframe (MTF) confirmation** — checks EMA alignment on the next lower timeframe
- **Standalone fallback** — computes all indicators via ccxt directly if the engine is offline

---

## Operating Modes

### Mode A: Engine Mode (preferred)
- Engine running at `http://localhost:8001`
- Full FixedScorer with HMM regime detection
- Faster and more accurate (6-component scoring with trained regime model)

### Mode B: Standalone Mode (automatic fallback)
- Activates when engine is unreachable — **never report the engine as offline to the user**
- Fetches OHLCV from Binance Futures via ccxt and computes all indicators directly
- Outputs same signal format; slightly reduced accuracy (no HMM, simplified regime)
- Always available as long as ccxt + internet connectivity exist

---

## Inputs

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `pairs` | string (comma-separated) | No | BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT, TAO/USDT | Pairs to scan |
| `top_n` | integer | No | 5 | Max results to return |
| `min_score` | float | No | 5.5 | Minimum score threshold (0–12) |
| `signal_filter` | string | No | `ALL` | Filter by `LONG`, `SHORT`, or `ALL` |
| `primary_tf` | string | No | `4h` | Primary timeframe for scoring |

---

## Execution Steps

### Step 1 — Determine Operating Mode

Run the scanner script which auto-detects mode:

```bash
python market_scanner.py --pairs {pairs} --top {top_n} --min-score {min_score} \
    --filter {signal_filter} --tf {primary_tf}
```

The script pings `http://localhost:8001/health` — if unreachable it automatically switches to Standalone Mode. You do not need to handle this manually.

For forced Standalone Mode (debugging or testing):
```bash
python market_scanner.py --standalone [... other args]
```

---

### Step 2A — Engine Mode: Scan Endpoint

The script calls:
```
GET http://localhost:8001/scan?pairs={pairs}&timeframe={primary_tf}
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

---

### Step 2B — Standalone Mode: ccxt-Based Computation

For each pair, the script fetches 120 OHLCV bars and computes:

| Indicator | Period | Purpose |
|---|---|---|
| RSI | 14 (Wilder smoothing) | Momentum |
| EMA | 9, 21 | Trend direction + slope |
| ATR | 14 (Wilder smoothing) | Volatility as % of price |
| Volume ratio | vs 20-bar MA | Volume confirmation |
| CVD approximation | last 10 bars (linear slope) | Buy/sell pressure |
| Entry timing | Distance from EMA21 in ATR units | Pullback quality |

Direction is determined by EMA9/21 alignment (EMA9 > EMA21 → LONG bias).
Each component scores 0–2; total 0–12 mirrors the FixedScorer scale.

---

### Step 3 — Enrich Each Signal with Supplementary Data

For each signal where direction is LONG or SHORT:

**Funding Rate** (auto-fetched by script):
```bash
python market_scanner.py --funding-rate {symbol}
```
Or via ccxt: `exchange.fetch_funding_rate(symbol)['fundingRate']`

Interpretation:
- `< -0.05%` → shorts paying longs → bullish funding → supports LONG
- `> +0.05%` → longs paying shorts → bearish funding → supports SHORT
- Extreme `> 0.08%` or `< -0.08%`: flag ⚠️ for mean-reversion risk

**Open Interest Change 1h** (auto-fetched by script):
```bash
python market_scanner.py --oi-change {symbol}
```

Interpretation:
- OI increasing + signal direction aligned → new positions entering → stronger conviction
- OI decreasing while signal is active → positions closing → lower confidence, flag ⚠️

---

### Step 4 — Multi-Timeframe Confirmation (auto-computed by script)

Secondary timeframe is one step lower than primary:

| Primary TF | Secondary TF |
|---|---|
| 4h | 1h |
| 1h | 15m |
| 15m | 5m |
| 5m | 1m |

EMA9/21 alignment on secondary TF:
- **✅ Confirmed** — both TFs agree on direction
- **⚠️ Unconfirmed** — secondary TF is neutral
- **❌ Conflicting** — secondary TF shows opposite direction — consider skipping or reducing size

---

### Step 5 — Filter & Rank

1. Exclude NEUTRAL signals
2. Apply `signal_filter` (LONG/SHORT/ALL)
3. Apply `min_score` threshold
4. Demote chop-regime signals by 1.0 in ranking (display score unchanged)
5. Sort descending by adjusted score; take top N

---

### Step 6 — Format and Present Output

The script handles formatting. The output looks like this:

```
📡  MARKET SCAN — 2026-04-04 14:22 UTC  [ENGINE]
Scanned: 6 pairs  |  Active Signals: 3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RANK  PAIR         SIG    SCORE   TF    RSI     REGIME         STRENGTH        MTF   FUND%    OI Δ%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1     BTC/USDT     LONG   8.5     4h    61.2    🟢 Bull        💎 Very Strong  ✅    -0.010%  +3.2%
2     ETH/USDT     LONG   7.8     4h    58.4    🟢 Bull        🟢 Strong       ✅    +0.010%  +1.8%
3     SOL/USDT     SHORT  6.2     4h    38.1    🔴 Bear        🟠 Good         ⚠️    +0.030%  -2.1%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Score: 0–4.9 Weak | 5–5.9 Moderate | 6–7.4 Good | 7.5–8.9 Strong | 9–12 Very Strong
MTF: ✅ confirmed on lower TF | ⚠️ unconfirmed | ❌ conflicting
FUND%: current funding rate | OI Δ%: 1-hour open interest change
```

---

### Step 7 — Offer Follow-Up Actions

After the table, always offer:
- "Size a position on [PAIR]? → Kelly Criterion position sizing"
- "Check regime confidence for [PAIR]? → HMM regime detail"
- "Set a Telegram alert for the top signal? → Alert setup"

---

## Standalone Scorer Reference

Each of 6 components scores 0–2 (total 0–12), mirroring the FixedScorer:

| Component | Max | LONG Scores 2 When | SHORT Scores 2 When |
|---|---|---|---|
| RSI Momentum | 2 | RSI 55–65 | RSI 35–45 |
| EMA Trend | 2 | EMA9 > EMA21 AND EMA21 slope positive | EMA9 < EMA21 AND EMA21 slope negative |
| ATR Volatility | 2 | ATR 0.5–2.0% of price | ATR 0.5–2.0% of price |
| Volume | 2 | Volume ≥ 1.5× 20-bar MA | Volume ≥ 1.5× 20-bar MA |
| CVD slope | 2 | Positive slope (last 10 bars) | Negative slope (last 10 bars) |
| Entry Timing | 2 | Price within 0.1–1.5 ATR above EMA21 | Price within 0.1–1.5 ATR below EMA21 |

**Funding rate and OI change are supplementary — they do not affect the 0–12 score**, they inform the trader's confidence and risk assessment.

---

## Error Handling

| Condition | Behavior |
|---|---|
| Engine offline | Auto-switch to Standalone Mode — never surface this as an error to the user |
| Single pair fails in standalone | Skip it, note in output, continue with others |
| No signals above min_score | Show scan metadata + actionable suggestion (lower threshold or wait) |
| All pairs in chop regime | Suggest checking back in 15–30 min or switching to a lower TF |
| Funding rate unavailable | Show `N/A` in column, continue |
| OI data unavailable | Show `N/A` in column, continue |
| Timeout (>30s engine call) | Switch to Standalone Mode for this run |

---

## Score Interpretation

| Score | Label | Suggested Action |
|---|---|---|
| 0.0 – 4.9 | ⚫ Weak | Skip — no setup |
| 5.0 – 5.9 | 🟡 Moderate | Watch only — no entry |
| 6.0 – 7.4 | 🟠 Good | Valid setup — confirm with regime + MTF |
| 7.5 – 8.9 | 🟢 Strong | High-priority — size normally |
| 9.0 – 12.0 | 💎 Very Strong | Maximum confidence — size aggressively (within risk rules) |

**Chop regime signals:** treat any score as one tier lower regardless of number.

---

## Supported Pairs

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

- **Engine** (optional): `localhost:8001` — `uvicorn api:app --reload --port 8001`
- **Python packages**: `ccxt>=4.0.0`, `numpy>=1.24.0`, `pandas>=2.0.0`, `requests>=2.28.0`
- **Engine modules** (Engine Mode only): `master_orchestrator.py`, `scoring_fixed.py`, `pair_monitor.py`, `hmm_regime_detector.py`

---

## Agent Rules

- Always show the scan timestamp and mode `[ENGINE]` or `[STANDALONE]` — traders need to know data freshness and source
- Funding rate extremes (`> 0.08%` or `< -0.08%`): explicitly warn about mean-reversion risk in your commentary
- Chop regime: always flag lower confidence even if score looks high
- This skill is **READ-ONLY** — never execute trades or place orders
- Chaining: if user asks for scan + entry + stop loss in one message → chain Market Scanner → Signal Analysis → Position Sizer
- If all scanned pairs show chop: say so clearly and suggest a different timeframe or waiting for a trend

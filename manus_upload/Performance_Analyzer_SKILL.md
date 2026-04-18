# Performance Analyzer Skill — CoinScopeAI
**Skill ID:** `coinscope.performance_analyzer`
**Version:** 1.0.0
**Platform:** Manus
**Category:** Analytics

---

## Overview

Retrieves and presents trading performance metrics from the CoinScopeAI engine. Covers P&L, win rate, drawdown, Sharpe ratio, and per-regime breakdowns. Use this for weekly reviews, daily check-ins, or any time the trader wants to understand how the system is performing.

---

## Trigger Phrases

- "How am I performing?"
- "Show my stats"
- "What's my win rate?"
- "Weekly performance summary"
- "How much have I made?"
- "Show P&L"
- "What's my drawdown?"
- "Performance report"
- "Give me my numbers"
- "How is CoinScopeAI doing?"

---

## Inputs

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `period` | string | No | week | day / week / month / all |

---

## Execution Steps

### Step 1 — Call Performance Endpoint
```
GET http://localhost:8001/performance?period={period}
```

Expected response:
```json
{
  "period": "week",
  "total_trades": 12,
  "wins": 7,
  "losses": 5,
  "win_rate": 0.583,
  "net_pnl_usdt": 87.40,
  "avg_win_usdt": 22.60,
  "avg_loss_usdt": 8.94,
  "avg_rr": 1.87,
  "max_drawdown_pct": 0.031,
  "sharpe_ratio": 1.42,
  "best_trade": { "symbol": "BTCUSDT", "pnl": 48.20 },
  "worst_trade": { "symbol": "DOGEUSDT", "pnl": -14.30 },
  "by_regime": {
    "bull": { "trades": 7, "win_rate": 0.714 },
    "bear": { "trades": 3, "win_rate": 0.667 },
    "chop": { "trades": 2, "win_rate": 0.0 }
  },
  "by_score_band": {
    "9-12": { "trades": 3, "win_rate": 1.0 },
    "7-8.9": { "trades": 5, "win_rate": 0.6 },
    "5.5-6.9": { "trades": 4, "win_rate": 0.25 }
  }
}
```

### Step 2 — Format Output

```
📊 PERFORMANCE REPORT — This Week
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OVERVIEW
  Trades:       12  (7W / 5L)
  Win Rate:     58.3%   Target: ≥55% ✅
  Net P&L:      +$87.40
  Avg Win:      $22.60  |  Avg Loss: $8.94
  Avg R:R:      1.87:1  Target: ≥1.5 ✅
  Max Drawdown: 3.1%    Limit: 10% ✅
  Sharpe Ratio: 1.42

BY REGIME
  🟢 Bull:  7 trades — 71.4% win rate
  🔴 Bear:  3 trades — 66.7% win rate
  🟡 Chop:  2 trades — 0.0% win rate ⚠️

BY SCORE BAND
  ⚡ 9–12 (Very Strong):  3 trades — 100% win
  💪 7–8.9 (Strong):      5 trades — 60% win
  ✅ 5.5–6.9 (Moderate):  4 trades — 25% win ⚠️

HIGHLIGHTS
  Best Trade:  BTCUSDT +$48.20
  Worst Trade: DOGEUSDT −$14.30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 Insight: Chop regime trades have 0% win rate.
   Consider raising min_score to 8.0 in Chop.
   Moderate score (5.5–6.9) trades underperforming.
   Consider raising threshold to 7.0.
```

### Step 3 — Auto-Insights

Always analyse the data and add 2–3 actionable insights at the bottom. Focus on:
- Which regime performs best/worst
- Which score band is dragging win rate
- Whether R:R target is being met
- Whether drawdown is trending toward limit

---

## Performance Benchmarks

| Metric | Target | Warning | Critical |
|--------|--------|---------|---------|
| Win Rate | ≥ 55% | 45–55% | < 45% |
| Avg R:R | ≥ 1.5:1 | 1.0–1.5 | < 1.0 |
| Sharpe Ratio | ≥ 1.0 | 0.5–1.0 | < 0.5 |
| Max Drawdown | < 5% | 5–8% | > 8% |
| Consecutive Losses | < 3 | 3–4 | 5 (gate triggers) |

---

## Weekly Review Mode

When trader says "weekly review" or "end of week summary", compile:
1. Performance report (above)
2. Best and worst trade breakdown
3. Regime distribution for the week
4. Recommendations for next week (score thresholds, regime adjustments)
5. Prompt to fill in the Weekly Performance Report template in Google Drive

---

## Chaining

After Performance Report:
- If drawdown > 5% → automatically run Risk Gate status check
- If win rate < 45% → suggest lowering scan frequency and raising min_score threshold
- Offer to export report to Notion or Weekly Performance Report template

---
name: coinscope-daily-review
description: End-of-day or on-demand testnet performance review for CoinScopeAI — risk-first framing, caps versus actuals, regime breakdown, anomaly notes from the journal, and prioritized next steps. Use to recap the last 24h (or arbitrary window) on Binance Testnet.
triggers:
  - "daily testnet review"
  - "give me today's performance"
  - "how did the system do in the last 24h"
  - "daily summary for BTC/ETH/ALTS"
  - "EOD review"
allowed-tools: Bash(curl *), Bash(python3 *), Read, Grep
inputs:
  required:
    - none
  defaults:
    - window: last 24h (rolling, UTC)
  optional:
    - symbols          # default: top movers + BTCUSDT, ETHUSDT
    - window_override  # e.g. "last 7d"
phase_constraint: Testnet only. 30-day validation phase. No real capital. Always include the disclaimer in user-facing output.
---

# CoinScopeAI — Daily Testnet Performance Review

Frame everything as risk-first: drawdown and daily-loss usage come *before* PnL.

## Inputs

Defaults to last 24h on Binance Testnet. User may override window or symbol set.

Engine base URL (dev): `http://localhost:8001`

## Steps

### 1. Frame assumptions
State explicitly:
- Window (default: last 24h UTC).
- Venue: Binance Testnet (no real capital).
- Symbol set.
- Phase: P0 validation cohort (capped at 40 users, May 2026).

### 2. Fetch core metrics
From `/performance`:
- PnL (gross, R-units, %)
- Max drawdown observed in window
- Daily loss observed
- Trade count, win rate, average R
- Per-symbol breakdown

From `/journal`:
- Notable events: gate rejections, regime flips around trades, errors, kill-switch activations.

### 3. Risk-first evaluation
Compare observed vs canonical caps:
- Max drawdown observed vs **10% cap** (account hard stop)
- Worst rolling 24h loss vs **5% cap** (daily loss limit)
- Concurrent open positions vs **5 cap**
- Heat used vs **80% cap**

Flag any breach **or near-breach** (>70% of cap), even if PnL is positive.

### 4. Regime context
For each major symbol, summarize regime distribution in window:
- % time in Trending / Mean-Reverting / Volatile / Quiet.
- Highlight regimes where the engine performed poorly (e.g., repeated losses in Volatile).

### 5. Anomaly scan
Cross-reference `/journal` events against trades:
- Did a regime flip occur within 5m of an entry? Within 5m of a stop-out?
- Were any signals issued during a `mock_fallback` window? Flag explicitly.
- Were any cap warnings issued?

### 6. Recommendations
2-3 next actions, ranked. Examples:
- Strategy tweaks (parameter review, regime filter tightening).
- Symbols/timeframes to pause.
- Tests or replays to add via `test-and-simulation-lab`.

**Never** call results "production-ready." If strong, say:
> "Candidate for further shadow-testing in the validation cohort."

## Output format

```
DAILY TESTNET REVIEW — {YYYY-MM-DD UTC}
window  last 24h
venue   Binance Testnet (no real capital)

OVERVIEW
PnL          +{x}R / {y}%
max DD       {a}% of cap (10%)
daily loss   {b}% of cap (5%)
trades       {n}   win-rate {w}%   avg R {r}
positions    peak {p} of cap (5)   heat peak {h}% of cap (80%)

BY SYMBOL
| symbol  | trades | PnL  | DD    | dominant regime |
| BTCUSDT |    12  | +2.1 | 1.4%  | Trending        |
| ETHUSDT |     8  | -0.4 | 2.1%  | Volatile        |
...

RISK ASSESSMENT
{No caps breached / Daily loss cap would have triggered at HH:MM / etc.}

NOTES & ANOMALIES
- {timestamp} regime flip BTCUSDT Trending → Volatile, signal expired
- {timestamp} mock_fallback active on /regime, 4 signals tagged
...

NEXT STEPS
1. {action}
2. {action}
3. {action}

DISCLAIMER
Testnet only. 30-day validation phase. No real capital.
```

## Anti-patterns

- Reporting PnL before risk usage (violates risk-first principle).
- Hiding `mock_fallback` events — they must be visible in NOTES.
- Saying "production-ready" / "ready to ship" — Scoopy voice violation.
- Skipping the disclaimer.

## Cross-references

- Skill: `skills_src/alerting-and-user-experience/SKILL.md` (severity tags align with journal)
- Skill: `skills_src/futures-market-researcher/SKILL.md` (regime distribution interpretation)
- Caps: `skills/coinscopeai-trading-rules/SKILL.md`
- Engine API: `skills/coinscopeai-engine-api/SKILL.md` (`/performance`, `/journal`)
- Daily-status skill: `skills_src/daily-status/SKILL.md`

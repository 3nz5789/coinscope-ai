---
name: coinscope-signal-design
description: Take a trader's informal idea and turn it into a formal rule set with a vectorized backtest plan plus risk-first metrics. Use to prototype a new signal end-to-end (idea → rules → code → metrics → verdict) before any deployment talk.
triggers:
  - "let's prototype a funding + OI squeeze long"
  - "design a short-term mean-reversion algo for BTC 5m"
  - "turn this idea into rules and backtest it"
  - "is this signal real?"
allowed-tools: Bash(python3 *), Read, Grep, Edit, Write
inputs:
  required:
    - idea_description    # natural-language
    - universe            # e.g. ["BTCUSDT","ETHUSDT"]
    - timeframe           # 5m | 15m | 1h
  optional:
    - regime_filter       # subset of {Trending, Mean-Reverting, Volatile, Quiet}
    - backtest_window     # default: last 90 days
phase_constraint: Engine is frozen during the 30-day validation phase. This workflow produces the rule set + backtest script. Promotion is gated on cohort close and cannot be called "production-ready."
---

# CoinScopeAI — New Signal Prototype + Backtest

Front-end for `signal-design-and-backtest`. Idea → Rules → Code → Metrics → Verdict. Risk-first: a signal is not credible until drawdown and daily-loss exposure are documented against caps.

## Inputs

User provides natural-language idea, universe, timeframe. Optional: regime filter, backtest window.

## Steps

### 1. Idea capture
Restate the idea in **one sentence**. If you can't, ask for clarification.

GOOD: "Long BTC 5m when funding < -0.01% AND OI rises > 2% over 1h, only in Trending regime."
BAD: "Long BTC when it looks oversold."

### 2. Domain sanity (futures-market-researcher)
- Are the features perp-only (funding, OI, basis, liquidations) or generic (price, volume)?
- Do thresholds sit in the empirical range for the symbol over the window?
- Does the proposed setup contradict the regime filter? Flag if so.

### 3. Rule formalization (YAML)
```yaml
signal_id: <kebab-case-id>
side: long | short
universe: [...]
timeframe: 5m | 15m | 1h
regime_filter: [...]
features:
  - name: funding_rate
    threshold: "< -0.0001"
    window: latest
  - name: oi_pct_change_1h
    threshold: "> 0.02"
entry: <price/event>
exit:
  take_profit: <ATR-based or fixed>
  stop_loss:   <ATR-based or fixed>
  time_stop:   <bars>
gates:
  max_leverage: 10x
  max_open_positions: 5
  daily_loss_limit: 5%
assumptions:
  - bars: 5m, last 500 closes
  - data_source: Binance USDT-M
  - validation_phase: P0 (testnet only)
```

### 4. Backtest skeleton
Vectorized pandas. Place under `scripts/backtests/<signal_id>.py`. Skeleton:
```python
# 1. Load OHLCV + funding + OI for universe & window
# 2. Compute features (regime aligned via /regime/{symbol} or local model)
# 3. Build entry mask (AND-joined conditions)
# 4. Simulate exits (TP / SL / time-stop, whichever first)
# 5. Aggregate trades into per-trade dataframe (entry_ts, exit_ts, pnl_R)
# 6. Apply gate layer LAST: clip by max_open_positions and daily_loss_limit
```

Never row-by-row loops on the entry/exit decision.

### 5. Risk-first metrics
**Mandatory** (in this order):
- Max drawdown (% of equity) — must be < 10%
- Worst rolling 24h loss — must be < 5%
- Hit rate
- Average R (avg win / avg loss)
- Trades per day (sanity vs `max_open_positions: 5`)
- Regime-conditional hit rate (if `regime_filter` set)

**Optional**: Sharpe, Sortino, profit factor.

### 6. Verdict
One of:
- `Promote to shadow-test` — survives all caps, regime filter justified.
- `Iterate` — fails one metric or has unjustified parameters; specify what to change.
- `Reject` — fundamental flaw (overfit, lookahead bias, regime contradiction).

Never use "production-ready." Strong results = "candidate for further shadow-testing in the validation cohort."

## Output format

- `Idea (one sentence)`
- `Domain sanity` — perp-feature check, regime fit
- `Signal spec (YAML)` — the rule block above
- `Backtest script` — saved to `scripts/backtests/<signal_id>.py`
- `Metrics table` — all "Mandatory" rows
- `Verdict` — Promote / Iterate / Reject + justification

## Anti-patterns

- Looping bar-by-bar in pandas.
- Reporting Sharpe without max drawdown — mandatory order matters.
- Optimizing parameters on the same window the metrics are measured on.
- Promoting a signal that survives metrics but contradicts regime profile.
- Skipping the gate layer in the backtest.
- Calling output "production-ready."

## Cross-references

- Skill: `skills_src/signal-design-and-backtest/SKILL.md`
- Skill: `skills_src/futures-market-researcher/SKILL.md`
- Skill: `skills_src/test-and-simulation-lab/SKILL.md` (regression coverage on promote)
- Caps: `skills/coinscopeai-trading-rules/SKILL.md`
- Engine API: `skills/coinscopeai-engine-api/SKILL.md`

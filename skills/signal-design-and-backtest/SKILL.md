---
name: signal-design-and-backtest
description: Convert an informal trade idea into an explicit rule set (entry, exit, filters, gates) and produce a vectorized backtest with risk-first metrics (max drawdown, daily loss exposure, hit rate, average R, Sharpe). Use when a trader proposes a new signal, when an existing signal needs formalization before it can be evaluated, or when "intuition" needs to be turned into testable code. Triggers on "design a signal", "prototype a signal", "backtest this idea", "formalize this strategy", "is this signal real", "turn this into rules", "let's test this on history", "what's the hit rate".
---

# Signal Design and Backtest

Turns trader intuition into rules + numbers. Risk-first: a signal is not credible until drawdown, daily-loss exposure, and hit rate are documented against caps.

## When to use

- A trader (or Scoopy) proposes a new signal idea in informal language.
- An existing signal needs to be re-formalized before a parameter change.
- A regime-conditional behavior needs a controlled test (e.g., "this only works in Trending").
- Before any signal is referenced in user-facing copy as "validated."

## When NOT to use

- Live engine changes — engine is frozen during the 30-day validation phase.
- Pure performance review of already-deployed signals — use `daily-testnet-review` workflow.
- Risk-cap changes — those route to `coinscopeai-premortem` and the decision log.

## Process (5 phases — Idea → Rules → Code → Metrics → Verdict)

### Phase 1 — Idea capture

Restate the idea in one sentence. If you cannot, the idea is not specific enough. Examples:
- GOOD: "Long BTC 5m when funding < -0.01% and OI rises >2% over 1h, only in Trending regime."
- BAD: "Long BTC when it looks oversold." (which oversold? which timeframe? which regime?)

### Phase 2 — Rule formalization

Output a YAML-shaped rule block:

```yaml
signal_id: <kebab-case-id>
side: long | short
universe:
  - BTCUSDT
  - ETHUSDT
timeframe: 5m | 15m | 1h
regime_filter:
  - Trending
features:
  - name: funding_rate
    threshold: "< -0.0001"
    window: latest
  - name: oi_pct_change_1h
    threshold: "> 0.02"
entry: <explicit price/event>
exit:
  take_profit: <ATR-based or fixed>
  stop_loss: <ATR-based or fixed>
  time_stop: <bars>
gates:
  - max_leverage: 10x
  - max_open_positions: 5
  - daily_loss_limit: 5%
assumptions:
  - bars: 5m, last 500 closes
  - data_source: Binance USDT-M
  - validation_phase: P0 (testnet only)
```

### Phase 3 — Backtest code

Vectorized pandas, never row-by-row loops for the entry/exit decision. Skeleton:

```python
# 1. Load OHLCV + funding + OI for the universe and window.
# 2. Compute features (funding_rate, oi_pct_change_1h, regime).
# 3. Build entry mask: all conditions AND-joined.
# 4. Simulate exits: take-profit, stop-loss, or time-stop, whichever first.
# 5. Aggregate trades into a per-trade dataframe (entry_ts, exit_ts, pnl_R).
# 6. Apply the gate layer last — clip by max_open_positions, daily_loss_limit.
```

Always ship the backtest as a script under `scripts/backtests/<signal_id>.py`, not as a notebook cell, so it's reproducible.

### Phase 4 — Risk-first metrics

Mandatory metrics. Optional ones come after.

| Metric | Mandatory? | Cap reference |
|---|---|---|
| Max drawdown (% of equity) | Yes | Must be < 10% (account hard stop) |
| Worst rolling 24h loss | Yes | Must be < 5% (daily loss limit) |
| Hit rate | Yes | — |
| Average R (avg win / avg loss) | Yes | — |
| Trades per day | Yes | Sanity-check vs `max_open_positions: 5` |
| Sharpe (annualized) | Optional | — |
| Sortino | Optional | — |
| Regime-conditional hit rate | Yes if `regime_filter` is set | Justifies the filter |

### Phase 5 — Verdict

Always one of:
- `Promote to shadow-test` — survives all caps, hit rate documented, regime filter justified.
- `Iterate` — fails one metric or has unjustified parameters; specify what to change.
- `Reject` — fundamental flaw (overfit, lookahead bias, regime contradiction per `futures-market-researcher`).

Never use "production-ready." Use "candidate for further shadow-testing in the validation cohort" if results are strong.

## Anti-patterns

- Looping bar-by-bar in pandas — kills reproducibility and speed.
- Reporting Sharpe without max drawdown — mandatory metrics first.
- Optimizing parameters on the same window you measure on (lookahead / overfit).
- Promoting a signal that survives metrics but contradicts regime profile per `futures-market-researcher`.
- Skipping the gate layer — a backtest without `max_open_positions` and `daily_loss_limit` is wrong by construction.

## Output contract

- YAML rule block (Phase 2)
- Reproducible script under `scripts/backtests/<signal_id>.py`
- Metrics table covering all "Mandatory? = Yes" rows
- Verdict line with justification
- Cross-reference into `business-plan/_decisions/decision-log.md` if Promote

## Cross-references

- Domain validation: `skills_src/futures-market-researcher`
- Risk caps: `skills/coinscopeai-trading-rules`
- Engine endpoints: `skills/coinscopeai-engine-api` (`/scan`, `/regime/{symbol}`)
- Replay regression: `skills_src/test-and-simulation-lab`
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)

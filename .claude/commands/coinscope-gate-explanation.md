---
name: coinscope-gate-explanation
description: Explain why a specific trade was blocked or gated — first-failing cap, current vs threshold values, regime context, and 2-3 risk-consistent alternatives. Use when the user asks "why was this blocked?" or pastes a /risk-gate fail response.
triggers:
  - "why was this BTC long blocked?"
  - "explain this gate fail for SOL at 12:10"
  - "tell me exactly which limit rejected this trade"
  - "why did /risk-gate fail?"
allowed-tools: Bash(curl *), Read, Grep
inputs:
  required:
    - symbol
    - side
    - size_or_leverage
    - timestamp_utc
  optional:
    - risk_gate_payload   # raw /risk-gate response
phase_constraint: User-facing output — apply the canonical alert payload schema from `alerting-and-user-experience` and surface the disclaimer.
---

# CoinScopeAI — Gate Explanation

The "Why rejected?" template from `alerting-and-user-experience`. First-failing cap + current vs threshold + safe alternatives — never "just raise the cap."

## Inputs

User provides the attempted trade params (symbol, side, size or leverage, timestamp) and either pastes the `/risk-gate` response or asks Scoopy to re-run with same params.

Engine base URL (dev): `http://localhost:8001`

## Steps

### 1. Reconstruct gate evaluation
Parse `/risk-gate` result. Identify which checks ran and the **first failing cap**.

The full gate set:
- `leverage` → max 10x (per PCC v2 §8 Capital Cap)
- `drawdown` → max 10% (account hard stop)
- `daily_loss` → max 5% (24h rolling)
- `heat` → max 80% per position
- `max_positions` → max 5 concurrent (revised 2026-05-03)
- `regime_restriction` → tightens in Volatile, suppresses most signals in Quiet

### 2. Map fail to canonical cap
For each failing check, show:
- Cap name
- Threshold value (canonical)
- Current value at request time
- % of cap consumed

### 3. Contextualize with regime
- Pull `/regime/{symbol}` at request time.
- If Volatile or Quiet, explain how the regime tightened gate strictness or suppressed the signal.

### 4. Propose safe alternatives
2-3 concrete, risk-consistent options. Examples:
- Smaller size (compute the size that would pass the binding cap).
- Close another position (reduces `open_positions` and `heat`).
- Wait for daily loss to cool down (compute the time when cap clears).
- Wait for regime to flip (with caveat: speculative).

**Never** suggest "raise the cap" as a first option. Cap changes route through `coinscopeai-premortem` and the decision log.

### 5. Render in canonical alert format
Use the `rejected` template from `alerting-and-user-experience`:

```
REJECTED  {side} {symbol} @ {price}
gate      FAIL — {first_failing_cap}
caps      DD {dd}% (cap 10%) | daily_loss {dl}% (cap 5%) | leverage {lev}x (cap 10x) | heat {h}% (cap 80%) | open {n} (cap 5)
regime    {regime} ({confidence})
options   {alt_1} | {alt_2} | {alt_3}
note      Testnet only. 30-day validation phase. No real capital.
```

## Output format

- `Summary` — one sentence: "Trade blocked by [primary_cap]."
- `Gate breakdown` — table: check, status, threshold, actual value.
- `Regime impact` — short note if regime mattered.
- `Safe options` — 2-3 alternatives with the cap each one relieves.
- `Telegram-ready render` — the REJECTED block above, ready to paste.

## Anti-patterns

- Suggesting "raise the cap" as a first option.
- Hiding which gate failed first behind generic "risk too high."
- Skipping regime context when regime was the binding constraint.
- Omitting the disclaimer in user-facing output.
- Inventing a cap that isn't in canonical list.

## Cross-references

- Skill: `skills_src/alerting-and-user-experience/SKILL.md` (the canonical `rejected` template)
- Caps: `skills/coinscopeai-trading-rules/SKILL.md`
- Engine API: `skills/coinscopeai-engine-api/SKILL.md` (`/risk-gate`, `/regime/{symbol}`)
- Premortem (for cap-change requests): `skills/coinscopeai-premortem/SKILL.md`

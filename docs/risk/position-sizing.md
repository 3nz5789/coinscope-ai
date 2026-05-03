# Position Sizing

**Status:** current
**Audience:** developers reviewing or modifying `kelly_position_sizer.py`
**Related:** [`risk-framework.md`](risk-framework.md), [`risk-gate.md`](risk-gate.md), [`../backend/configuration.md`](../backend/configuration.md)

How the engine turns a gate-accepted candidate into a position size in base currency. The short version: fractional Kelly with a hard cap and a regime multiplier.

## The pipeline

```
Kelly-full → × fractional factor (0.25)
           → clamp to hard cap (2% of equity)
           → × regime multiplier (bull 1.0 / chop 0.5 / bear 0.3)
           → × leverage respecting MAX_LEVERAGE (10x)
           → round to exchange step size
```

Each step is a clamp or a multiply, never a widen. The output is always ≤ the previous step.

## Step 1 — Kelly-full

Classical Kelly fraction:

```
f* = edge / odds
```

Where `edge` is expected return and `odds` is the risk/reward ratio implied by the ATR stop and the 2:1 RR take-profit. The scorer provides the expected edge; the stop placement provides the denominator.

Kelly-full is rarely used directly — it overreacts to noisy edge estimates.

## Step 2 — Fractional Kelly (0.25)

Multiply by `KELLY_FRACTION = 0.25`. This is a standard fractional-Kelly discount that damps the sensitivity of Kelly-full to edge mis-estimation. Most practical literature lands between 0.2 and 0.5; we picked the low end.

## Step 3 — Hard cap (2% of equity)

`KELLY_HARD_CAP_PCT = 2.0`. This is an absolute ceiling. No candidate, in any regime, at any edge, is sized above 2% of equity. If the fractional Kelly says 5%, the sizer clips to 2%.

The cap is enforced after the fractional factor but before the regime multiplier — the multiplier can only reduce size further, never restore it.

## Step 4 — Regime multiplier

Read from the HMM regime detector. The multiplier table is fixed during validation:

| HMM state | Multiplier |
| --- | --- |
| bull | 1.0 |
| chop | 0.5 |
| bear | 0.3 |

The v3 classifier's labels do not enter the sizing pipeline today — they adjust the scoring floor, not size. Consolidating the two systems' influence on sizing is a post-validation item.

## Step 5 — Leverage ceiling

The sized trade is converted to a notional and checked against `MAX_LEVERAGE = 10x`. If the implied leverage exceeds the cap, size shrinks further.

## Step 6 — Exchange step size

Binance imposes a minimum quantity and a step size per symbol. The sizer rounds down to the nearest valid step. If rounding down yields zero (size below minimum), the gate rejects with `size_below_minimum` (see [`risk-gate.md`](risk-gate.md)).

## Worked examples

### Example 1 — Clean bull

- Equity: $10,000
- Kelly-full: 12%
- After fractional (0.25): 3%
- After hard cap (2%): 2%
- Regime (bull): × 1.0 → 2%
- Final: $200 notional

### Example 2 — Same candidate, chop regime

- Equity: $10,000
- Kelly-full: 12%
- After fractional: 3%
- After cap: 2%
- Regime (chop): × 0.5 → 1%
- Final: $100 notional

### Example 3 — Bear regime, lower edge

- Equity: $10,000
- Kelly-full: 3%
- After fractional: 0.75%
- After cap (no effect, below): 0.75%
- Regime (bear): × 0.3 → 0.225%
- Final: $22.5 notional → likely rejected as below minimum for most perps

Example 3 is deliberate. In bear regimes with low edge, the engine should either not trade or trade a token size. The sizing pipeline naturally produces that outcome; the gate enforces the floor.

## Invariants

1. **Monotone non-increasing across steps.** Each step can only leave size the same or smaller. A step that increased size would be a bug.
2. **No step may be skipped.** The sizer does not have an "override" path. If you want a different size, the right answer is a different candidate or a different regime, not a flag.
3. **The cap is absolute.** The 2% hard cap is enforced in code, not config alone. Changing the cap requires both a config change **and** a PR to the sizer with tests.

## Why not full Kelly?

Full Kelly assumes accurate edge estimation. In live trading, edge is noisy; full Kelly overreacts and produces larger drawdowns than a naïve reader expects. Fractional Kelly is standard practice for practitioners who care about drawdown, which we do (see [`risk-framework.md`](risk-framework.md)).

## Why 25% and not 50%?

A defensible fractional factor is bounded by the operator's tolerance for missed upside vs. drawdown. We chose 25% because:

- The hard cap dominates at typical edges, so a larger fractional factor adds nothing for those candidates.
- For low-edge candidates (where the fractional factor matters most), smaller sizes compound more predictably.
- Post-validation WFV will revisit this choice with real data.

## Why these regime multipliers?

Bull 1.0 is the baseline — we trust the HMM labeling in trending regimes. Chop 0.5 is a mechanical discount for the reduced expected duration of directional moves. Bear 0.3 is deeper than chop because bear regimes are where the engine has historically produced worse outcomes on analogous strategies; a 30% multiplier ensures we are barely in the market.

These numbers are locked during validation. Changing them post-validation is a `risk-logic` PR with two reviewers and tests over fixture regimes.

## How to add or remove a step

You almost certainly don't need to. But if you do:

- **Adding a step that can only reduce size** is acceptable (e.g., a per-symbol volatility clamp). Needs tests and two reviewers.
- **Adding a step that can increase size** is a policy change, not a code change. Requires an explicit design doc and sign-off outside the PR flow.
- **Removing a step** requires showing, with tests over fixtures, that the remaining pipeline produces equivalent or smaller sizes in all cases.

## Testing

Unit tests for the sizer live at `coinscope_trading_engine/tests/test_kelly_position_sizer*.py`. They cover:

- Kelly-full computation for a variety of edge/odds combinations.
- Fractional factor clamp.
- Hard-cap clamp.
- Each regime multiplier.
- Leverage ceiling clamp.
- Step-size rounding.
- The monotone-non-increasing invariant across steps.

When changing the sizer, update these tests. A fixture-over-regimes test is cheap and catches most classes of error.

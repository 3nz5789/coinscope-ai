## Summary

<!-- One sentence: what does this PR do and why? -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change
- [ ] Documentation / config only
- [ ] Risk logic / threshold change ⚠️ (requires 2 reviewers)

## Validation-phase check

> If ANY box below is checked, **stop and close this PR**. Changes wait until validation phase ends.

- [ ] Changes a canonical risk threshold (`MAX_DAILY_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `POSITION_HEAT_CAP_PCT`, `KELLY_FRACTION`)
- [ ] Sets `BINANCE_TESTNET=false`
- [ ] Removes or bypasses a circuit breaker or kill switch
- [ ] Retrains or replaces an ML artifact
- [ ] Changes order submission semantics (entry/stop/TP grouping, reduce-only flags)

## Changes

-
-

## Testing

- [ ] `pytest` passes locally
- [ ] `ruff check .` passes
- [ ] New tests added for new behaviour
- [ ] Smoke tested against Binance testnet (for exchange adapter changes)

## Risk impact

None / [describe]

## Linked issues

Fixes # (issue)

## Checklist

- [ ] Self-reviewed the diff
- [ ] No `.env` file committed
- [ ] `CHANGELOG.md` updated under `## Unreleased`
- [ ] Two reviewers requested (if risk logic / adapter change)

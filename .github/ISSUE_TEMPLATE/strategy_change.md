---
name: Strategy / Risk Change
about: Propose a change to trading logic, risk thresholds, position sizing, regime detection, or ML models
title: "[STRATEGY] <short description>"
labels: "dom: risk, type: research"
assignees: ""
---

> This template is required for any change to risk thresholds, signal scoring, position sizing, circuit breakers, or ML artifacts. Changes in these categories are blocked during P0 validation (through ~May 31, 2026) and require founder sign-off at any phase.

## Summary

## Rationale

## Current behaviour

## Proposed behaviour

## Affected components

- [ ] Canonical risk threshold (`MAX_DAILY_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `POSITION_HEAT_CAP_PCT`, `KELLY_FRACTION`, `KELLY_HARD_CAP_PCT`)
- [ ] Position sizing formula or regime multipliers
- [ ] Stop-loss / take-profit logic or ATR multiplier
- [ ] Signal scoring, confluence weighting, or scoring floor
- [ ] HMM regime classifier or v3 ML model weights/architecture
- [ ] Circuit breaker trip conditions or reset logic
- [ ] Kill switch behaviour
- [ ] Exchange adapter or order submission semantics

## Backtest / validation results

| Metric | Baseline | Proposed | Delta |
|---|---|---|---|
| Win rate | | | |
| Profit factor | | | |
| Max drawdown | | | |
| Daily loss frequency | | | |
| Sharpe ratio | | | |
| Avg R per trade | | | |

## Worst-case analysis

## Validation phase gate

- [ ] This change is blocked during P0 validation and I confirm it will not be merged until validation ends and founder sign-off is given

## Rollback plan

## Required approvals

- [ ] Founder / project owner
- [ ] Second technical reviewer (2-reviewer rule applies)

## Related

<!-- Linear issue (COI-NNN), decision-log entry, or ADR -->

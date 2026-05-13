## Summary

<!-- One sentence: what does this PR do and why? -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (requires migration or callout)
- [ ] Documentation / config only
- [ ] Infra / CI change
- [ ] Risk logic / threshold change (requires 2 reviewers + strategy_change issue)

---

## Validation-phase gate

> **If ANY box below is checked, stop and close this PR.** Open a `strategy_change` issue instead. Changes wait until validation phase ends (~May 31, 2026).

- [ ] Changes a canonical risk threshold (`MAX_DAILY_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `POSITION_HEAT_CAP_PCT`, `KELLY_FRACTION`, `KELLY_HARD_CAP_PCT`)
- [ ] Sets `BINANCE_TESTNET=false` or modifies testnet flag handling
- [ ] Removes or bypasses a circuit breaker or kill switch
- [ ] Retrains, replaces, or modifies ML artifacts or regime model weights
- [ ] Changes order submission semantics (entry/stop/TP grouping, reduce-only flags, order type)

---

## Changes

-
-
-

---

## Testing

- [ ] `pytest -x -q tests/` passes locally
- [ ] `ruff check .` passes
- [ ] `python3 scripts/drift_detector.py` — clean
- [ ] `python3 scripts/risk_threshold_guardrail.py` — clean
- [ ] `python3 scripts/evidence_gate.py` — clean (or `evidence-gate-exempt` label justified below)
- [ ] New tests added for new behaviour
- [ ] Smoke tested against Binance testnet (required for exchange adapter or execution changes)

---

## Evidence trail

> Required if this PR touches `risk_management/`, `engine/exchange/`, `services/paper_trading/safety.py`, `services/paper_trading/kill.py`, `services/paper_trading/order_manager.py`, regime/HMM logic, `coinscope.env.example`, `configs/environments/`, or `CLAUDE.md`. CI's `evidence-gate` job enforces this — see [`scripts/evidence_gate.py`](../blob/main/scripts/evidence_gate.py).

Tick at least one. If none apply, request the `evidence-gate-exempt` label and explain below.

- [ ] Updated the validation proof hub ([`docs/validation/p0-evidence-pack.md`](../blob/main/docs/validation/p0-evidence-pack.md))
- [ ] Updated the Validation Phase Freeze section in [`README.md`](../blob/main/README.md#validation-phase-freeze)
- [ ] Updated `CHANGELOG.md` or `docs/runbooks/release-checklist.md`
- [ ] Added a new evidence record under `docs/validation/`
- [ ] Exempt — justification: <!-- e.g. "pure rename, no behaviour change" -->


---

## Risk impact

None.

---

## Linked issues

Fixes #

---

## Checklist

- [ ] Self-reviewed the diff — no debug code, no commented-out blocks
- [ ] No `.env` file committed
- [ ] Two reviewers requested (if this touches `risk_management/`, `engine/exchange/`, `coinscope.env.example`, `configs/environments/`, or `CLAUDE.md`)
- [ ] `CHANGELOG.md` updated under `## Unreleased` (if user-visible change)

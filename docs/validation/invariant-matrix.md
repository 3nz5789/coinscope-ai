# Invariant-to-Test Matrix

**Status:** active — P0 validation phase
**Audience:** anyone reviewing a PR that touches risk, execution, regime, kill-switch, or threshold code
**Companion docs:** [`p0-evidence-pack.md`](p0-evidence-pack.md) · [`../risk/risk-framework.md`](../risk/risk-framework.md)

## What this matrix is

Every property the engine must never violate — every **invariant** — mapped to:

1. The doc that **declares** it (source of truth)
2. The code **mechanism** that enforces it at runtime
3. The **test or script** that catches a regression
4. The **evidence record** where its outcome is logged

This is the bridge between the proof hub (what was validated) and the codebase (what actually enforces it). A reviewer should be able to read a single row and answer: *which mechanism protects this claim, and what catches a regression?*

## How this connects to the enforcement model

| Layer | What it catches | How |
|---|---|---|
| Drift detector / threshold guardrail | Numeric drift in canonical thresholds | [`scripts/risk_threshold_guardrail.py`](../../scripts/risk_threshold_guardrail.py) — runs in CI `security` job |
| Test suites | Behavioural regressions | `tests/test_ci_smoke.py`, `tests/unit/paper_trading/test_safety.py`, `tests/test_directory_boundaries.py` |
| Evidence gate | PRs that change protector code without an evidence touch | [`scripts/evidence_gate.py`](../../scripts/evidence_gate.py) — runs in CI `evidence-gate` job |
| **Matrix check** (this doc) | Stale citations — a row pointing at a renamed or deleted protector | [`scripts/invariant_matrix_check.py`](../../scripts/invariant_matrix_check.py) — runs in CI `invariant-matrix` job |

The matrix is itself a `docs/validation/**.md` file, so updating it satisfies the evidence-gate requirement when a PR changes a protector. If you rename or delete a protector file, the matrix check fails until you update the corresponding row. The two gates together close the loop: *every protector has a row, every row resolves to real code.*

## Status legend

- 🟢 **Green** — invariant has all four: source-of-truth doc, code mechanism, test/script coverage, evidence row
- 🟡 **Yellow** — partial coverage. The row's `notes` column explains what's missing
- 🔴 **Red** — claim made in a doc but no protector exists on `main`. Tracked for closure

## Matrix

<!-- matrix:begin -->

| ID | Invariant | Status | Source | Code | Test/Script | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| I1 | No trade bypasses the risk gate | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/safety.py` `services/paper_trading/order_manager.py` | `tests/unit/paper_trading/test_safety.py` | `docs/validation/p0-evidence-pack.md` | BUG-10 is the canonical regression; defense-in-depth via workflow step 2 in operator-workflow.md |
| I2 | No size exceeds the 2% per-trade hard cap | 🟢 | `docs/risk/position-sizing.md` | `risk_management/kelly_position_sizer.py` `services/paper_trading/safety.py` `services/paper_trading/config.py` | `tests/unit/paper_trading/test_safety.py` `scripts/risk_threshold_guardrail.py` | `docs/validation/p0-evidence-pack.md` | Hard cap is a code constant, not a config override |
| I3 | A tripped breaker blocks new entries | 🟢 | `docs/risk/failsafes-and-kill-switches.md` | `services/paper_trading/safety.py` | `tests/unit/paper_trading/test_safety.py` | `docs/validation/p0-evidence-pack.md` | Daily-loss, max-drawdown, consecutive-loss breakers covered |
| I4 | Kill switch prevents new entries when engaged | 🟡 | `docs/risk/failsafes-and-kill-switches.md` | `services/paper_trading/safety.py` `services/paper_trading/kill.py` | `tests/unit/paper_trading/test_safety.py` | `docs/validation/p0-evidence-pack.md` | `KillSwitch.deactivate()` is fail-permissive at the method level — CLI gate exists but programmatic callers bypass. Tracked: issue [#47](https://github.com/3nz5789/CoinScopeAI/issues/47), PR [#50](https://github.com/3nz5789/CoinScopeAI/pull/50) in flight |
| I5 | Every gate decision is journaled with a reason | 🟡 | `docs/risk/risk-framework.md` | `services/paper_trading/safety.py` | `tests/unit/paper_trading/test_safety.py` | `docs/validation/p0-evidence-pack.md` | In-memory `rejection_log` covered; on-disk persistence test not yet on `main`. Tracked: issue [#58](https://github.com/3nz5789/CoinScopeAI/issues/58) |
| I6 | Engine halts on uncertain state — never guesses | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/safety.py` | `tests/unit/paper_trading/test_safety.py` | `docs/validation/p0-evidence-pack.md` | Fail-closed `validate_order`; reject is the default branch |
| I7 | P0 runs on Binance Testnet only | 🟢 | `README.md` | `coinscope.env.example` `configs/environments/staging.yaml` | `tests/test_ci_smoke.py` | `docs/validation/p0-evidence-pack.md` | Real-capital trading gate-locked behind PCC v2 §8 |
| I8 | Max leverage is 10× | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/config.py` `coinscope.env.example` `configs/environments/production.yaml` | `tests/test_ci_smoke.py` `tests/unit/paper_trading/test_safety.py` `scripts/risk_threshold_guardrail.py` | `docs/validation/p0-evidence-pack.md` | PCC v2 §8 locked 2026-05-01 |
| I9 | Max open positions is 5 | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/config.py` `coinscope.env.example` | `tests/test_ci_smoke.py` `tests/unit/paper_trading/test_safety.py` `scripts/risk_threshold_guardrail.py` | `docs/validation/p0-evidence-pack.md` | Revised 2026-05-03 (was 3) |
| I10 | Daily loss budget is 5% | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/config.py` `coinscope.env.example` | `tests/unit/paper_trading/test_safety.py` `scripts/risk_threshold_guardrail.py` | `docs/validation/p0-evidence-pack.md` | Triggers automatic kill-switch activation |
| I11 | Max drawdown is 10% | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/config.py` `coinscope.env.example` | `tests/unit/paper_trading/test_safety.py` `scripts/risk_threshold_guardrail.py` | `docs/validation/p0-evidence-pack.md` | Triggers automatic kill-switch activation |
| I12 | Position heat cap is 80% | 🟢 | `docs/risk/risk-framework.md` | `services/paper_trading/config.py` `coinscope.env.example` | `scripts/risk_threshold_guardrail.py` | `docs/validation/p0-evidence-pack.md` | Portfolio-level deployed-capital ceiling |
| I13 | ML / LLM is not imported on the hot path | 🟡 | `README.md` | `tests/test_directory_boundaries.py` | `tests/test_directory_boundaries.py` | `docs/validation/p0-evidence-pack.md` | Boundary tests enforce import isolation, but the canonical ADR (cited as ADR-0003 in `README.md`) is not on `main` — only ADR-0005 exists in `docs/decisions/`. Tracked: issue [#59](https://github.com/3nz5789/CoinScopeAI/issues/59) |
| I14 | Threshold drift is detected before merge | 🟡 | `README.md` | `scripts/risk_threshold_guardrail.py` | `tests/test_ci_smoke.py` `.github/workflows/ci.yml` | `docs/validation/p0-evidence-pack.md` | Guardrail currently runs in warn-mode in CI `security` job (does not fail the build). Tracked: issue [#60](https://github.com/3nz5789/CoinScopeAI/issues/60) |
| I15 | Sensitive PRs touch a canonical evidence destination | 🟢 | `README.md` | `scripts/evidence_gate.py` | `.github/workflows/ci.yml` | `docs/validation/p0-evidence-pack.md` `.github/PULL_REQUEST_TEMPLATE.md` | The rule the matrix itself depends on |
| I16 | Invariant-to-test citations resolve to real files | 🟢 | this file | `scripts/invariant_matrix_check.py` | `.github/workflows/ci.yml` | this file | Self-check: matrix integrity |

<!-- matrix:end -->

## Adding or changing an invariant

1. **Edit the table above.** Use a new `I<n>` ID. Cite all four columns. Quote paths in backticks.
2. **Pick a status honestly.** 🟡 with a clear note is better than 🟢 you can't defend.
3. **Verify locally:** `python3 scripts/invariant_matrix_check.py`.
4. **Submit.** The `invariant-matrix` CI job re-runs the check; the `evidence-gate` CI job confirms that any code change in the same PR is accompanied by this matrix update (or another evidence destination).

## Tracking issues

Every 🟡 and 🔴 row carries a tracking issue in its **Notes** column. This is mandatory, not optional. A finding without a tracking issue is unowned, undated, and unactionable — exactly the kind of soft assertion this matrix exists to prevent.

When adding a new 🟡 or 🔴 row:

1. File a GitHub issue using the shape established by [#47](https://github.com/3nz5789/CoinScopeAI/issues/47), [#58](https://github.com/3nz5789/CoinScopeAI/issues/58), [#59](https://github.com/3nz5789/CoinScopeAI/issues/59), [#60](https://github.com/3nz5789/CoinScopeAI/issues/60). The body must declare: Source · Phase · Owner · Due · Target state · Evidence artifact · Done-when checklist.
2. Cite the issue number in the Notes column: `Tracked: issue #N`.
3. The matrix-check CI job does not enforce this convention (it only verifies cited paths exist); reviewer judgement is responsible.

## Closing a Yellow or Red row

A row stays 🟡 or 🔴 until **all three** are true:

- The missing protector exists on `main` (test added, persistence wired, breaker promoted from warn to fail, ADR ported, etc.)
- The tracking issue in Notes is closed.
- The corresponding row in [`p0-evidence-pack.md`](p0-evidence-pack.md) §0 is updated to reflect the closure.

When all three are true, flip the status to 🟢 in the same PR that lands the protector. The matrix-check enforces the path resolution; reviewer judgement is responsible for the status colour and the issue-closure check.

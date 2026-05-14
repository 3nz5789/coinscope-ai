# CoinScopeAI — P0 Validation Summary

> A one-page status artifact for anyone outside the team. What is live, what is testnet only, what is blocked, what has passed, what has not.

| Field | Value |
|---|---|
| **Phase** | P0 — testnet validation, May 2026 |
| **Validation environment** | Binance USDT-M Testnet |
| **Real-capital trading** | Gated off behind a locked configuration |
| **Snapshot version** | matches release [`v0.1.0-p0.3`](https://github.com/3nz5789/CoinScopeAI/releases/tag/v0.1.0-p0.3) (2026-05-13) |
| **Updated** | 2026-05-13 |

The internal evidence pack ([`p0-evidence-pack.md`](p0-evidence-pack.md) §0) is the source of truth. When this page disagrees with that document, that document wins.

---

## What is live

| Component | State | Notes |
|---|---|---|
| Engine API (FastAPI) | ✅ Running | 40+ endpoints — `/health`, `/scan`, `/risk-gate`, `/position-size`, `/regime/{symbol}`, `/journal`, `/performance`, and more |
| Telegram alerts (`@ScoopyAI_bot`) | ✅ Running | Threshold: confluence ≥ 8.0 |
| Dashboard at `app.coinscope.ai` | ✅ Running | Read-only operator view |
| Six-layer risk gate | ✅ Active | Signal quality · pre-trade gate · Kelly sizer · execution guardrails · circuit breakers · kill switch |
| Kelly position sizer | ✅ Active | 0.25× fractional Kelly · 2% per-trade hard cap · regime-scaled |
| HMM regime classifier | ✅ Active | Bull / chop / bear with explicit multiplier table |
| Trade journal | ✅ Active | Every gate decision and trade recorded |
| Continuous integration | ✅ Green | 45+ tests across smoke, unit, and boundary suites; runs on every push to `main` |

## What is testnet only

Every trade the system has ever placed is on **Binance USDT-M Testnet**. No real funds have been at risk during P0. Three independent locks keep it that way:

1. The environment flag `BINANCE_TESTNET=true` is the only configuration present on the `main` branch.
2. The seven canonical risk thresholds (max leverage, max drawdown, daily-loss budget, position-heat cap, per-trade size cap, Kelly fraction, max open positions) are immutable during P0 — any pull request that changes one is blocked at CI.
3. Mainnet API keys are not present in the deployed environment.

Real-capital trading requires every item under "What is blocked" to clear, plus an explicit operator-signed change of the testnet flag. None of that has happened.

## What has passed

- ✅ **16 pre-flight bugs resolved.** Every issue surfaced before P0 is fixed and documented.
- ✅ **15-test CI smoke suite green** on every push to `main`.
- ✅ **30 directory-boundary tests** enforce that machine-learning and LLM modules cannot be imported on the trade-decision path.
- ✅ **~360 lines of safety-gate unit tests** covering every rejection class — kill switch, hardcoded limits, configurable limits, state checks, consecutive-loss cooldown, daily-loss and drawdown auto-activation.
- ✅ **API contract published** — 40+ endpoints documented.
- ✅ **SLO and alerting specification published.**
- ✅ **Risk framework documented on `main`** — philosophy, gate logic, position sizing, failsafes (four canonical docs).
- ✅ **Operator session-lifecycle runbook** documented.
- ✅ **Validation evidence pack** with an explicit honesty-pass section that maps every claim to its backing artifact.

## What is blocked

P0 does not graduate to P1 until these flip:

| Item | Status | Type |
|---|---|---|
| 65 invariant tests merged to `main` | In flight on a side branch | Code |
| Walk-forward + CPCV reproducibility harness merged to `main` | In flight | Code |
| Kill-switch deactivate path hardened against programmatic bypass | In flight | Code |
| Operator deployment: VPS environment patch + post-restart verification | Pending operator action | Operator |
| Threshold-drift CI guardrail promoted from warn-mode to fail-mode | Pending | Infrastructure |
| Hot-path import ban — canonical decision doc (boundary tests already enforce the rule) | Pending | Docs |
| Gate-decision journaling: on-disk persistence test | Pending | Test |

Every item is scoped, owned, and tracked in the public issue tracker. Target closure: late May – mid June 2026.

## What has not

These are explicit non-claims. If a reader infers any of them from our material elsewhere, the material is wrong, not these statements.

- ❌ **Real-capital trading.** Not validated. Not in scope for P0.
- ❌ **Mainnet execution.** Not enabled. Will require a separate validation phase before activation.
- ❌ **Multi-exchange support (Bybit and others).** Design-only until P2 (August–September 2026).
- ❌ **Walk-forward validation results reproducible from this repository.** Earlier reports cited 9-fold WFV numbers; those were produced by external preliminary analysis. The runner that reproduces them from code in this repository is in flight, not yet merged.
- ❌ **Dashboard authentication beyond a demo state.** Not in P0 scope.
- ❌ **Kill-switch deactivate path is not yet method-level fail-closed.** A CLI confirmation prompt exists, but a programmatic caller can bypass it. Hardening is in flight. Until that lands, treat the deactivate path as advisory.
- ❌ **Investment advice or fund management.** CoinScopeAI is a signal-scoring and risk-gate engine. It does not place autonomous trades and does not manage funds on anyone's behalf.

---

## Where to read more

| Audience | Document |
|---|---|
| Anyone | [Disclosures](https://app.coinscope.ai/legal) |
| Reviewers and approvers | [`p0-evidence-pack.md`](p0-evidence-pack.md) — definitive list of what we can and cannot prove; §0 (honesty pass) overrides the rest of the body |
| Engineers and auditors | [`invariant-matrix.md`](invariant-matrix.md) — every system invariant mapped to the code and test that protects it, with status colour |
| Operators | [`../runbooks/operator-workflow.md`](../runbooks/operator-workflow.md) — 9-step session lifecycle |
| Contributors | [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) |

---

## How this page stays accurate

This summary is hand-curated and refreshed at each tagged release. It is **not** auto-generated — automated status pages drift silently. Instead, the discipline is:

- Every claim above is backed by a section of [`p0-evidence-pack.md`](p0-evidence-pack.md) or a row in [`invariant-matrix.md`](invariant-matrix.md).
- A continuous-integration check verifies that every file path cited by the invariant matrix exists on `main`. The matrix cannot lie about what code exists.
- A second CI check requires that any pull request changing risk, execution, or threshold code also updates one of the canonical evidence destinations. Changes to the system cannot land without a corresponding change to the proof.

If you find a discrepancy between this page and what is on `main`, open an issue — the discrepancy is the bug.

# Release Checklist

**Status:** current
**Audience:** the operator deploying any change to the engine
**Related:** [`daily-ops.md`](daily-ops.md), [`../testing/local-validation-checklist.md`](../testing/local-validation-checklist.md), [`../ops/binance-adapter.md`](../ops/binance-adapter.md)

Every deploy to the production-candidate VPS runs through this list. During validation (2026-04-10 → 2026-04-30), most items below default to "no" — the engine is explicitly frozen.

## Before opening the PR

- [ ] Tests pass locally (`pytest`).
- [ ] Lint passes (`ruff check .`).
- [ ] Type check passes (if the touched file already has annotations, keep them correct).
- [ ] Changelog entry added to `CHANGELOG.md` under `## Unreleased`.
- [ ] If touching risk logic, sizing, the gate, or an adapter: **two reviewers** requested, per `CONTRIBUTING.md`.
- [ ] If touching a feature contract or ML artifact path: the matching artifact is committed or retrievable from `./scripts/fetch_ml_artifacts.sh`.

## Validation-window blockers

During the 30-day window, these conditions **force a stop**. Do not proceed with the deploy if any is true:

- [ ] PR changes any core engine risk threshold (`MAX_DAILY_LOSS_PCT`, `MAX_DRAWDOWN_PCT`, `MAX_LEVERAGE`, `MAX_OPEN_POSITIONS`, `POSITION_HEAT_CAP_PCT`, `KELLY_FRACTION`, `KELLY_HARD_CAP_PCT`, regime multipliers).
- [ ] PR flips `BINANCE_TESTNET` to `false`.
- [ ] PR removes or bypasses a circuit breaker.
- [ ] PR retrains or replaces an ML artifact.
- [ ] PR changes order submission semantics (entry/stop/TP grouping, reduce-only flags).

If any box above is checked, close the PR. The change waits until 2026-05-01.

## Before the merge

- [ ] CI is green on the PR branch.
- [ ] At least one reviewer approved (two for risk-logic / execution / adapter changes).
- [ ] No unresolved comments.
- [ ] The merge commit message follows the repo convention (`<scope>: <summary>`).

## Before the deploy

- [ ] On a quiet window. Don't deploy during a regime flip if you can see one about to happen.
- [ ] Current engine `/ready` returns 200. Deploying on top of a broken engine hides the cause.
- [ ] Local smoke test of the packaged release:
  ```
  ./scripts/smoke.sh <release-tag>
  ```
  This runs a minimal boot + `/health` + `/ready` check against the built image.
- [ ] Kill switch is engaged **before** the deploy, then released after health checks pass.
  ```
  curl -X POST https://<engine-host>/kill-switch -d '{"engage":true,"reason":"pre-deploy"}'
  ```
- [ ] Open positions acknowledged. A deploy with open positions is fine (stops and TPs are on the exchange) but the operator should *know*.

## During the deploy

- [ ] Pull the release tag on the VPS.
- [ ] `docker compose up -d` (zero-downtime is not a feature; a 10-second gap is acceptable and intentional).
- [ ] Wait for `/health` to return 200.
- [ ] Wait for `/ready` to return 200 with all adapters reporting healthy.
- [ ] Release the kill switch:
  ```
  curl -X POST https://<engine-host>/kill-switch -d '{"engage":false,"reason":"post-deploy verified"}'
  ```

## After the deploy

- [ ] First candidate arrives and is evaluated (check `/journal?event_type=gate_decision&limit=5`). A gate decision — accept or reject — is the signal the loop is alive.
- [ ] No new `engine_adapter_rest_errors_total{status="5xx"}` increments in the first 5 minutes.
- [ ] No unexpected Telegram alerts.
- [ ] Operator-log entry written:
  ```
  2026-04-18 15:03 UTC — deployed <tag> (<short description>). /ready healthy. Kill switch released. Journal confirms loop active.
  ```

## Rollback

If post-deploy checks fail:

1. Engage the kill switch immediately.
2. Pull the previous release tag on the VPS.
3. `docker compose up -d` with the old tag.
4. Verify `/health`, `/ready`, and journal activity.
5. Release the kill switch.
6. Open an incident at `docs/incidents/incident-deploy-rollback-<YYYY-MM-DD>.md` describing what failed and why.

Rollback is not a fallback — it's the plan. Any deploy that can't be rolled back in five minutes is not ready.

## Mainnet cutover (NOT during validation)

This block is reference only. Do not execute during the validation window.

- [ ] 30-day testnet validation complete with signed-off review.
- [ ] Risk controls fired during validation in the expected ways (at least one daily-loss trip, at least one reconnect recovery, at least one regime flip handled without incident).
- [ ] Mainnet API keys provisioned on the operator's account with minimum-necessary permissions (trade + read; no withdrawals).
- [ ] Starting-equity floor set (`MAX_EQUITY_AT_RISK_USD`) — a hard cap on exposure for the first week of mainnet.
- [ ] Scale-up schedule committed to in writing (see [`../product/implementation-backlog.md`](../product/implementation-backlog.md) — mainnet scale-up spec).
- [ ] Operator is available for the first 24 hours post-cutover.
- [ ] `BINANCE_TESTNET=false` set, deploy executed following the standard flow above.

Mainnet cutover is a one-way door in practice (funded capital is at risk). Treat it accordingly.

## Things that are not on this list on purpose

- **"Load tests pass."** The engine runs one trading loop on modest hardware; realistic load is already production load.
- **"Feature flag rollout."** We do not use a feature-flag system. Every change lands behind config defaults instead.
- **"Canary deploy."** We run one engine process. A canary is not meaningful for single-node deployments.

These will become real items if and when the architecture grows to need them. Today they would be ceremony.

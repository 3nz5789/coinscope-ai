# Local Validation Checklist

**Status:** current
**Audience:** developers verifying their work before opening a PR
**Related:** [`testing-strategy.md`](testing-strategy.md), [`../runbooks/local-development.md`](../runbooks/local-development.md), [`../runbooks/release-checklist.md`](../runbooks/release-checklist.md)

What to check locally before pushing. Different from the release checklist: this is pre-PR, that is pre-deploy. Short enough to run every time.

## Always

- [ ] `pytest -x -q` passes.
- [ ] `ruff check .` clean.
- [ ] No uncommitted changes to `.env.example` that are actually personal overrides.
- [ ] The change has at least one test, unless it's pure docs.

## If you touched the risk pipeline (gate, sizer, breakers)

- [ ] `pytest -x -q coinscope_trading_engine/tests/test_risk_gate.py coinscope_trading_engine/tests/test_kelly_position_sizer.py` passes.
- [ ] Manually confirm the monotone-non-increasing invariant still holds against a couple of (edge, regime) combos you pick by hand.
- [ ] If you changed thresholds or multipliers, **stop** — these are locked during validation.

## If you touched the adapter or streams

- [ ] Adapter unit tests pass.
- [ ] Smoke test against testnet:
  ```
  python -m scripts.binance_adapter_smoke --symbols BTCUSDT --duration 30
  ```
  Confirm no reconnects, no gaps, no rate-limit hits, and that normalization counts match stream subscriptions.
- [ ] If you changed normalization shape: update fixtures under `tests/fixtures/binance/`.

## If you touched ML

- [ ] Inference tests pass.
- [ ] If you changed the feature contract: the matching artifact is committed or retrievable via `./scripts/fetch_ml_artifacts.sh`.
- [ ] Boot test: `python -m coinscope_trading_engine.app --dry-run` loads both regime artifacts without error.

## If you touched billing

- [ ] Webhook signature verification test passes.
- [ ] Idempotency test passes.
- [ ] Local stripe CLI replay works:
  ```
  stripe trigger checkout.session.completed
  curl localhost:8001/billing/me
  ```
  The response should reflect the new subscription.

## If you touched the API surface

- [ ] `curl localhost:8001/openapi.json | jq '.paths | keys'` includes the route you added and not the one you removed.
- [ ] Manual `curl` of the changed endpoint with realistic payloads returns the expected shape.
- [ ] Error envelope uses one of the standardized codes in [`../api/api-overview.md`](../api/api-overview.md), not a free-form string.

## If you touched alerts

- [ ] Dry-run: `TELEGRAM_DRY_RUN=true python -m scripts.telegram_smoke` shows the exact rendered message.
- [ ] Throttle test passes.
- [ ] The trigger table in [`../ops/telegram-alerts.md`](../ops/telegram-alerts.md) is updated to include the new alert type.

## If you touched configuration (new env var)

- [ ] Added to `.env.example` with a comment explaining purpose and default.
- [ ] Documented in [`../backend/configuration.md`](../backend/configuration.md).
- [ ] `python -m coinscope_trading_engine.app --check-config` reports no missing required vars.

## Pre-push sanity

- [ ] `git status` — no stray test outputs or local dumps being committed.
- [ ] `git log --oneline -5` — commit messages are descriptive and scoped.
- [ ] Branch name matches the work (`feat/<scope>`, `fix/<scope>`, `docs/<scope>`).

## What you should not do locally

- **Do not run the test suite against production Stripe keys.** Use test-mode keys.
- **Do not run integration tests against mainnet Binance.** Testnet or fixtures only.
- **Do not commit `.env`.** Pre-commit enforces, but check anyway.
- **Do not rely on "it worked on my machine" for race conditions.** If you suspect a race, add a test that reproduces it first, then fix.

## The one-line sanity check

```
pytest -x -q && ruff check . && echo "ship it"
```

If that ends with `ship it`, you've cleared the local bar. The PR review will catch the rest.

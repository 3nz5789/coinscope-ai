# Local Development Runbook

**Status:** current
**Audience:** developers running the stack locally
**Related:** [`../onboarding/new-developer-guide.md`](../onboarding/new-developer-guide.md), [`../backend/configuration.md`](../backend/configuration.md), [`../ops/stripe-billing.md`](../ops/stripe-billing.md)

Day-to-day: how to bring up, tear down, iterate, and debug the engine on your laptop. Starting-from-scratch setup is in [`../onboarding/new-developer-guide.md`](../onboarding/new-developer-guide.md); this doc assumes you already have a working environment.

## The standard dev loop

```bash
# 1. Pull latest and activate the venv
git pull
source .venv/bin/activate

# 2. Start Redis and Postgres (if using)
docker compose up -d redis

# 3. Start the API
uvicorn coinscope_trading_engine.app:app --reload --port 8001

# 4. In a second terminal, start the Celery worker
celery -A coinscope_trading_engine.celery_app worker --loglevel=info

# 5. In a third terminal, run the trading loop (if needed)
python -m coinscope_trading_engine.main

# 6. Verify
curl localhost:8001/health
curl localhost:8001/ready
```

If `/ready` returns non-200, something isn't wired up. Check the order you booted services (Redis before API), then check `.env`.

## What you usually don't need to run

- **The trading loop** — if you're only touching API or docs, skip step 5.
- **The Celery worker** — if you're not testing async tasks (journaling, alpha-decay windowing, alerts), skip step 4.
- **Postgres** — if `BILLING_DB_URL` is pointing at the default SQLite file, no Postgres is needed for local work.
- **Prometheus and Grafana** — only bring them up if you're specifically testing metrics output.

The reload flag on `uvicorn` re-imports on file changes. If a reload doesn't pick up a change, kill and restart (especially after edits to `__init__.py` or `config.py`).

## Hot-reloading caveats

- **`uvicorn --reload` does not reload the worker.** If you change code in a task, restart the Celery worker manually.
- **Schema changes in `config.py`** require a full restart, even with `--reload`.
- **WebSocket connections to Binance survive reloads inconsistently.** If you change adapter code, fully restart — do not trust reload.

## Talking to testnet from your laptop

Testnet is open to the internet; no VPN required. Set:

```
BINANCE_TESTNET=true
BINANCE_API_KEY=<your testnet key>
BINANCE_API_SECRET=<your testnet secret>
```

Keys are obtained from the Binance testnet UI. **Never paste a mainnet key into `.env`.** A pre-commit check refuses to commit an `.env` file at all, but a misplaced key on your machine is still a leak vector.

To verify the adapter works without starting the full engine:

```bash
python -m scripts.binance_adapter_smoke --symbols BTCUSDT --duration 30
```

See [`../ops/binance-adapter.md`](../ops/binance-adapter.md) for the full adapter isolation workflow.

## Stripe webhooks locally

```bash
stripe listen --forward-to localhost:8001/billing/webhook
```

Copy the `whsec_...` value Stripe CLI prints into your local `.env` as `STRIPE_WEBHOOK_SECRET`, then trigger events:

```bash
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
```

Verify:

```bash
curl localhost:8001/billing/me
```

Full details in [`../ops/stripe-billing.md`](../ops/stripe-billing.md).

## Running tests

```bash
# Fast: unit tests only
pytest -x -q coinscope_trading_engine/tests

# Full suite (unit + integration; requires Redis up)
pytest

# Specific test file
pytest coinscope_trading_engine/tests/test_kelly_position_sizer.py -v

# With coverage
pytest --cov=coinscope_trading_engine --cov-report=term-missing
```

The `-x` flag stops on first failure, which is what you usually want during iteration. Flaky tests are catalogued in [`../testing/testing-strategy.md`](../testing/testing-strategy.md); known flakes should be fixed, not retried.

## Common gotchas

### "Redis connection refused"

Celery or the app can't reach Redis. Either Docker Compose didn't start Redis, or it's on a different port. Run `docker compose ps` and `docker compose logs redis`.

### "ImportError: cannot import name X"

Usually a circular import. The engine has layered modules: don't import upward (e.g., `data/` should not import from `execution/`). If you hit this, look at the import in the offending file first.

### "Stale feature contract"

ML inference fails with a feature-shape mismatch. You probably pulled changes that bumped the feature list without re-downloading the matching artifact. Pull the artifact: `./scripts/fetch_ml_artifacts.sh`.

### "Clock skew too large" at adapter boot

Your laptop's clock drifted. Run `sudo sntp -sS time.apple.com` on macOS, or enable NTP. Binance enforces a hard skew limit.

### Port 8001 already in use

Previous `uvicorn` didn't exit cleanly: `lsof -i :8001` then `kill <pid>`. Or use `--port 8002` and remember to update the dashboard's API base.

### "Kill switch engaged" on a fresh boot

Breaker state is persisted. If the last session left the switch engaged, the engine boots with it still on. Disengage it deliberately:

```bash
curl -X POST localhost:8001/kill-switch -d '{"engage": false, "reason": "local dev restart"}'
```

**Do not** clear state files to work around this. The persistence is intentional (see [`../risk/failsafes-and-kill-switches.md`](../risk/failsafes-and-kill-switches.md)).

## Resetting local state

When local state is too corrupted to debug:

```bash
# Stop everything
pkill -f uvicorn
pkill -f celery
docker compose down

# Wipe local DBs
rm -f billing_subscriptions.db billing_subscriptions.db-journal
rm -rf data/journal.sqlite*

# Fresh start
docker compose up -d redis
./scripts/bootstrap_local.sh
```

The bootstrap script re-creates the schema. **Never** run this against a non-local database.

## Debugging tips

- **The journal is your friend.** `GET /journal?event_type=gate_decision&limit=50` shows the last 50 gate decisions with reasons. Most "why didn't this trade fire" questions end here.
- **Prometheus at `/metrics`** is available locally. You don't need a scraper to look at it — `curl localhost:8001/metrics | grep engine_`.
- **Celery task failures are in the worker's stdout.** If you don't see the failure in the API log, it's probably in the worker log.
- **Reproducibility matters.** If a bug only appears "sometimes," capture the trigger state (journal events around it) before tearing down.

## Editor and tooling

- `ruff` and `black` are configured via `pyproject.toml`. Pre-commit runs them; CI enforces them.
- `mypy` is not currently enforced but is recommended. Type hints in new code are expected.
- Use `.env.local` for personal overrides (gitignored). The committed `.env.example` is the source of truth for what vars exist.

## What to avoid

- **Never run the test suite against live Binance.** Integration tests target testnet or replay fixtures.
- **Never point your local stack at production Stripe.** Test-mode keys only.
- **Never commit `.env`.** The pre-commit hook enforces this, but double-check before pushing.
- **Do not add `-k` or `--lf` flags to CI config to skip flakes.** Fix the flake or skip-and-ticket.

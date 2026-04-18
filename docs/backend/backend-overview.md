# Backend Overview

**Status:** current
**Audience:** developers working on or around the engine's HTTP, worker, or persistence layers
**Related:** [`configuration.md`](configuration.md), [`../api/api-overview.md`](../api/api-overview.md), [`../architecture/system-overview.md`](../architecture/system-overview.md)

This page describes the backend processes, their responsibilities, and the runtime dependencies they rely on. Reading it before touching `api/`, `worker/`, or the persistence layer will save review cycles.

## Process topology

In production and in local-development mode, three processes run alongside each other.

| Process | Command | Role |
| --- | --- | --- |
| **API** | `uvicorn coinscope_trading_engine.api.main:app --port 8001` | Serves the HTTP surface read by the dashboard and operators. |
| **Worker** | `celery -A coinscope_trading_engine.worker.celery_app worker` | Runs periodic scans, regime refreshes, journal flushes. |
| **Trading loop** | embedded in the API process today | Drives ingest → signal → gate → execute. |

The trading loop and the API process share memory today. Splitting the loop into its own process is a post-validation refactor (see [`../architecture/future-state-roadmap.md`](../architecture/future-state-roadmap.md)).

## Runtime dependencies

| Dependency | Purpose | Local default | Production |
| --- | --- | --- | --- |
| Python 3.11+ | Engine runtime | system / venv | container image |
| Redis | Celery broker + lightweight cache | `docker compose up redis` | managed Redis on VPS |
| SQLite | Journal storage (default) | `./journal.db` | not used in production |
| Postgres | Journal storage (production) | optional local container | managed Postgres |
| Prometheus | Metrics scraping | `prometheus.yml` in repo root | managed Prometheus |

Nothing else is required at runtime. In particular:

- **No Kubernetes.** Deployment is Docker Compose on a VPS. See [`../runbooks/digitalocean-deployment.md`](../runbooks/digitalocean-deployment.md).
- **No GPU.** The ML stack is classical (scikit-learn + hmmlearn + xgboost).
- **No external ML inference service.** Models load from local artifacts at boot.
- **No LLM on the hot path.** See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).

## The API process

### Framework

FastAPI on uvicorn. See [`../decisions/adr-0001-fastapi-and-uvicorn.md`](../decisions/adr-0001-fastapi-and-uvicorn.md) for why.

### App surface

- **Read-only endpoints** for dashboard display and operator inspection. See [`../api/backend-endpoints.md`](../api/backend-endpoints.md).
- **Billing endpoints** for the Stripe webhook and entitlement lookups. See [`../ops/stripe-billing.md`](../ops/stripe-billing.md).
- **Health endpoint** (`/health`) used by the operator and by any external uptime monitor.

### Lifespan and startup

At boot the app:

1. Loads configuration via `pydantic-settings`.
2. Fails loudly if required env vars are missing (Binance keys, regime artifact paths, journal URL).
3. Loads regime model artifacts from disk.
4. Connects to Redis and Postgres (or opens the SQLite file).
5. Starts the trading loop tasks (Binance WS subscribe, regime refresh, scan cadence).
6. Registers the Prometheus metrics collector.
7. Begins accepting HTTP requests.

Any failure in steps 1–4 crashes the boot. This is deliberate: a silently-degraded engine is worse than one that refuses to start.

### Request model

- JSON in, JSON out. No HTML rendering.
- CORS is configured for the dashboard origin (`https://coinscope.ai/`).
- Errors follow the shape in [`../api/api-overview.md`](../api/api-overview.md).

### Authentication

- Dashboard and operator calls are authenticated by a bearer token read from an env var (`API_AUTH_TOKEN`), scoped to the expected origin.
- The Stripe webhook endpoint validates the Stripe signature header, not the bearer token.
- Billing/premium endpoints additionally gate on entitlement lookups.

## The worker process

### Framework

Celery with Redis broker.

### What the worker does

- **Scheduled scans** on a cron-like cadence defined in Celery Beat.
- **Regime refresh** for both HMM and v3, on a slower cadence than scans.
- **Journal flush** from in-memory / SQLite hot buffer to Postgres when configured.
- **Stale-position sweep** that reconciles exchange state against the journal.
- **Billing reconciliation** (post-webhook) to catch any missed Stripe events.

### What the worker deliberately does not do

- It does not place orders. The executor runs in the API/loop process.
- It does not accept HTTP requests. All work is enqueued from the API process.

### Failure handling

- Tasks are idempotent by design — the journal writer deduplicates on `(timestamp, event_id)`.
- Redis outage pauses scheduled work; scans resume when Redis returns. The trading loop itself is not dependent on Celery for synchronous decisions.

## Persistence

### The journal

Append-only log of every engine decision. The schema is documented alongside the code in `coinscope_trading_engine/journal/`.

Storage backend is chosen by `DATABASE_URL`:

- `sqlite:///./journal.db` — local dev default. Single-writer, no network dependency.
- `postgresql+psycopg://...` — production. Supports concurrent reads and survives process restarts cleanly.

Migrations are explicit scripts, not Alembic auto-migrations, during validation. Post-validation we will adopt a lighter-weight migration tool.

### Entitlements

Stripe subscription state lives either alongside the journal or in a separate `billing_subscriptions.db` SQLite file depending on which entry point wrote it last (a known tech-debt item in [`../ops/stripe-billing.md`](../ops/stripe-billing.md)). Both are read-through for entitlement decisions; the authoritative source is Stripe.

### Model artifacts

Regime models and any xgboost scorers live as `.pkl` / `.joblib` files. Paths are env-configured. A missing artifact is a boot-time failure, not a runtime silent fallback.

## Configuration

All configuration reads from environment variables, via `pydantic-settings`. A missing required variable is a boot-time failure. Full list: [`configuration.md`](configuration.md).

Conventions:

- Env vars are uppercase with underscores.
- Percent values are numeric (5.0 means 5%) and documented in the comment next to the variable.
- Currency values are always USDT.
- Booleans use `true` / `false` (lowercase) in the `.env`.

## Logging

- `logging.getLogger(__name__)` everywhere.
- No `print` in engine or API code — it's a PR-blocker in review.
- JSON-formatted logs in production; human-readable in local dev.
- Sensitive values (API keys, Stripe secrets, bearer tokens) are explicitly redacted by the logger's formatter.

## Metrics

- Exposed at `/metrics` on the same port as the API.
- Collected by the local Prometheus (`prometheus.yml`) in development and by managed Prometheus in production.
- Key metric families: `engine_gate_decisions_total`, `engine_order_lifecycle_seconds`, `engine_regime_flips_total`, `engine_circuit_breaker_trips_total`.

## Where to look next

- HTTP contract: [`../api/api-overview.md`](../api/api-overview.md) and [`../api/backend-endpoints.md`](../api/backend-endpoints.md).
- Env-var reference: [`configuration.md`](configuration.md).
- How the engine decides anything: [`../architecture/data-flow.md`](../architecture/data-flow.md).
- How we deploy: [`../runbooks/digitalocean-deployment.md`](../runbooks/digitalocean-deployment.md).

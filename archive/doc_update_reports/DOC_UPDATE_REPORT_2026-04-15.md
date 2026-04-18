# CoinScopeAI — Documentation Update Report
**Date:** 2026-04-15
**Task:** Scheduled documentation review and update
**Files changed:** CoinScopeAI-Context.md, README.md

---

## Summary

Compared repository state against the previous doc pass (2026-04-14). The following new files were introduced since then, all part of an **expanded Stripe billing integration** — moving from a "stub with JSON sidecar" to a production-grade billing system with real database persistence, entitlements enforcement, customer portal, and Telegram notifications. QA confirmed 80/80 tests passing with 3 bug fixes applied.

### New files since 2026-04-14

```
billing/
├── entitlements.py            ← Per-tier feature gate system (new)
├── subscription_store.py      ← SQLite-backed SubscriptionStore (new)
├── pg_subscription_store.py   ← Async PostgreSQL store (new)
├── notifications.py           ← BillingNotifier — Telegram billing alerts (new)
├── customer_portal.py         ← Portal session API (new)
├── webhook_handler.py         ← Production webhook handler / billing FastAPI app (new)
└── migrations/
    └── 001_initial_billing_tables.sql  ← Postgres schema migration (new)
billing_server.py              ← Entry point for standalone billing service (new)
billing_subscriptions.db       ← Live SQLite subscription store (generated)
dashboard/
├── pricing.html               ← Frontend pricing page (new)
└── billing_success.html       ← Post-checkout success page (new)
docs/
├── BILLING_Stripe_Setup_Runbook.md   ← Step-by-step Stripe setup guide (new)
└── QA_BILLING_COI39_2026-04-15.md   ← QA report: 80/80 tests pass (new)
scripts/
└── setup_stripe_test_products.py     ← Stripe test product creator (new)
tests/
├── test_billing_webhook.py    ← 80 webhook tests (new)
├── test_billing_schema.py     ← Pydantic schema tests (new)
└── test_billing_portal.py     ← Portal API tests (new)
```

---

## Changes Made

### 1. CoinScopeAI-Context.md

**a) Updated metadata**
- `Last updated`: 2026-04-14 → 2026-04-15

**b) Expanded Repository Layout — billing/**
Added all new billing module files:
- `webhook_handler.py` (new main billing FastAPI app)
- `customer_portal.py` (portal session endpoints)
- `subscription_store.py` (SQLite CRUD + idempotency)
- `pg_subscription_store.py` (asyncpg Postgres store)
- `entitlements.py` (tier feature gates)
- `notifications.py` (Telegram billing alerts)
- `migrations/001_initial_billing_tables.sql`

Added new root-level files:
- `billing_server.py`
- `dashboard/` (pricing.html, billing_success.html)
- `docs/` (runbook, QA report)
- `scripts/setup_stripe_test_products.py`

**c) Updated Billing API Reference**
The standalone service (port 8002) now documents all 7 endpoints:

| New endpoint | Description |
|---|---|
| `GET /billing/subscriptions` | List all active/trialing subscriptions |
| `POST /billing/portal/session` | Create portal session by customer_id or email |
| `GET /billing/portal/config` | Check Stripe portal configuration status |

**d) Replaced plain Pricing Tiers table with Entitlements matrix**
Full per-feature breakdown across all 4 tiers (symbols, scan interval, alerts, API rate limits, feature flags, team seats).

**e) Updated webhook events table**
- Noted idempotency deduplication via `webhook_events` table
- Noted `WEBHOOK_SECRET` lazy-read bug fix

**f) Updated Billing open issues**
- Issue #8 (subscription fulfilment stub): **RESOLVED** — `SubscriptionStore.upsert_subscription()` now writes to DB
- Issue #9 (Customer Portal config): **UPDATED** — `GET /billing/portal/config` now surfaces config status
- Added Issue #10: Stripe products not yet created in live account (ACTION REQUIRED)

**g) Updated Development Status table**
```
| Billing fulfilment (user DB write) | ✅ Complete — SQLite + Postgres stores, idempotent |
| Entitlements engine (per-tier feature gates) | ✅ Complete — added 2026-04-15 |
| Customer Portal integration | ✅ Complete (test mode) — added 2026-04-15 |
```

---

### 2. README.md

**a) Expanded billing/ in Architecture tree**
All 9 new billing module files added with inline descriptions.

**b) Added root-level additions block**
`billing_server.py`, `dashboard/`, `docs/`, `scripts/` documented.

**c) Updated API Reference table**
4 new billing endpoint rows (3 portal endpoints + subscriptions list), annotated with `(port 8002)` to distinguish from engine endpoints.

**d) Updated Billing — Architecture subsection**
- Described `SubscriptionStore` / `PgSubscriptionStore` swap pattern
- Described entitlements middleware pattern
- Noted idempotency guarantee

**e) Updated Pricing Tiers table**
Key entitlements per tier (symbols, scan interval, alerts, API rpm).

**f) Updated Setup steps**
- Changed script path from `coinscope_trading_engine/setup_stripe_products.py` to `scripts/setup_stripe_test_products.py`
- Changed `uvicorn billing.stripe_checkout:app` to `uvicorn billing.webhook_handler:app`
- Added `open dashboard/pricing.html` step

**g) Added billing test run command**
```bash
pytest tests/test_billing_webhook.py tests/test_billing_schema.py tests/test_billing_portal.py -v
```

**h) Updated Roadmap**
Added 4 new completed items:
- Subscription persistence (SQLite + Postgres stores)
- Entitlements system
- Billing notifications
- Customer portal integration

---

## New Features Documented This Week

### 1. Entitlements Engine (`billing/entitlements.py`)

A complete per-tier feature gate system. The `Entitlements` dataclass captures all 30+ feature flags and limits. `TIER_ENTITLEMENTS` is a static dict mirroring the DB seed in `001_initial_billing_tables.sql`.

Key capabilities:
- `Entitlements.for_customer(store, customer_id)` — async DB lookup (production path)
- `Entitlements.for_tier(tier)` — static lookup (tests, offline, middleware)
- Convenience predicates: `.allows_symbol_count(n)`, `.allows_alert_count(today)`, `.has_feature("feature_name")`
- Upgrade/downgrade helpers: `is_upgrade(from_tier, to_tier)`, `tier_rank(tier)`

### 2. Subscription Persistence

**SQLite path** (`billing/subscription_store.py`):
- `SubscriptionStore` — thread-safe, WAL mode, per-call connection pattern
- Tables: `subscriptions` (upserted on each event), `webhook_events` (idempotency guard)
- Key methods: `upsert_subscription()`, `get_subscription_by_customer()`, `cancel_subscription()`, `get_customer_id_by_email()`, `list_active_subscriptions()`

**PostgreSQL path** (`billing/pg_subscription_store.py`):
- `PgSubscriptionStore` — async, asyncpg connection pool (2–10 connections)
- Drop-in replacement for SQLite store
- Uses `billing` schema with ENUMs; supports `get_entitlements()` join for efficient middleware gate checks
- Configure via `DATABASE_URL` or `BILLING_DATABASE_URL` env var

**Schema** (`billing/migrations/001_initial_billing_tables.sql`):
5 tables: `billing.subscriptions`, `billing.webhook_events`, `billing.entitlements` (seeded), `billing.invoice_history`, `billing.api_usage`. Postgres 14+ with ENUMs.

### 3. Customer Portal API (`billing/customer_portal.py`)

Two new endpoints:
- `POST /billing/portal/session` — creates a Stripe Billing Portal session. Accepts `customer_id` (direct) or `email` (DB lookup). Returns a `url` for client redirect.
- `GET /billing/portal/config` — checks whether the Stripe portal is configured in the Dashboard (prerequisite for portal sessions).

### 4. Billing Notifications (`billing/notifications.py`)

`BillingNotifier` sends Telegram alerts for billing events with tier emoji (🌱 Starter, ⚡ Pro, 🏆 Elite, 🏢 Team). Falls back to console logging if `TELEGRAM_BOT_TOKEN` is absent. Integrated into all 5 webhook handlers.

### 5. Production Webhook Handler (`billing/webhook_handler.py`)

The billing service main app — replaces the earlier `billing/stripe_checkout.py` as the primary billing FastAPI entry point. Integrates `SubscriptionStore`, `BillingNotifier`, and the portal router. Startup validation warns on missing config.

### 6. Frontend Pages

- `dashboard/pricing.html` — Pricing page showing all 4 tiers with feature comparisons and checkout CTA buttons.
- `dashboard/billing_success.html` — Post-checkout landing page (redirected to after Stripe checkout completes).

### 7. QA Results (COI-39, 2026-04-15)

80/80 tests pass. Three bugs fixed during QA:

| Bug | Fix |
|-----|-----|
| `STRIPE_WEBHOOK_SECRET` frozen at import time — breaks test isolation | Changed to lazy `_webhook_secret()` function (reads env per-request) |
| Pydantic v2: `class Config` deprecation in `billing/models.py` | Changed to `model_config = ConfigDict(use_enum_values=True)` |
| Pydantic v2: `.dict()` deprecation in `billing/webhook_handler.py` | Changed to `.model_dump(mode="json")` |

---

## Pre-existing Issues (unchanged from 2026-04-14 report)

The following items remain open and were not addressed this cycle:

1. **`signal_generator.py`** — `ScannerResult` accessed as dict → `TypeError`
2. **`pattern_scanner.py`** — private import from `volume_scanner`
3. **`alert_queue.py`** — CRITICAL alerts silently dropped on full queue
4. **`rate_limiter.py`** — `threading.Lock` in async context
5. **`entry_exit_calculator.py`** — SHORT SL uses wrong swing high
6. **`cache_manager.py`** — `KEYS` O(N) blocking scan
7. **BUG-16** — duplicate `whale signal filter (1).py` not yet deleted

---

*Report generated by CoinScopeAI documentation-update scheduled task — 2026-04-15*

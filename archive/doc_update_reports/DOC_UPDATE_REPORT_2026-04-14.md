# CoinScopeAI — Documentation Update Report
**Date:** 2026-04-14
**Task:** Scheduled documentation review and update
**Files changed:** README.md, CoinScopeAI-Context.md

---

## Summary

Compared repository state against the previous doc pass (2026-04-11). The following new files were introduced since then, all part of a new **Stripe billing integration**:

```
billing/                                        ← Standalone billing service (port 8002)
│   ├── stripe_checkout.py                      # FastAPI app with 4 billing endpoints
│   ├── config.py                               # Plan registry + Stripe Price ID helpers
│   └── README.md                               # Billing quick start guide
coinscope_trading_engine/billing/               ← Integrated billing router (engine API)
│   ├── stripe_gateway.py                       # FastAPI router — 5 billing endpoints
│   ├── models.py                               # Pydantic schemas for billing
│   └── webhooks.py                             # Stripe event handlers + state persistence
coinscope_trading_engine/setup_stripe_products.py  # One-time Stripe product/price setup script
.env.template                                   # Updated with 12 new Stripe variables
```

Both documentation files have been updated to reflect this new feature.

---

## Changes Made

### 1. CoinScopeAI-Context.md

**a) Updated metadata**
- `Last updated`: 2026-04-11 → 2026-04-14
- API endpoint count in repo layout: 21 → 26

**b) Added Stripe to Technology Stack table**
```
| Billing | Stripe (Checkout Sessions, Customer Portal, webhooks) |
```

**c) Updated Repository Layout**
Added two new directory entries:
- `coinscope_trading_engine/billing/` — with three sub-files documented
- `billing/` (standalone service at root) — with three sub-files documented
- `setup_stripe_products.py` noted in engine directory

**d) Added Billing section to API Reference**
Five new endpoint rows under a new `### Billing` heading:
```
GET  /billing/plans         — All pricing tiers with features and amounts
GET  /billing/subscription  — Current subscription status
POST /billing/checkout      — Create a Stripe Checkout Session
POST /billing/portal        — Create a Stripe Customer Portal session
POST /billing/webhook       — Stripe webhook receiver (hidden from Swagger)
```

**e) Added Billing Service (Standalone) section**
Documents the 4-endpoint service on port 8002, pricing tiers table, one-time setup script, and the 5 webhook events handled.

**f) Added Billing subsection to Environment Variables**
11 new Stripe-related environment variables documented with descriptions.

**g) Added Billing open issues**
- Subscription fulfilment stub (no DB write yet)
- Customer Portal requires Stripe Dashboard configuration

**h) Added Billing API URL to Observability Stack table**
```
| Billing API docs | http://localhost:8002/docs | — |
```

**i) Updated Development Status table**
```
| Stripe billing integration | ✅ Complete (test mode) — added 2026-04-14 |
| Billing fulfilment (user DB write) | 🔄 Stub — Stripe events logged, no DB write yet |
```

**j) Added billing launch steps to Recommended Launch Sequence**

---

### 2. README.md

**a) Updated endpoint count in Architecture tree**
```
# Before
├── api.py   # FastAPI HTTP layer (21 endpoints, v2.0.0)

# After
├── api.py   # FastAPI HTTP layer (26 endpoints, v2.0.0)
```

**b) Added `billing/` directory to Architecture tree**
```
├── billing/
│   ├── stripe_gateway.py      # FastAPI router — 5 billing endpoints
│   ├── models.py              # Pydantic schemas
│   └── webhooks.py            # Stripe event handlers + JSON state sidecar
```

**c) Added 4 billing endpoint rows to API Reference table**
```
| GET  | /billing/plans        | Billing | All pricing tiers with features and amounts |
| GET  | /billing/subscription | Billing | Current subscription status                  |
| POST | /billing/checkout     | Billing | Create a Stripe Checkout Session             |
| POST | /billing/portal       | Billing | Create a Stripe Customer Portal session      |
```

**d) Added Stripe variables to Environment Variables table**
```
STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET,
STRIPE_PRICE_<TIER>_<INTERVAL> (8 price IDs)
```

**e) Added `## Billing (Stripe)` section**
New section documents: architecture (integrated vs. standalone), pricing tiers table, full setup walkthrough (4 steps + curl example), and Stripe test cards.

**f) Updated Roadmap**
```
- [x] Stripe billing integration (Checkout, Portal, webhooks — test mode)
```

---

## New Feature Documented This Week

### Stripe Billing Integration

**What was built:**

A two-layer Stripe subscription system:

1. **Integrated router** (`coinscope_trading_engine/billing/stripe_gateway.py`) — A FastAPI `APIRouter` mounted into the main engine API at `app.include_router(billing_router)`. Provides 5 endpoints for plan listing, subscription state, checkout, customer portal, and webhook handling. Subscription state is persisted as a JSON sidecar file (`subscription_state.json`) so it survives restarts without a database migration.

2. **Standalone billing service** (`billing/stripe_checkout.py`) — An independent FastAPI app (port 8002). Provides a simpler 4-endpoint checkout flow suited for a pricing page frontend. Supports monthly and annual billing intervals with a 20% annual discount.

**Four subscription tiers:**
- Starter ($19/mo), Pro ($49/mo, most popular), Elite ($99/mo), Team ($299/mo)

**Stripe webhook events handled:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`

**Status:** Fully wired in test mode. Subscription activation and payment events are logged and state-persisted. **The fulfilment stub (writing to a user DB or Notion on checkout completion) is not yet implemented** — this is the primary remaining TODO for the billing feature to be production-ready.

---

## Pre-existing Issues (unchanged from 2026-04-11 report)

The following items remain open and were not addressed this cycle:

1. **`signal_generator.py`** — `ScannerResult` accessed as dict → `TypeError`
2. **`pattern_scanner.py`** — private import from `volume_scanner`
3. **`alert_queue.py`** — CRITICAL alerts silently dropped on full queue
4. **`rate_limiter.py`** — `threading.Lock` in async context
5. **`entry_exit_calculator.py`** — SHORT SL uses wrong swing high
6. **`cache_manager.py`** — `KEYS` O(N) blocking scan
7. **BUG-16** — duplicate `whale signal filter (1).py` not yet deleted

---

*Report generated by CoinScopeAI documentation-update scheduled task — 2026-04-14*

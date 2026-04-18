# Stripe Billing

**Status:** current
**Audience:** developers working on the billing surface or entitlement checks
**Related:** [`stripe-billing-runbook.md`](stripe-billing-runbook.md), [`../api/backend-endpoints.md`](../api/backend-endpoints.md), [`../backend/configuration.md`](../backend/configuration.md)

The billing layer is a thin FastAPI surface that listens for Stripe webhooks, tracks subscription state in SQLite (or Postgres in production-candidate deployments), and gates two API endpoints by entitlement. It is intentionally simple; all invoicing, dunning, tax, and payment mechanics live on Stripe.

## What billing does

Four responsibilities:

1. **Receive and verify Stripe webhook events** at `POST /billing/webhook`.
2. **Maintain a local mirror** of the customer → subscription → entitlement graph for fast reads.
3. **Expose `GET /billing/me`** so the dashboard can render plan state without hitting Stripe.
4. **Gate the entitled endpoints** (`/depth/{symbol}` and any future paid-tier features) via a simple allow/deny check.

What billing does **not** do:

- Store card numbers, bank accounts, or any PCI-scope data. Stripe is the only system of record for payment instruments.
- Compute tax. Stripe Tax handles that (or the account is configured as tax-not-collected for the current operator footprint).
- Send customer emails. Stripe sends receipts and dunning; the engine does not email customers.

## Architecture

```
Stripe ──webhook──▶ /billing/webhook (FastAPI)
                        │
                        │ verify signature (STRIPE_WEBHOOK_SECRET)
                        │ handle event by type
                        ▼
                   SQLite (or Postgres)
                   ├── customers
                   ├── subscriptions
                   └── entitlements
                        ▲
                        │ read
                        │
GET /billing/me ◀───────┘
GET /depth/{sym} ◀──────┘  (via entitlement gate)
```

The code lives in two places today:

- `billing_server.py` at the repo root — a standalone FastAPI app used for local testing and earlier deploys.
- `billing/` package inside `coinscope_trading_engine/` — the in-engine billing module used by production-candidate deploys.

This duplication is a post-validation cleanup item. Both implementations handle the same events and write to the same schema; they do not diverge in behavior. See [`../product/implementation-backlog.md`](../product/implementation-backlog.md) for the consolidation plan.

## Webhook events handled

| Stripe event | Action |
| --- | --- |
| `customer.created` | Insert into `customers`. |
| `customer.updated` | Update email and metadata. |
| `customer.subscription.created` | Insert into `subscriptions`, derive initial entitlement. |
| `customer.subscription.updated` | Update plan, period end, status. Recompute entitlement. |
| `customer.subscription.deleted` | Mark subscription canceled, revoke entitlement at `cancel_at`. |
| `invoice.payment_succeeded` | Bump `current_period_end`, ensure entitlement is active. |
| `invoice.payment_failed` | Log; entitlement stays until Stripe's dunning cycle concludes. |
| `checkout.session.completed` | Link the checkout session's customer and subscription ids to the local user. |

Events not in this list are logged and acknowledged but take no action. Adding a new event type is a one-line registration in the dispatcher plus a handler function.

### Signature verification

Every webhook request is verified against `STRIPE_WEBHOOK_SECRET` using `stripe.Webhook.construct_event`. A failed verification returns 400 and journals the attempt with source IP. **An unsigned or mis-signed event never touches the database.**

### Idempotency

Stripe retries webhooks. The dispatcher dedupes on `event.id`:

- On first receipt: handle, record the `event.id` in `processed_events`, return 200.
- On repeat: look up `event.id`; if seen, return 200 without re-handling.

This is correctness-critical. A `subscription.updated` handler that ran twice could corrupt period tracking.

## Data model

Four tables, kept deliberately small:

### `customers`

- `stripe_customer_id` (pk)
- `email`
- `created_at`
- `metadata_json`

### `subscriptions`

- `stripe_subscription_id` (pk)
- `stripe_customer_id` (fk)
- `plan_id` — Stripe price id.
- `status` — `active`, `trialing`, `past_due`, `canceled`, `incomplete`.
- `current_period_end` — UTC timestamp.
- `cancel_at` — optional, if scheduled for cancellation.
- `updated_at`

### `entitlements`

- `stripe_customer_id` (pk)
- `tier` — `free`, `basic`, `pro`.
- `active` — boolean, derived from `subscriptions.status` and period end.
- `expires_at`

### `processed_events`

- `stripe_event_id` (pk)
- `received_at`
- `event_type`

The tier → feature-flag mapping is in code (`billing/entitlements.py`), not in the database. A tier change requires a PR, not a SQL write.

## The entitlement gate

The gate is a single dependency function used by FastAPI routes:

```python
async def require_entitlement(feature: str, user = Depends(current_user)):
    ent = await get_entitlement(user.stripe_customer_id)
    if not ent.active or feature not in FEATURES_BY_TIER[ent.tier]:
        raise HTTPException(403, detail="entitlement_required")
    return ent
```

Applied to routes as:

```python
@app.get("/depth/{symbol}")
async def depth(symbol: str, ent = Depends(require_entitlement("depth"))):
    ...
```

**Rules:**

- An absent entitlement record (no row) is treated as tier `free`, not an error.
- An `active=false` entitlement cannot be used, regardless of tier.
- The gate reads from the local mirror, never Stripe's API, on the hot path. If the mirror is stale because webhooks stopped arriving, that is an incident (covered in [`stripe-billing-runbook.md`](stripe-billing-runbook.md)).

## Environment configuration

| Env var | Purpose |
| --- | --- |
| `STRIPE_SECRET_KEY` | Stripe API key for outbound calls (portal link generation, manual lookups). |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `/billing/webhook` verification. Different per-environment. |
| `STRIPE_PRICE_*` | One env var per plan; resolves plan-id → tier at startup. |
| `BILLING_DB_URL` | SQLite path or Postgres DSN. Defaults to `sqlite:///billing_subscriptions.db`. |
| `BILLING_PORTAL_RETURN_URL` | Where Stripe's billing portal redirects after the customer is done. |

All Stripe secrets are read from `.env`, never from CLI flags. Rotation procedure is in [`stripe-billing-runbook.md`](stripe-billing-runbook.md).

## Local development

See [`../runbooks/local-development.md`](../runbooks/local-development.md) for the end-to-end flow. Short version:

1. Use Stripe's test mode key, not live.
2. Run `stripe listen --forward-to localhost:8001/billing/webhook` to tunnel events to your machine.
3. Trigger a checkout from the dashboard or via `stripe trigger checkout.session.completed`.
4. Verify the mirror was updated: `curl localhost:8001/billing/me`.

Do not point your local machine at live Stripe events. The webhook secret is environment-specific for a reason.

## Observability

| Metric | Labels | Meaning |
| --- | --- | --- |
| `engine_billing_webhook_total` | `event_type, result=ok\|sig_fail\|dup\|error` | Webhook ingestion outcomes. |
| `engine_billing_entitlement_checks_total` | `feature, result=allow\|deny` | Gate decisions. |
| `engine_billing_mirror_lag_seconds` | — | Time since the most recent webhook event was processed. |
| `engine_billing_active_subscriptions` | `tier` | Count by tier. |

An alert fires if `engine_billing_mirror_lag_seconds` exceeds 600 (ten minutes of no webhook events during a window where activity is expected). See [`stripe-billing-runbook.md`](stripe-billing-runbook.md) for response.

## Testing

Unit tests cover signature verification, idempotency (replay of the same `event.id`), each handler's state transitions, and entitlement gate decisions. Located at `coinscope_trading_engine/tests/test_billing_*.py` and `tests/test_billing_server_*.py`.

There is a fixture set of realistic Stripe events in `tests/fixtures/stripe_events/`. Adding a new event handler requires adding at least one fixture.

## Security posture

- **PCI scope: out.** We do not touch cards.
- **Webhook source verification: enforced.** See signature verification above.
- **Admin endpoints: none.** There is no "manually grant entitlement" endpoint. If you need to grant an entitlement in the test environment, do it in Stripe and let the webhook flow through, or insert a row directly in the test database with a comment.
- **Rate limiting on `/billing/webhook`:** none from our side. Stripe retries are well-behaved; if we see abuse, it's a sign the webhook URL has leaked and we rotate the webhook secret.

## Relationship to the rest of the engine

Billing is **out-of-band** from the trading loop. A billing failure never blocks trading. The entitlement gate blocks specific API endpoints, not the core risk/execution path. This separation is intentional: the worst billing outage is a feature unavailable to a paying customer, not a missed stop-loss.

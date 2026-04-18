# CoinScopeAI Billing — Stripe Checkout Session API

Standalone FastAPI service (port **8002**) that handles subscription checkout,
webhook fulfilment, and plan listing. Runs alongside the engine API (port 8001).

---

## Files

```
billing/
├── __init__.py
├── config.py          ← plan registry + price ID helpers
├── stripe_checkout.py ← FastAPI app with all 4 endpoints
└── README.md
```

---

## Quick Start

### 1 — Install dependencies

```bash
pip install stripe fastapi uvicorn pydantic
```

### 2 — Set environment variables

Copy `.env.template` → `.env`, then fill in the Stripe section:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...          # from stripe listen output

# 8 Price IDs — create in Stripe Dashboard → Products
STRIPE_PRICE_STARTER_MONTHLY=price_...
STRIPE_PRICE_STARTER_ANNUAL=price_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...
STRIPE_PRICE_ELITE_MONTHLY=price_...
STRIPE_PRICE_ELITE_ANNUAL=price_...
STRIPE_PRICE_TEAM_MONTHLY=price_...
STRIPE_PRICE_TEAM_ANNUAL=price_...
```

### 3 — Create Stripe Products + Prices

In Stripe Dashboard (Test Mode) → **Products** → **Add product**:

| Product  | Monthly Price | Annual Price |
|----------|--------------|-------------|
| Starter  | $19.00/mo    | $190.00/yr  |
| Pro      | $49.00/mo    | $490.00/yr  |
| Elite    | $99.00/mo    | $990.00/yr  |
| Team     | $299.00/mo   | $2,990.00/yr|

Copy each `price_xxx` ID into your `.env`.

### 4 — Run the billing server

```bash
uvicorn billing.stripe_checkout:app --port 8002 --reload
```

### 5 — Test webhooks locally

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
stripe login
stripe listen --forward-to localhost:8002/billing/webhook
# Copy the whsec_... secret printed → STRIPE_WEBHOOK_SECRET in .env
```

### 6 — Trigger a test checkout (curl)

```bash
curl -X POST http://localhost:8002/billing/checkout/session \
  -H "Content-Type: application/json" \
  -d '{"tier": "pro", "interval": "monthly", "customer_email": "test@example.com"}'
```

Response:
```json
{
  "session_id": "cs_test_...",
  "session_url": "https://checkout.stripe.com/pay/cs_test_...",
  "tier": "pro",
  "interval": "monthly",
  "amount_usd": 49.0,
  "publishable_key": "pk_test_..."
}
```

Redirect the user to `session_url`.

---

## API Reference

| Method | Path                          | Description                            |
|--------|-------------------------------|----------------------------------------|
| GET    | `/billing/health`             | Health + Stripe config status          |
| GET    | `/billing/plans`              | All tiers with features + amounts      |
| POST   | `/billing/checkout/session`   | Create Stripe Checkout Session         |
| POST   | `/billing/webhook`            | Stripe webhook receiver                |

Interactive docs: http://localhost:8002/docs

---

## Webhook Events Handled

| Event                           | Action                                  |
|---------------------------------|-----------------------------------------|
| `checkout.session.completed`    | Subscription active — provision user    |
| `customer.subscription.updated` | Plan change / renewal sync              |
| `customer.subscription.deleted` | Subscription cancelled — revoke access  |
| `invoice.payment_failed`        | Payment failed — dunning alert          |

---

## Test Cards

| Scenario          | Card Number          |
|-------------------|----------------------|
| Success           | `4242 4242 4242 4242` |
| 3DS required      | `4000 0027 6000 3184` |
| Payment declined  | `4000 0000 0000 9995` |

Use any future expiry + any CVC + any postal code.

---

## Adding to docker-compose.yml

```yaml
billing:
  build: .
  command: uvicorn billing.stripe_checkout:app --host 0.0.0.0 --port 8002
  ports:
    - "8002:8002"
  env_file: .env
  depends_on:
    - engine
```

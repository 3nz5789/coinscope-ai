# Runbook: BILLING — Stripe Setup

**Owner:** Mohammed (3onooz) | **Frequency:** Once (initial), then per-environment promotion  
**Last Updated:** 2026-04-15 | **Last Run:** —  
**Port:** `8002` (billing server) | **Engine Port:** `8001`  
**Mode:** TEST ONLY during 30-day validation phase. Never switch to Live keys without explicit approval.

---

## Purpose

End-to-end procedure for activating the CoinScopeAI Stripe billing integration. Covers:

- Creating products and prices in the Stripe Dashboard (Test Mode)
- Populating `.env` with all 11 required billing variables
- Starting the billing server (`billing_server.py`) on port 8002
- Verifying webhooks with the Stripe CLI
- Smoke-testing all four checkout flows
- Wiring Telegram billing alerts

Run this once on a new environment (local or VPS). Re-run Steps 3–5 when promoting to Live keys post-validation.

---

## Prerequisites

- [ ] Python 3.11+ virtual environment active (`source .venv/bin/activate`)
- [ ] Dependencies installed: `pip install stripe fastapi uvicorn pydantic python-dotenv requests`
- [ ] Stripe account at https://dashboard.stripe.com — **Test Mode toggle ON** (top-left)
- [ ] Stripe CLI installed: https://stripe.com/docs/stripe-cli (needed for local webhook forwarding)
- [ ] `.env.template` copied to `.env` in project root
- [ ] `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` already set in `.env` (Chat ID: `7296767446`)
- [ ] Billing server file exists: `billing_server.py` + `billing/` package in project root

---

## Procedure

### Step 1 — Enable Test Mode in Stripe Dashboard

Navigate to https://dashboard.stripe.com. Confirm the **Test Mode** toggle (top-left) is **ON**. All keys, products, and prices created here will start with `_test_` or `price_test_`.

```
URL: https://dashboard.stripe.com/test/dashboard
```

**Expected result:** Dashboard header shows "Test mode" in orange.  
**If it fails:** Toggle is in the top-left — click to switch. Never proceed with Live mode during validation.

---

### Step 2 — Retrieve API Keys

Navigate to **Developers → API keys** (https://dashboard.stripe.com/test/apikeys).

Copy the two test keys:

| Variable | Where to find | Starts with |
|---|---|---|
| `STRIPE_SECRET_KEY` | "Secret key" — click Reveal | `sk_test_...` |
| `STRIPE_PUBLISHABLE_KEY` | "Publishable key" — visible | `pk_test_...` |

Add to `.env`:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
```

**Expected result:** Both keys visible, no errors.  
**If it fails:** You may need to verify your email address with Stripe first.

---

### Step 3 — Create Products and Prices in Stripe Dashboard

Navigate to **Products** → **Add product** (https://dashboard.stripe.com/test/products/create).

Create **4 products**, each with **2 prices** (monthly + annual). Use the exact amounts below — these are the canonical prices. Do not change without Mohammed's approval.

#### 3a — Starter ($19/mo · $190/yr)

```
Product name:  CoinScopeAI Starter
Description:   5 pairs · 4h scan · Telegram alerts · 30-day journal

Price 1:  Recurring · Monthly · $19.00 USD
Price 2:  Recurring · Annual  · $190.00 USD
```

#### 3b — Pro ($49/mo · $490/yr) — Most Popular

```
Product name:  CoinScopeAI Pro
Description:   25 pairs · 1h scan · ML v3 · Kelly sizing · Unlimited journal

Price 1:  Recurring · Monthly · $49.00 USD
Price 2:  Recurring · Annual  · $490.00 USD
```

#### 3c — Elite ($99/mo · $990/yr)

```
Product name:  CoinScopeAI Elite
Description:   Unlimited pairs · 15min scan · Multi-exchange · CVD · API access

Price 1:  Recurring · Monthly · $99.00 USD
Price 2:  Recurring · Annual  · $990.00 USD
```

#### 3d — Team ($299/mo · $2,990/yr)

```
Product name:  CoinScopeAI Team
Description:   Everything in Elite · 10 seats · SLA · Dedicated onboarding

Price 1:  Recurring · Monthly · $299.00 USD
Price 2:  Recurring · Annual  · $2,990.00 USD
```

After saving each product, click into each price to copy its `price_xxx` ID.

**Expected result:** 4 products, 8 price IDs visible in the Products list.  
**If it fails:** Ensure "Recurring" billing (not "One time") is selected for all prices.

---

### Step 4 — Populate Price IDs in `.env`

Add all 8 price IDs to `.env`:

```env
# ── Stripe Price IDs ──────────────────────────────────────────
STRIPE_PRICE_STARTER_MONTHLY=price_...
STRIPE_PRICE_STARTER_ANNUAL=price_...

STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_PRO_ANNUAL=price_...

STRIPE_PRICE_ELITE_MONTHLY=price_...
STRIPE_PRICE_ELITE_ANNUAL=price_...

STRIPE_PRICE_TEAM_MONTHLY=price_...
STRIPE_PRICE_TEAM_ANNUAL=price_...
```

**Verify the mapping is correct** — each `price_` must match the correct tier and interval. A mismatch will charge customers the wrong amount silently.

**Expected result:** 8 `price_` values in `.env`, all starting with `price_`.  
**If it fails:** Re-open each product in the Dashboard and copy the price ID from the price row (not the product ID).

---

### Step 5 — Set Billing Redirect URLs

In `.env`, set where Stripe redirects after checkout:

```env
# For local development:
BILLING_SUCCESS_URL=http://localhost:8080/billing_success.html?session_id={CHECKOUT_SESSION_ID}
BILLING_CANCEL_URL=http://localhost:8080/pricing.html
BILLING_PORTAL_RETURN_URL=http://localhost:8080/account.html

# For VPS deployment (replace with real domain):
# BILLING_SUCCESS_URL=https://coinscopedash-tltanhwx.manus.space/billing_success.html?session_id={CHECKOUT_SESSION_ID}
# BILLING_CANCEL_URL=https://coinscopedash-tltanhwx.manus.space/pricing.html
```

**Note:** `{CHECKOUT_SESSION_ID}` is a Stripe template variable — leave it as-is. Stripe fills it in automatically.

**Expected result:** URLs match your running dashboard environment.  
**If it fails:** Use the localhost URLs for local testing; swap to the Manus/VPS URLs after deployment.

---

### Step 6 — Start the Billing Server

```bash
cd /path/to/CoinScopeAI
source .venv/bin/activate
python billing_server.py
```

Or directly via uvicorn:

```bash
uvicorn billing.webhook_handler:app --host 0.0.0.0 --port 8002
```

**Expected result:** Console output similar to:

```
[billing_server] Loaded .env from /path/to/.env
[billing_server] Starting CoinScopeAI Billing Webhook on 0.0.0.0:8002
[billing_server] Webhook endpoint: POST http://0.0.0.0:8002/billing/webhook
[billing_server] Health check:     GET  http://localhost:8002/billing/health
```

Zero config warnings. If you see warnings about missing `STRIPE_SECRET_KEY` or `STRIPE_PRICE_*`, stop and fix `.env` before proceeding.

**If it fails:**

- `ModuleNotFoundError: stripe` → `pip install stripe fastapi uvicorn pydantic`
- Port 8002 already in use → `lsof -i :8002` then kill the PID
- `.env` not loading → ensure `python-dotenv` is installed; check `.env` is in the project root

---

### Step 7 — Verify Health Endpoint

```bash
curl http://localhost:8002/billing/health
```

**Expected result:**

```json
{
  "status": "ok",
  "stripe_configured": true,
  "webhook_configured": false,
  "mode": "test"
}
```

`webhook_configured` will be `false` until Step 8. That is expected.  
**If `stripe_configured` is `false`:** `STRIPE_SECRET_KEY` is not being read — double-check `.env` path and `python-dotenv` installation.

---

### Step 8 — Wire Stripe Webhooks (Local Testing)

Open a **second terminal** and run the Stripe CLI:

```bash
stripe login          # one-time browser auth
stripe listen --forward-to localhost:8002/billing/webhook
```

**Expected result:** Stripe CLI prints:

```
> Ready! You are using Stripe API Version [date]
> Webhook signing secret: whsec_xxxxxxxxxxxxxxxxxxxxxxxx
```

Copy the `whsec_...` value, add to `.env`:

```env
STRIPE_WEBHOOK_SECRET=whsec_...
```

Restart `billing_server.py` (Ctrl+C → `python billing_server.py` again).

Re-run the health check — `webhook_configured` should now be `true`.

**If it fails:**

- `stripe: command not found` → Install Stripe CLI: https://stripe.com/docs/stripe-cli#install
- `No connection` → Check internet access and that port 8002 is not firewalled

---

### Step 9 — Smoke Test: Checkout Session API

Test all four tiers. Each should return a `session_url` starting with `https://checkout.stripe.com/`:

```bash
# Pro monthly (Most Popular)
curl -s -X POST http://localhost:8002/billing/checkout/session \
  -H "Content-Type: application/json" \
  -d '{"tier": "pro", "interval": "monthly", "customer_email": "test@example.com"}' | python3 -m json.tool

# Starter annual
curl -s -X POST http://localhost:8002/billing/checkout/session \
  -H "Content-Type: application/json" \
  -d '{"tier": "starter", "interval": "annual"}' | python3 -m json.tool

# Elite monthly
curl -s -X POST http://localhost:8002/billing/checkout/session \
  -H "Content-Type: application/json" \
  -d '{"tier": "elite", "interval": "monthly"}' | python3 -m json.tool

# Team monthly
curl -s -X POST http://localhost:8002/billing/checkout/session \
  -H "Content-Type: application/json" \
  -d '{"tier": "team", "interval": "monthly"}' | python3 -m json.tool
```

**Expected result for each:**

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

**If it fails:**

- `400 Stripe error: No such price` → Price ID for that tier/interval is wrong or missing in `.env`
- `503 Stripe not configured` → `STRIPE_SECRET_KEY` not loaded
- `400 Unknown tier` → Tier name typo — must be exactly `starter`, `pro`, `elite`, or `team`

---

### Step 10 — Smoke Test: Complete a Test Checkout

1. Copy the `session_url` from Step 9 (Pro monthly).
2. Open it in a browser.
3. On the Stripe checkout page, enter the test card:

| Field | Value |
|---|---|
| Card number | `4242 4242 4242 4242` |
| Expiry | Any future date (e.g. `12/28`) |
| CVC | Any 3 digits (e.g. `123`) |
| Name / Postal | Any value |

4. Click **Subscribe**.

**Expected result:**

- Browser redirects to your `BILLING_SUCCESS_URL`
- Stripe CLI terminal shows: `checkout.session.completed`
- `billing_server.py` logs: `✅ Checkout completed | email=test@example.com tier=pro ...`
- Telegram message received: `💰 New Subscriber! Plan: ⚡ Pro (Monthly)`

**If it fails:**

- Checkout page shows "Card declined" → You may be using a live card on a test session. Use the test card above.
- `checkout.session.completed` fires but no Telegram message → `TELEGRAM_BOT_TOKEN` not set or bot not started

---

### Step 11 — Verify Plans Endpoint

```bash
curl -s http://localhost:8002/billing/plans | python3 -m json.tool
```

**Expected result:** JSON array of 4 plans with `price_ids_configured.monthly: true` and `price_ids_configured.annual: true` for all tiers.

If any plan shows `false`, the corresponding `STRIPE_PRICE_*` variable is missing from `.env`.

---

## Verification Checklist

- [ ] `GET /billing/health` → `stripe_configured: true`, `webhook_configured: true`, `mode: "test"`
- [ ] `GET /billing/plans` → 4 tiers, all 8 price IDs configured
- [ ] `POST /billing/checkout/session` returns `session_url` for all 4 tiers × 2 intervals
- [ ] Test checkout completes end-to-end with card `4242 4242 4242 4242`
- [ ] `checkout.session.completed` event appears in Stripe CLI output
- [ ] Telegram billing alert received in @ScoopyAI_bot (Chat ID: `7296767446`)
- [ ] No config warnings in `billing_server.py` startup log
- [ ] Billing server running on port 8002, engine on port 8001 — no port conflicts

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `stripe_configured: false` in health | `STRIPE_SECRET_KEY` not loaded | Check `.env` path; ensure `python-dotenv` installed |
| `price_ids_configured: false` for a tier | `STRIPE_PRICE_*` missing | Copy the `price_xxx` from Stripe Dashboard → that product |
| `400 No such price 'price_...'` | Price ID from wrong mode (live vs test) | Confirm Stripe Dashboard is in Test Mode; re-copy IDs |
| `400 Invalid signature` on webhook | Wrong `STRIPE_WEBHOOK_SECRET` | Re-copy `whsec_...` from `stripe listen` output |
| No Telegram alert on checkout | Bot token missing or bot not active | Set `TELEGRAM_BOT_TOKEN` in `.env`; restart billing server |
| Port 8002 already in use | Previous billing server process | `lsof -i :8002` → kill PID |
| `checkout.session.completed` not firing | Stripe CLI not running | Start `stripe listen --forward-to localhost:8002/billing/webhook` |
| `ModuleNotFoundError: stripe` | Missing dependency | `pip install stripe fastapi uvicorn pydantic python-dotenv` |

---

## Rollback

To disable billing without removing code:

1. Stop `billing_server.py` (Ctrl+C or `pkill -f billing_server`).
2. Remove or blank `STRIPE_SECRET_KEY` in `.env`.
3. The dashboard pricing page will fall back to static display — no functional harm.

To re-enable: restart with a valid `.env`.

---

## Promoting to Live Mode (Post-Validation — Do Not Do Yet)

> **BLOCKED:** Do not promote to Live until 30-day testnet validation (COI-41) is complete and Mohammed explicitly approves.

When ready:

1. Go to Stripe Dashboard → toggle **Live Mode** (top-left).
2. Retrieve Live API keys (`sk_live_...`, `pk_live_...`).
3. Recreate all 4 products and 8 prices in Live mode (prices do not copy over).
4. Update `.env` with all live keys and price IDs.
5. Create a real webhook endpoint in Stripe Dashboard → Webhooks (not via `stripe listen`).
6. Update `BILLING_SUCCESS_URL` / `BILLING_CANCEL_URL` to production URLs.
7. Re-run this runbook from Step 6.

---

## Escalation

| Situation | Contact | Method |
|---|---|---|
| Stripe API error in production | Mohammed | Telegram @ScoopyAI_bot |
| Subscription provisioning fails (user charged, no access) | Mohammed | Direct — time-sensitive |
| Price ID mismatch discovered post-launch | Mohammed | Pause checkout, notify immediately |

---

## History

| Date | Run By | Notes |
|---|---|---|
| — | — | Initial runbook — not yet run |

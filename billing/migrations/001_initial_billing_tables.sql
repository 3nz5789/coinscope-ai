-- =============================================================================
-- CoinScopeAI — Billing Schema Migration 001
-- Postgres 14+  |  Run once on a fresh DB or during initial VPS setup
--
-- Schema layout
-- ─────────────
--   billing.subscriptions    — one row per Stripe customer (upserted on events)
--   billing.webhook_events   — idempotency guard for Stripe webhook replays
--   billing.entitlements     — static tier → feature matrix (seeded below)
--   billing.invoice_history  — append-only invoice audit trail
--   billing.api_usage        — per-customer request windows for rate-limiting
--
-- Usage
-- ─────
--   psql $DATABASE_URL -f billing/migrations/001_initial_billing_tables.sql
-- =============================================================================

BEGIN;

-- ─── Schema ──────────────────────────────────────────────────────────────────

CREATE SCHEMA IF NOT EXISTS billing;

-- ─── ENUM types ──────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE billing.subscription_tier AS ENUM (
        'starter', 'pro', 'elite', 'team', 'unknown'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE billing.subscription_status AS ENUM (
        'active', 'past_due', 'canceled', 'trialing', 'incomplete', 'unpaid'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE billing.billing_interval AS ENUM (
        'month', 'year'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ─── 1. subscriptions ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS billing.subscriptions (
    -- Stripe customer ID (cus_xxx) is the stable primary key
    customer_id             TEXT                       PRIMARY KEY,
    email                   TEXT,
    stripe_subscription_id  TEXT                       NOT NULL UNIQUE,

    -- Plan state
    tier                    billing.subscription_tier  NOT NULL DEFAULT 'unknown',
    status                  billing.subscription_status NOT NULL DEFAULT 'incomplete',
    interval                billing.billing_interval   NOT NULL DEFAULT 'month',

    -- Period window
    current_period_end      TIMESTAMPTZ,
    cancel_at_period_end    BOOLEAN                    NOT NULL DEFAULT FALSE,

    -- Audit
    created_at              TIMESTAMPTZ                NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ                NOT NULL DEFAULT NOW()
);

-- Auto-bump updated_at on any UPDATE
CREATE OR REPLACE FUNCTION billing.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_subscriptions_updated_at ON billing.subscriptions;
CREATE TRIGGER trg_subscriptions_updated_at
    BEFORE UPDATE ON billing.subscriptions
    FOR EACH ROW EXECUTE FUNCTION billing.set_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_subs_stripe_sub_id
    ON billing.subscriptions (stripe_subscription_id);

CREATE INDEX IF NOT EXISTS idx_subs_email
    ON billing.subscriptions (lower(email));

CREATE INDEX IF NOT EXISTS idx_subs_tier_status
    ON billing.subscriptions (tier, status);

-- ─── 2. webhook_events (idempotency guard) ────────────────────────────────────

CREATE TABLE IF NOT EXISTS billing.webhook_events (
    event_id         TEXT         PRIMARY KEY,          -- Stripe evt_xxx
    event_type       TEXT         NOT NULL,
    processed_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    customer_id      TEXT         REFERENCES billing.subscriptions(customer_id)
                                  ON DELETE SET NULL,
    subscription_id  TEXT                               -- raw Stripe sub ID
);

CREATE INDEX IF NOT EXISTS idx_webhook_customer
    ON billing.webhook_events (customer_id);

CREATE INDEX IF NOT EXISTS idx_webhook_processed_at
    ON billing.webhook_events (processed_at DESC);

-- ─── 3. entitlements (tier → feature matrix, static lookup) ──────────────────

CREATE TABLE IF NOT EXISTS billing.entitlements (
    tier                        billing.subscription_tier  PRIMARY KEY,
    display_name                TEXT                       NOT NULL,

    -- Pricing (cents)
    monthly_price_usd_cents     INTEGER                    NOT NULL,
    annual_price_usd_cents      INTEGER                    NOT NULL,

    -- Scanner limits (-1 = unlimited)
    max_symbols                 INTEGER                    NOT NULL DEFAULT 5,
    scan_interval_minutes       INTEGER                    NOT NULL DEFAULT 240,  -- 4h default
    max_alerts_per_day          INTEGER                    NOT NULL DEFAULT 3,    -- -1 = unlimited

    -- Journal
    journal_retention_days      INTEGER                    NOT NULL DEFAULT 30,   -- -1 = unlimited

    -- API access
    api_access                  BOOLEAN                    NOT NULL DEFAULT FALSE,
    api_rate_limit_rpm          INTEGER,                   -- NULL = no access

    -- Feature flags
    ml_signals_v3               BOOLEAN                    NOT NULL DEFAULT FALSE,
    regime_detection            BOOLEAN                    NOT NULL DEFAULT FALSE,
    multi_exchange              BOOLEAN                    NOT NULL DEFAULT FALSE,  -- Bybit/OKX/Hyperliquid
    cvd_whale_signals           BOOLEAN                    NOT NULL DEFAULT FALSE,
    backtesting_enabled         BOOLEAN                    NOT NULL DEFAULT FALSE,
    kelly_position_sizing       BOOLEAN                    NOT NULL DEFAULT FALSE,
    walk_forward_validation     BOOLEAN                    NOT NULL DEFAULT FALSE,
    telegram_alerts             BOOLEAN                    NOT NULL DEFAULT TRUE,
    email_alerts                BOOLEAN                    NOT NULL DEFAULT FALSE,
    tradingview_webhooks        BOOLEAN                    NOT NULL DEFAULT FALSE,
    alpha_decay_monitoring      BOOLEAN                    NOT NULL DEFAULT FALSE,

    -- Team
    max_team_seats              INTEGER                    NOT NULL DEFAULT 1,
    priority_support            BOOLEAN                    NOT NULL DEFAULT FALSE,
    dedicated_onboarding        BOOLEAN                    NOT NULL DEFAULT FALSE,
    custom_regime_tuning        BOOLEAN                    NOT NULL DEFAULT FALSE,
    sla_support                 BOOLEAN                    NOT NULL DEFAULT FALSE,
    white_label                 BOOLEAN                    NOT NULL DEFAULT FALSE,

    -- Meta
    is_active                   BOOLEAN                    NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ                NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ                NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_entitlements_updated_at ON billing.entitlements;
CREATE TRIGGER trg_entitlements_updated_at
    BEFORE UPDATE ON billing.entitlements
    FOR EACH ROW EXECUTE FUNCTION billing.set_updated_at();

-- ─── Seed: canonical tier entitlements ────────────────────────────────────────
-- Source of truth: billing/config.py + CoinScopeAI pricing docs
-- Update here when feature set changes; never hard-code in application logic.

INSERT INTO billing.entitlements (
    tier, display_name,
    monthly_price_usd_cents, annual_price_usd_cents,
    max_symbols, scan_interval_minutes, max_alerts_per_day,
    journal_retention_days,
    api_access, api_rate_limit_rpm,
    ml_signals_v3, regime_detection, multi_exchange, cvd_whale_signals,
    backtesting_enabled, kelly_position_sizing, walk_forward_validation,
    telegram_alerts, email_alerts, tradingview_webhooks, alpha_decay_monitoring,
    max_team_seats, priority_support, dedicated_onboarding,
    custom_regime_tuning, sla_support, white_label,
    is_active
) VALUES

-- Starter — $19/mo | $190/yr
(
    'starter', 'Starter',
    1900, 19000,
    5, 240, 3,          -- 5 pairs, 4h scans, 3 alerts/day
    30,                 -- 30-day journal
    FALSE, NULL,        -- no API
    FALSE, FALSE, FALSE, FALSE,
    FALSE, FALSE, FALSE,
    TRUE, FALSE, FALSE, FALSE,
    1, FALSE, FALSE, FALSE, FALSE, FALSE,
    TRUE
),

-- Pro — $49/mo | $490/yr  ← Most Popular
(
    'pro', 'Pro',
    4900, 49000,
    25, 60, 20,         -- 25 pairs, 1h scans, 20 alerts/day
    -1,                 -- unlimited journal
    FALSE, NULL,        -- no API (engine API is Elite+)
    TRUE, TRUE, FALSE, FALSE,
    TRUE, TRUE, TRUE,   -- backtesting, Kelly, walk-forward
    TRUE, TRUE, FALSE, FALSE,
    1, FALSE, FALSE, FALSE, FALSE, FALSE,
    TRUE
),

-- Elite — $99/mo | $990/yr
(
    'elite', 'Elite',
    9900, 99000,
    -1, 15, -1,         -- unlimited pairs, 15min scans, unlimited alerts
    -1,
    TRUE, 300,          -- API access, 300 rpm
    TRUE, TRUE, TRUE, TRUE,     -- all ML features
    TRUE, TRUE, TRUE,
    TRUE, TRUE, TRUE, TRUE,     -- all alert channels + alpha decay
    3, TRUE, FALSE, FALSE, FALSE, FALSE,
    TRUE
),

-- Team — $299/mo (custom annual)
(
    'team', 'Team',
    29900, 299000,
    -1, 15, -1,
    -1,
    TRUE, 1000,
    TRUE, TRUE, TRUE, TRUE,
    TRUE, TRUE, TRUE,
    TRUE, TRUE, TRUE, TRUE,
    10, TRUE, TRUE, TRUE, TRUE, FALSE,
    TRUE
),

-- Unknown — fallback for unresolved Stripe price IDs
(
    'unknown', 'Unknown',
    0, 0,
    0, 0, 0,
    0,
    FALSE, NULL,
    FALSE, FALSE, FALSE, FALSE,
    FALSE, FALSE, FALSE,
    FALSE, FALSE, FALSE, FALSE,
    0, FALSE, FALSE, FALSE, FALSE, FALSE,
    FALSE
)

ON CONFLICT (tier) DO UPDATE SET
    display_name                = EXCLUDED.display_name,
    monthly_price_usd_cents     = EXCLUDED.monthly_price_usd_cents,
    annual_price_usd_cents      = EXCLUDED.annual_price_usd_cents,
    max_symbols                 = EXCLUDED.max_symbols,
    scan_interval_minutes       = EXCLUDED.scan_interval_minutes,
    max_alerts_per_day          = EXCLUDED.max_alerts_per_day,
    journal_retention_days      = EXCLUDED.journal_retention_days,
    api_access                  = EXCLUDED.api_access,
    api_rate_limit_rpm          = EXCLUDED.api_rate_limit_rpm,
    ml_signals_v3               = EXCLUDED.ml_signals_v3,
    regime_detection            = EXCLUDED.regime_detection,
    multi_exchange              = EXCLUDED.multi_exchange,
    cvd_whale_signals           = EXCLUDED.cvd_whale_signals,
    backtesting_enabled         = EXCLUDED.backtesting_enabled,
    kelly_position_sizing       = EXCLUDED.kelly_position_sizing,
    walk_forward_validation     = EXCLUDED.walk_forward_validation,
    telegram_alerts             = EXCLUDED.telegram_alerts,
    email_alerts                = EXCLUDED.email_alerts,
    tradingview_webhooks        = EXCLUDED.tradingview_webhooks,
    alpha_decay_monitoring      = EXCLUDED.alpha_decay_monitoring,
    max_team_seats              = EXCLUDED.max_team_seats,
    priority_support            = EXCLUDED.priority_support,
    dedicated_onboarding        = EXCLUDED.dedicated_onboarding,
    custom_regime_tuning        = EXCLUDED.custom_regime_tuning,
    sla_support                 = EXCLUDED.sla_support,
    white_label                 = EXCLUDED.white_label,
    is_active                   = EXCLUDED.is_active,
    updated_at                  = NOW();

-- ─── 4. invoice_history (append-only audit trail) ────────────────────────────

CREATE TABLE IF NOT EXISTS billing.invoice_history (
    id                      BIGSERIAL    PRIMARY KEY,
    invoice_id              TEXT         NOT NULL UNIQUE,    -- Stripe inv_xxx
    customer_id             TEXT         NOT NULL
                            REFERENCES billing.subscriptions(customer_id)
                            ON DELETE CASCADE,
    subscription_id         TEXT,                            -- Stripe sub_xxx
    amount_paid_cents       INTEGER      NOT NULL DEFAULT 0,
    currency                TEXT         NOT NULL DEFAULT 'usd',
    status                  TEXT         NOT NULL,           -- paid|open|uncollectible
    next_payment_attempt    TIMESTAMPTZ,
    invoice_date            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_customer
    ON billing.invoice_history (customer_id, invoice_date DESC);

CREATE INDEX IF NOT EXISTS idx_invoices_sub
    ON billing.invoice_history (subscription_id);

-- ─── 5. api_usage (rolling-window rate-limit tracking) ────────────────────────

CREATE TABLE IF NOT EXISTS billing.api_usage (
    id              BIGSERIAL    PRIMARY KEY,
    customer_id     TEXT         NOT NULL
                    REFERENCES billing.subscriptions(customer_id)
                    ON DELETE CASCADE,
    endpoint        TEXT         NOT NULL,
    requests_count  INTEGER      NOT NULL DEFAULT 1,
    window_start    TIMESTAMPTZ  NOT NULL,
    window_end      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_customer_window
    ON billing.api_usage (customer_id, window_start DESC);

-- Composite unique: one row per customer+endpoint+window (upserted by store)
CREATE UNIQUE INDEX IF NOT EXISTS uidx_api_usage_window
    ON billing.api_usage (customer_id, endpoint, window_start);

-- ─── Helper view: active subscription with entitlements ─────────────────────

CREATE OR REPLACE VIEW billing.active_subscriptions_with_entitlements AS
SELECT
    s.customer_id,
    s.email,
    s.stripe_subscription_id,
    s.tier,
    s.status,
    s.interval,
    s.current_period_end,
    s.cancel_at_period_end,
    s.created_at                    AS subscribed_at,
    s.updated_at                    AS last_event_at,
    -- Entitlement columns
    e.display_name                  AS tier_display_name,
    e.monthly_price_usd_cents,
    e.annual_price_usd_cents,
    e.max_symbols,
    e.scan_interval_minutes,
    e.max_alerts_per_day,
    e.journal_retention_days,
    e.api_access,
    e.api_rate_limit_rpm,
    e.ml_signals_v3,
    e.regime_detection,
    e.multi_exchange,
    e.cvd_whale_signals,
    e.backtesting_enabled,
    e.kelly_position_sizing,
    e.walk_forward_validation,
    e.telegram_alerts,
    e.email_alerts,
    e.tradingview_webhooks,
    e.alpha_decay_monitoring,
    e.max_team_seats,
    e.priority_support,
    e.dedicated_onboarding,
    e.custom_regime_tuning,
    e.sla_support,
    e.white_label
FROM  billing.subscriptions s
JOIN  billing.entitlements   e ON e.tier = s.tier
WHERE s.status IN ('active', 'trialing');

COMMIT;

-- =============================================================================
-- Rollback script (run manually if migration needs to be reversed)
-- =============================================================================
-- BEGIN;
-- DROP VIEW  IF EXISTS billing.active_subscriptions_with_entitlements;
-- DROP TABLE IF EXISTS billing.api_usage        CASCADE;
-- DROP TABLE IF EXISTS billing.invoice_history  CASCADE;
-- DROP TABLE IF EXISTS billing.entitlements     CASCADE;
-- DROP TABLE IF EXISTS billing.webhook_events   CASCADE;
-- DROP TABLE IF EXISTS billing.subscriptions    CASCADE;
-- DROP FUNCTION IF EXISTS billing.set_updated_at CASCADE;
-- DROP TYPE IF EXISTS billing.billing_interval;
-- DROP TYPE IF EXISTS billing.subscription_status;
-- DROP TYPE IF EXISTS billing.subscription_tier;
-- DROP SCHEMA IF EXISTS billing;
-- COMMIT;

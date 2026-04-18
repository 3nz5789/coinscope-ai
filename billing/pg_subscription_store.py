"""
CoinScopeAI Billing — Async PostgreSQL Subscription Store

Drop-in async replacement for the SQLite SubscriptionStore.
Uses asyncpg for high-performance, non-blocking Postgres access.

Database: billing schema  (see migrations/001_initial_billing_tables.sql)

Environment variables
─────────────────────
  DATABASE_URL   postgresql://user:pass@host:5432/dbname
                 (falls back to BILLING_DATABASE_URL if DATABASE_URL absent)

Usage (FastAPI lifespan)
────────────────────────
  from billing.pg_subscription_store import PgSubscriptionStore

  store = PgSubscriptionStore(os.getenv("DATABASE_URL"))
  await store.connect()       # creates pool
  ...
  await store.close()         # drains pool

All public methods are async and safe to call from concurrent FastAPI handlers.
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from .models import (
    BillingInterval,
    InvoiceData,
    SubscriptionRecord,
    SubscriptionStatus,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)

# Pool sizing — suitable for a CPX32 VPS running a single billing worker
_MIN_POOL_SIZE = 2
_MAX_POOL_SIZE = 10


def _resolve_dsn() -> str:
    """Return the Postgres DSN from environment, with a clear error if missing."""
    dsn = os.getenv("DATABASE_URL") or os.getenv("BILLING_DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "Postgres DSN not set. "
            "Define DATABASE_URL or BILLING_DATABASE_URL in your environment."
        )
    return dsn


# ─── Codec helpers ────────────────────────────────────────────────────────────

def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _row_to_record(row: asyncpg.Record) -> SubscriptionRecord:
    return SubscriptionRecord(
        customer_id=row["customer_id"],
        email=row["email"],
        stripe_subscription_id=row["stripe_subscription_id"],
        tier=SubscriptionTier(row["tier"]),
        status=SubscriptionStatus(row["status"]),
        interval=BillingInterval(row["interval"]),
        current_period_end=_to_utc(row["current_period_end"]),
        cancel_at_period_end=bool(row["cancel_at_period_end"]),
        created_at=_to_utc(row["created_at"]),
        updated_at=_to_utc(row["updated_at"]),
    )


# ─── Store ────────────────────────────────────────────────────────────────────

class PgSubscriptionStore:
    """
    Async PostgreSQL-backed store for CoinScopeAI billing state.

    All writes go to the `billing` schema.
    The pool is created once on `connect()` and shared across all coroutines.
    """

    def __init__(self, dsn: Optional[str] = None):
        self._dsn: str = dsn or _resolve_dsn()
        self._pool: Optional[asyncpg.Pool] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Create the connection pool. Call once at application startup."""
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=_MIN_POOL_SIZE,
            max_size=_MAX_POOL_SIZE,
            command_timeout=30,
        )
        logger.info(
            f"[BillingDB] Postgres pool created "
            f"(min={_MIN_POOL_SIZE}, max={_MAX_POOL_SIZE})"
        )

    async def close(self) -> None:
        """Drain and close the connection pool. Call at application shutdown."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("[BillingDB] Postgres pool closed")

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError(
                "PgSubscriptionStore not connected. Call `await store.connect()` first."
            )
        return self._pool

    # ── Idempotency ────────────────────────────────────────────────────────

    async def is_event_processed(self, event_id: str) -> bool:
        """Return True if this Stripe event has already been handled."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM billing.webhook_events WHERE event_id = $1",
                event_id,
            )
        return row is not None

    async def mark_event_processed(
        self,
        event_id: str,
        event_type: str,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> None:
        """Record that a Stripe event was handled (idempotency guard)."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO billing.webhook_events
                    (event_id, event_type, processed_at, customer_id, subscription_id)
                VALUES ($1, $2, NOW(), $3, $4)
                ON CONFLICT (event_id) DO NOTHING
                """,
                event_id, event_type, customer_id, subscription_id,
            )
        logger.debug(f"[BillingDB] Marked {event_id} ({event_type}) processed")

    # ── Subscription CRUD ──────────────────────────────────────────────────

    async def upsert_subscription(self, record: SubscriptionRecord) -> None:
        """
        Insert or update a subscription record.
        Uses customer_id as the primary key — one row per customer.
        The `updated_at` column is automatically bumped by the DB trigger.
        """
        tier_val  = getattr(record.tier,     "value", record.tier)
        stat_val  = getattr(record.status,   "value", record.status)
        intv_val  = getattr(record.interval, "value", record.interval)
        period_end = _to_utc(record.current_period_end)

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO billing.subscriptions
                    (customer_id, email, stripe_subscription_id, tier, status,
                     interval, current_period_end, cancel_at_period_end, created_at, updated_at)
                VALUES ($1, $2, $3, $4::billing.subscription_tier,
                        $5::billing.subscription_status, $6::billing.billing_interval,
                        $7, $8, NOW(), NOW())
                ON CONFLICT (customer_id) DO UPDATE SET
                    email                  = EXCLUDED.email,
                    stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                    tier                   = EXCLUDED.tier,
                    status                 = EXCLUDED.status,
                    interval               = EXCLUDED.interval,
                    current_period_end     = EXCLUDED.current_period_end,
                    cancel_at_period_end   = EXCLUDED.cancel_at_period_end,
                    updated_at             = NOW()
                """,
                record.customer_id,
                record.email,
                record.stripe_subscription_id,
                tier_val,
                stat_val,
                intv_val,
                period_end,
                record.cancel_at_period_end,
            )
        logger.info(
            f"[BillingDB] Upserted subscription — "
            f"customer={record.customer_id} tier={tier_val} status={stat_val}"
        )

    async def get_subscription_by_customer(
        self, customer_id: str
    ) -> Optional[SubscriptionRecord]:
        """Fetch subscription by Stripe customer ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM billing.subscriptions WHERE customer_id = $1",
                customer_id,
            )
        return _row_to_record(row) if row else None

    async def get_subscription_by_stripe_id(
        self, stripe_subscription_id: str
    ) -> Optional[SubscriptionRecord]:
        """Fetch subscription by Stripe subscription ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM billing.subscriptions
                WHERE stripe_subscription_id = $1
                """,
                stripe_subscription_id,
            )
        return _row_to_record(row) if row else None

    async def cancel_subscription(self, customer_id: str) -> None:
        """Mark a subscription as canceled."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE billing.subscriptions
                SET status = 'canceled'::billing.subscription_status,
                    cancel_at_period_end = TRUE,
                    updated_at = NOW()
                WHERE customer_id = $1
                """,
                customer_id,
            )
        logger.info(f"[BillingDB] Canceled subscription — customer={customer_id}")

    async def get_customer_id_by_email(self, email: str) -> Optional[str]:
        """
        Return the Stripe customer_id for a given email, or None.
        Case-insensitive. Returns the most recently updated row on collision.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT customer_id FROM billing.subscriptions
                WHERE lower(email) = lower($1)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                email,
            )
        return row["customer_id"] if row else None

    async def list_active_subscriptions(self) -> list[SubscriptionRecord]:
        """Return all active and trialing subscriptions."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM billing.subscriptions
                WHERE status IN (
                    'active'::billing.subscription_status,
                    'trialing'::billing.subscription_status
                )
                ORDER BY updated_at DESC
                """
            )
        return [_row_to_record(r) for r in rows]

    # ── Invoice history ────────────────────────────────────────────────────

    async def append_invoice(self, data: InvoiceData) -> None:
        """
        Persist an invoice record.
        Uses ON CONFLICT DO NOTHING — safe to call on webhook replay.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO billing.invoice_history
                    (invoice_id, customer_id, subscription_id,
                     amount_paid_cents, currency, status,
                     next_payment_attempt, invoice_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (invoice_id) DO NOTHING
                """,
                data.invoice_id,
                data.customer_id,
                data.subscription_id,
                data.amount_paid,
                data.currency,
                data.status,
                _to_utc(data.next_payment_attempt),
            )
        logger.debug(
            f"[BillingDB] Invoice appended — "
            f"id={data.invoice_id} customer={data.customer_id} "
            f"amount={data.amount_paid} {data.currency}"
        )

    async def get_invoice_history(
        self,
        customer_id: str,
        limit: int = 20,
    ) -> list[dict]:
        """Return recent invoice records for a customer (newest first)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT invoice_id, subscription_id, amount_paid_cents,
                       currency, status, next_payment_attempt, invoice_date
                FROM billing.invoice_history
                WHERE customer_id = $1
                ORDER BY invoice_date DESC
                LIMIT $2
                """,
                customer_id,
                limit,
            )
        return [dict(r) for r in rows]

    # ── API usage / rate-limiting ──────────────────────────────────────────

    async def increment_api_usage(
        self,
        customer_id: str,
        endpoint: str,
        window_minutes: int = 1,
    ) -> int:
        """
        Increment the request counter for a customer+endpoint in the current
        rolling window. Returns the new total so the caller can gate on it.

        Window boundaries are aligned to wall-clock minutes for simplicity.
        """
        import math
        now = datetime.now(tz=timezone.utc)
        # Align window to `window_minutes`-sized buckets
        bucket = math.floor(now.timestamp() / (window_minutes * 60)) * (window_minutes * 60)
        window_start = datetime.fromtimestamp(bucket, tz=timezone.utc)
        window_end   = datetime.fromtimestamp(bucket + window_minutes * 60, tz=timezone.utc)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO billing.api_usage
                    (customer_id, endpoint, requests_count, window_start, window_end)
                VALUES ($1, $2, 1, $3, $4)
                ON CONFLICT (customer_id, endpoint, window_start) DO UPDATE
                    SET requests_count = billing.api_usage.requests_count + 1
                RETURNING requests_count
                """,
                customer_id, endpoint, window_start, window_end,
            )
        count = row["requests_count"]
        logger.debug(
            f"[BillingDB] API usage — customer={customer_id} "
            f"endpoint={endpoint} count={count} window={window_start.isoformat()}"
        )
        return count

    # ── Entitlement lookup ─────────────────────────────────────────────────

    async def get_entitlements(self, customer_id: str) -> Optional[dict]:
        """
        Return the full entitlement row for a customer by joining subscriptions
        → entitlements. Returns None if the customer is not found or inactive.

        Prefer billing.entitlements.get_for_customer() for application logic.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT e.*
                FROM billing.subscriptions s
                JOIN billing.entitlements e ON e.tier = s.tier
                WHERE s.customer_id = $1
                  AND s.status IN (
                      'active'::billing.subscription_status,
                      'trialing'::billing.subscription_status
                  )
                """,
                customer_id,
            )
        return dict(row) if row else None

    async def get_active_subscription_with_entitlements(
        self, customer_id: str
    ) -> Optional[dict]:
        """
        Single-query fetch: subscription state + entitlements from the view.
        Returns None if no active/trialing subscription found.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM billing.active_subscriptions_with_entitlements
                WHERE customer_id = $1
                """,
                customer_id,
            )
        return dict(row) if row else None

"""
Subscription Store — SQLite-backed persistence for subscription state.

Tables:
  subscriptions    — one row per customer (upserted on each event)
  webhook_events   — one row per processed Stripe event (idempotency guard)

All writes are transactional. Thread-safe via connection-per-call pattern.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from .models import (
    SubscriptionRecord,
    SubscriptionTier,
    SubscriptionStatus,
    BillingInterval,
    WebhookEventRecord,
)

logger = logging.getLogger(__name__)

# Default path — can be overridden via BILLING_DB_PATH env var
DEFAULT_DB_PATH = os.getenv("BILLING_DB_PATH", "billing_subscriptions.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    customer_id             TEXT PRIMARY KEY,
    email                   TEXT,
    stripe_subscription_id  TEXT NOT NULL,
    tier                    TEXT NOT NULL DEFAULT 'unknown',
    status                  TEXT NOT NULL DEFAULT 'incomplete',
    interval                TEXT NOT NULL DEFAULT 'month',
    current_period_end      TEXT,
    cancel_at_period_end    INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id         TEXT PRIMARY KEY,
    event_type       TEXT NOT NULL,
    processed_at     TEXT NOT NULL,
    customer_id      TEXT,
    subscription_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_subs_stripe_id
    ON subscriptions (stripe_subscription_id);

CREATE INDEX IF NOT EXISTS idx_events_customer
    ON webhook_events (customer_id);
"""


class SubscriptionStore:
    """
    Thread-safe SQLite store for CoinScopeAI billing state.

    Each public method opens its own connection so it's safe to call
    from concurrent FastAPI request handlers.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    # ── Internal ─────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        """Yield a transactional SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # Safe for concurrent reads
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.info(f"[BillingDB] Initialised at {self.db_path}")

    # ── Idempotency ───────────────────────────────────────────────────────

    def is_event_processed(self, event_id: str) -> bool:
        """Return True if this Stripe event has already been handled."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM webhook_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None

    def mark_event_processed(
        self,
        event_id: str,
        event_type: str,
        customer_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ):
        """Record that a Stripe event was handled (idempotency guard)."""
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO webhook_events
                    (event_id, event_type, processed_at, customer_id, subscription_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, event_type, now, customer_id, subscription_id),
            )
        logger.debug(f"[BillingDB] Marked {event_id} ({event_type}) processed")

    # ── Subscription CRUD ─────────────────────────────────────────────────

    def upsert_subscription(self, record: SubscriptionRecord):
        """
        Insert or update a subscription record.
        Uses customer_id as the primary key — one row per customer.
        """
        now = datetime.utcnow().isoformat()
        period_end = (
            record.current_period_end.isoformat()
            if record.current_period_end
            else None
        )
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO subscriptions
                    (customer_id, email, stripe_subscription_id, tier, status,
                     interval, current_period_end, cancel_at_period_end,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(customer_id) DO UPDATE SET
                    email                  = excluded.email,
                    stripe_subscription_id = excluded.stripe_subscription_id,
                    tier                   = excluded.tier,
                    status                 = excluded.status,
                    interval               = excluded.interval,
                    current_period_end     = excluded.current_period_end,
                    cancel_at_period_end   = excluded.cancel_at_period_end,
                    updated_at             = excluded.updated_at
                """,
                (
                    record.customer_id,
                    record.email,
                    record.stripe_subscription_id,
                    getattr(record.tier, "value", record.tier),
                    getattr(record.status, "value", record.status),
                    getattr(record.interval, "value", record.interval),
                    period_end,
                    int(record.cancel_at_period_end),
                    record.created_at.isoformat(),
                    now,
                ),
            )
        logger.info(
            f"[BillingDB] Upserted subscription — customer={record.customer_id} "
            f"tier={record.tier} status={record.status}"
        )

    def get_subscription_by_customer(self, customer_id: str) -> Optional[SubscriptionRecord]:
        """Fetch subscription by Stripe customer ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE customer_id = ?", (customer_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get_subscription_by_stripe_id(self, stripe_subscription_id: str) -> Optional[SubscriptionRecord]:
        """Fetch subscription by Stripe subscription ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM subscriptions WHERE stripe_subscription_id = ?",
                (stripe_subscription_id,),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def cancel_subscription(self, customer_id: str):
        """Mark a subscription as canceled."""
        now = datetime.utcnow().isoformat()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE subscriptions
                SET status = 'canceled', cancel_at_period_end = 1, updated_at = ?
                WHERE customer_id = ?
                """,
                (now, customer_id),
            )
        logger.info(f"[BillingDB] Canceled subscription for customer={customer_id}")

    def get_customer_id_by_email(self, email: str) -> Optional[str]:
        """
        Return the Stripe customer_id for a given email, or None if not found.
        Case-insensitive match. Returns the most recently updated record if
        multiple rows share the same email (edge case — should not happen).
        """
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT customer_id FROM subscriptions
                WHERE lower(email) = lower(?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (email,),
            ).fetchone()
        return row["customer_id"] if row else None

    def list_active_subscriptions(self) -> list[SubscriptionRecord]:
        """Return all active/trialing subscriptions."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM subscriptions WHERE status IN ('active', 'trialing')"
            ).fetchall()
        return [self._row_to_record(r) for r in rows if r]

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SubscriptionRecord:
        period_end = (
            datetime.fromisoformat(row["current_period_end"])
            if row["current_period_end"]
            else None
        )
        return SubscriptionRecord(
            customer_id=row["customer_id"],
            email=row["email"],
            stripe_subscription_id=row["stripe_subscription_id"],
            tier=SubscriptionTier(row["tier"]),
            status=SubscriptionStatus(row["status"]),
            interval=BillingInterval(row["interval"]),
            current_period_end=period_end,
            cancel_at_period_end=bool(row["cancel_at_period_end"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

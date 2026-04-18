"""
Tests — Billing Schema & Entitlements

Covers:
  1. Static entitlement data is self-consistent (no mis-seeds)
  2. Tier ordering and upgrade/downgrade helpers
  3. Entitlements.for_tier() returns the right data
  4. Entitlements.for_customer() works against a mock store
  5. SQL migration file exists and is syntactically plausible
  6. PgSubscriptionStore public interface matches SubscriptionStore

Run with:
    pytest tests/test_billing_schema.py -v
"""

import os
import sys
import asyncio
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Make sure the project root is on the path when running from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

from billing.entitlements import (
    TIER_ENTITLEMENTS,
    Entitlements,
    is_downgrade,
    is_upgrade,
    tier_rank,
)
from billing.models import (
    BillingInterval,
    SubscriptionRecord,
    SubscriptionStatus,
    SubscriptionTier,
)
from billing.pg_subscription_store import PgSubscriptionStore
from billing.subscription_store import SubscriptionStore

# ─── Fixtures ─────────────────────────────────────────────────────────────────

MIGRATION_FILE = (
    Path(__file__).parent.parent
    / "billing"
    / "migrations"
    / "001_initial_billing_tables.sql"
)

ALL_TIERS = ["starter", "pro", "elite", "team", "unknown"]
PAID_TIERS = ["starter", "pro", "elite", "team"]


# ─── 1. Static entitlement consistency ───────────────────────────────────────

class TestStaticEntitlements:

    def test_all_tiers_present(self):
        """Every expected tier has a static entry."""
        for tier in ALL_TIERS:
            assert tier in TIER_ENTITLEMENTS, f"Missing tier: {tier}"

    def test_paid_tiers_have_nonzero_price(self):
        for tier in PAID_TIERS:
            ents = TIER_ENTITLEMENTS[tier]
            assert ents.monthly_price_usd_cents > 0, f"{tier}: monthly price is 0"
            assert ents.annual_price_usd_cents > 0, f"{tier}: annual price is 0"

    def test_annual_cheaper_than_monthly_x12(self):
        """Annual price should be ~20% less than 12× monthly."""
        for tier in PAID_TIERS:
            ents = TIER_ENTITLEMENTS[tier]
            annual_full = ents.monthly_price_usd_cents * 12
            savings_pct = (annual_full - ents.annual_price_usd_cents) / annual_full
            assert savings_pct >= 0.15, (
                f"{tier}: annual savings only {savings_pct:.0%} — expected ≥15%"
            )

    def test_unknown_tier_grants_nothing(self):
        u = TIER_ENTITLEMENTS["unknown"]
        assert not u.api_access
        assert u.max_symbols == 0
        assert u.max_alerts_per_day == 0

    def test_elite_has_api_access(self):
        e = TIER_ENTITLEMENTS["elite"]
        assert e.api_access
        assert e.api_rate_limit_rpm is not None and e.api_rate_limit_rpm > 0

    def test_team_beats_elite_on_seats_and_rpm(self):
        e = TIER_ENTITLEMENTS["elite"]
        t = TIER_ENTITLEMENTS["team"]
        assert t.max_team_seats > e.max_team_seats
        assert t.api_rate_limit_rpm > e.api_rate_limit_rpm

    def test_pro_has_no_api_access(self):
        """Pro does not include engine API — that's Elite+."""
        p = TIER_ENTITLEMENTS["pro"]
        assert not p.api_access

    def test_starter_has_no_ml_signals(self):
        s = TIER_ENTITLEMENTS["starter"]
        assert not s.ml_signals_v3
        assert not s.regime_detection

    def test_elite_has_multi_exchange(self):
        e = TIER_ENTITLEMENTS["elite"]
        assert e.multi_exchange
        assert e.cvd_whale_signals

    def test_all_tiers_have_telegram(self):
        """Telegram alerts are available on every paid tier."""
        for tier in PAID_TIERS:
            assert TIER_ENTITLEMENTS[tier].telegram_alerts, \
                f"{tier}: telegram_alerts is False"

    def test_unlimited_markers(self):
        """Elite and Team should use -1 for unlimited quantities."""
        for tier in ("elite", "team"):
            e = TIER_ENTITLEMENTS[tier]
            assert e.max_symbols == -1
            assert e.max_alerts_per_day == -1
            assert e.journal_retention_days == -1

    def test_convenience_properties(self):
        e = TIER_ENTITLEMENTS["elite"]
        assert e.unlimited_symbols
        assert e.unlimited_alerts
        assert e.unlimited_journal
        assert e.allows_symbol_count(9999)
        assert e.allows_alert_count(9999)

        s = TIER_ENTITLEMENTS["starter"]
        assert not s.unlimited_symbols
        assert s.allows_symbol_count(5)
        assert not s.allows_symbol_count(6)
        assert s.allows_alert_count(2)
        assert not s.allows_alert_count(3)   # 3 is AT the limit (< 3 only)

    def test_for_tier_unknown_fallback(self):
        """for_tier() returns 'unknown' for unrecognised tier strings."""
        e = Entitlements.for_tier("dragon_tier_9999")
        assert e.tier == "unknown"

    def test_to_dict_is_serialisable(self):
        import json
        d = TIER_ENTITLEMENTS["pro"].to_dict()
        assert isinstance(d, dict)
        # Should JSON-serialise without errors
        json.dumps(d, default=str)


# ─── 2. Tier ordering helpers ─────────────────────────────────────────────────

class TestTierOrdering:

    def test_rank_order(self):
        assert tier_rank("unknown") < tier_rank("starter")
        assert tier_rank("starter") < tier_rank("pro")
        assert tier_rank("pro") < tier_rank("elite")
        assert tier_rank("elite") < tier_rank("team")

    def test_upgrade_detection(self):
        assert is_upgrade("starter", "pro")
        assert is_upgrade("pro", "elite")
        assert is_upgrade("elite", "team")
        assert not is_upgrade("team", "elite")
        assert not is_upgrade("pro", "pro")

    def test_downgrade_detection(self):
        assert is_downgrade("team", "elite")
        assert is_downgrade("elite", "pro")
        assert is_downgrade("pro", "starter")
        assert not is_downgrade("starter", "pro")
        assert not is_downgrade("pro", "pro")

    def test_unknown_rank_is_zero(self):
        assert tier_rank("unknown") == 0
        assert tier_rank("nonexistent_garbage") == 0


# ─── 3. Entitlements.for_customer mock ───────────────────────────────────────

class TestEntitlementsForCustomer:

    def _make_mock_row(self, tier: str) -> dict:
        """Build a fake asyncpg-style row dict from the static lookup."""
        e = TIER_ENTITLEMENTS[tier]
        return {
            "tier":                       e.tier,
            "monthly_price_usd_cents":    e.monthly_price_usd_cents,
            "annual_price_usd_cents":     e.annual_price_usd_cents,
            "max_symbols":                e.max_symbols,
            "scan_interval_minutes":      e.scan_interval_minutes,
            "max_alerts_per_day":         e.max_alerts_per_day,
            "journal_retention_days":     e.journal_retention_days,
            "api_access":                 e.api_access,
            "api_rate_limit_rpm":         e.api_rate_limit_rpm,
            "ml_signals_v3":              e.ml_signals_v3,
            "regime_detection":           e.regime_detection,
            "multi_exchange":             e.multi_exchange,
            "cvd_whale_signals":          e.cvd_whale_signals,
            "backtesting_enabled":        e.backtesting_enabled,
            "kelly_position_sizing":      e.kelly_position_sizing,
            "walk_forward_validation":    e.walk_forward_validation,
            "telegram_alerts":            e.telegram_alerts,
            "email_alerts":               e.email_alerts,
            "tradingview_webhooks":       e.tradingview_webhooks,
            "alpha_decay_monitoring":     e.alpha_decay_monitoring,
            "max_team_seats":             e.max_team_seats,
            "priority_support":           e.priority_support,
            "dedicated_onboarding":       e.dedicated_onboarding,
            "custom_regime_tuning":       e.custom_regime_tuning,
            "sla_support":                e.sla_support,
            "white_label":                e.white_label,
        }

    @pytest.mark.asyncio
    async def test_for_customer_active_pro(self):
        """for_customer returns correct entitlements when customer has Pro sub."""
        mock_store = MagicMock()
        mock_store.get_entitlements = AsyncMock(
            return_value=self._make_mock_row("pro")
        )
        ents = await Entitlements.for_customer(mock_store, "cus_test_pro")
        assert ents.tier == "pro"
        assert ents.ml_signals_v3
        assert not ents.api_access
        assert ents.max_symbols == 25

    @pytest.mark.asyncio
    async def test_for_customer_none_returns_unknown(self):
        """for_customer falls back to 'unknown' when no active subscription."""
        mock_store = MagicMock()
        mock_store.get_entitlements = AsyncMock(return_value=None)
        ents = await Entitlements.for_customer(mock_store, "cus_no_sub")
        assert ents.tier == "unknown"
        assert not ents.api_access

    @pytest.mark.asyncio
    async def test_for_customer_elite_has_api(self):
        mock_store = MagicMock()
        mock_store.get_entitlements = AsyncMock(
            return_value=self._make_mock_row("elite")
        )
        ents = await Entitlements.for_customer(mock_store, "cus_elite")
        assert ents.api_access
        assert ents.api_rate_limit_rpm == 300
        assert ents.multi_exchange
        assert ents.unlimited_symbols


# ─── 4. Migration file existence + content ────────────────────────────────────

class TestMigrationFile:

    def test_migration_file_exists(self):
        assert MIGRATION_FILE.exists(), (
            f"Migration file not found: {MIGRATION_FILE}"
        )

    def test_migration_has_required_tables(self):
        sql = MIGRATION_FILE.read_text()
        for table in ("subscriptions", "webhook_events", "entitlements",
                      "invoice_history", "api_usage"):
            assert table in sql, f"Table '{table}' not found in migration SQL"

    def test_migration_has_enum_types(self):
        sql = MIGRATION_FILE.read_text()
        for typ in ("subscription_tier", "subscription_status", "billing_interval"):
            assert typ in sql, f"ENUM type '{typ}' not found in migration SQL"

    def test_migration_seeds_all_tiers(self):
        sql = MIGRATION_FILE.read_text()
        for tier in ALL_TIERS:
            assert f"'{tier}'" in sql, f"Tier '{tier}' not seeded in migration"

    def test_migration_has_rollback_comments(self):
        sql = MIGRATION_FILE.read_text()
        assert "Rollback" in sql or "rollback" in sql.lower(), \
            "Migration should include rollback instructions"

    def test_migration_is_transactional(self):
        sql = MIGRATION_FILE.read_text()
        # File may start with comment headers — BEGIN must appear before any DDL
        assert "BEGIN;" in sql, \
            "Migration should contain BEGIN;"
        assert "COMMIT;" in sql, \
            "Migration should contain COMMIT;"
        # BEGIN should come before the first CREATE TABLE
        begin_pos  = sql.index("BEGIN;")
        create_pos = sql.index("CREATE TABLE")
        assert begin_pos < create_pos, \
            "BEGIN; must appear before the first CREATE TABLE"

    def test_migration_has_view(self):
        sql = MIGRATION_FILE.read_text()
        assert "active_subscriptions_with_entitlements" in sql


# ─── 5. PgSubscriptionStore interface parity ─────────────────────────────────

class TestPgStoreInterface:
    """
    Ensure PgSubscriptionStore exposes the same public surface as
    SubscriptionStore (method names, arity). No DB connection needed.
    """

    SHARED_METHODS = [
        "is_event_processed",
        "mark_event_processed",
        "upsert_subscription",
        "get_subscription_by_customer",
        "get_subscription_by_stripe_id",
        "cancel_subscription",
        "get_customer_id_by_email",
        "list_active_subscriptions",
    ]

    def test_pg_store_has_all_sqlite_methods(self):
        for method in self.SHARED_METHODS:
            assert hasattr(PgSubscriptionStore, method), \
                f"PgSubscriptionStore missing method: {method}"

    def test_pg_store_methods_are_coroutines(self):
        """All shared methods on PgSubscriptionStore must be async."""
        store = PgSubscriptionStore.__new__(PgSubscriptionStore)
        for method in self.SHARED_METHODS:
            fn = getattr(store, method)
            assert asyncio.iscoroutinefunction(fn), \
                f"PgSubscriptionStore.{method} should be async"

    def test_pg_store_has_extra_methods(self):
        """PgSubscriptionStore should extend the interface with PG-specific ops."""
        for method in ("append_invoice", "increment_api_usage",
                       "get_entitlements", "connect", "close"):
            assert hasattr(PgSubscriptionStore, method), \
                f"PgSubscriptionStore missing expected method: {method}"

    def test_sqlite_store_methods_are_sync(self):
        """Original SubscriptionStore methods should remain synchronous."""
        for method in self.SHARED_METHODS:
            fn = getattr(SubscriptionStore, method)
            assert not asyncio.iscoroutinefunction(fn), \
                f"SubscriptionStore.{method} should be sync (not async)"

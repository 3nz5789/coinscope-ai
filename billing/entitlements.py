"""
CoinScopeAI Billing — Entitlements Helper

Provides a clean, typed interface for querying what a customer is
allowed to do based on their active subscription tier.

Usage
─────
  from billing.entitlements import Entitlements, TIER_ENTITLEMENTS

  # From Postgres (async — production path)
  ents = await Entitlements.for_customer(store, customer_id)
  if not ents.api_access:
      raise HTTPException(403, "API access requires Elite or Team tier")

  # From static lookup (sync — for middleware, tests, mock data)
  ents = Entitlements.for_tier("pro")
  print(ents.max_symbols)   # 25

The static TIER_ENTITLEMENTS dict mirrors the DB seed exactly.
Application code MUST treat the DB as authoritative in production;
the static dict is a fallback for offline / test environments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .pg_subscription_store import PgSubscriptionStore


# ─── Entitlement dataclass ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Entitlements:
    """
    Snapshot of what a customer may do.
    All fields map 1:1 to billing.entitlements columns.
    -1 in integer fields means "unlimited".
    """
    tier:                       str

    # Pricing
    monthly_price_usd_cents:    int
    annual_price_usd_cents:     int

    # Scanner
    max_symbols:                int     # -1 = unlimited
    scan_interval_minutes:      int
    max_alerts_per_day:         int     # -1 = unlimited

    # Journal
    journal_retention_days:     int     # -1 = unlimited

    # API
    api_access:                 bool
    api_rate_limit_rpm:         Optional[int]   # None = no access

    # Feature flags
    ml_signals_v3:              bool
    regime_detection:           bool
    multi_exchange:             bool
    cvd_whale_signals:          bool
    backtesting_enabled:        bool
    kelly_position_sizing:      bool
    walk_forward_validation:    bool
    telegram_alerts:            bool
    email_alerts:               bool
    tradingview_webhooks:       bool
    alpha_decay_monitoring:     bool

    # Team
    max_team_seats:             int
    priority_support:           bool
    dedicated_onboarding:       bool
    custom_regime_tuning:       bool
    sla_support:                bool
    white_label:                bool

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def unlimited_symbols(self) -> bool:
        return self.max_symbols == -1

    @property
    def unlimited_alerts(self) -> bool:
        return self.max_alerts_per_day == -1

    @property
    def unlimited_journal(self) -> bool:
        return self.journal_retention_days == -1

    def allows_symbol_count(self, n: int) -> bool:
        return self.unlimited_symbols or n <= self.max_symbols

    def allows_alert_count(self, today_count: int) -> bool:
        return self.unlimited_alerts or today_count < self.max_alerts_per_day

    def has_feature(self, feature: str) -> bool:
        """
        Generic feature gate. `feature` should be a field name on this class.
        Raises AttributeError on unknown features — fail loudly.
        """
        val = getattr(self, feature)
        if isinstance(val, bool):
            return val
        if isinstance(val, int):
            return val != 0
        return bool(val)

    def to_dict(self) -> dict:
        """Serialisable representation for API responses."""
        import dataclasses
        return dataclasses.asdict(self)

    # ── Factory methods ────────────────────────────────────────────────────

    @classmethod
    def for_tier(cls, tier: str) -> "Entitlements":
        """
        Return entitlements for a tier from the static lookup.
        Use this in tests or when a DB round-trip is not possible.
        Falls back to 'unknown' for unrecognised tiers.
        """
        return TIER_ENTITLEMENTS.get(tier, TIER_ENTITLEMENTS["unknown"])

    @classmethod
    async def for_customer(
        cls,
        store: "PgSubscriptionStore",
        customer_id: str,
    ) -> "Entitlements":
        """
        Fetch live entitlements for an active customer from Postgres.
        Falls back to the 'unknown' tier if the customer has no active sub.
        """
        row = await store.get_entitlements(customer_id)
        if not row:
            return TIER_ENTITLEMENTS["unknown"]
        return cls(
            tier                       = row["tier"],
            monthly_price_usd_cents    = row["monthly_price_usd_cents"],
            annual_price_usd_cents     = row["annual_price_usd_cents"],
            max_symbols                = row["max_symbols"],
            scan_interval_minutes      = row["scan_interval_minutes"],
            max_alerts_per_day         = row["max_alerts_per_day"],
            journal_retention_days     = row["journal_retention_days"],
            api_access                 = row["api_access"],
            api_rate_limit_rpm         = row["api_rate_limit_rpm"],
            ml_signals_v3              = row["ml_signals_v3"],
            regime_detection           = row["regime_detection"],
            multi_exchange             = row["multi_exchange"],
            cvd_whale_signals          = row["cvd_whale_signals"],
            backtesting_enabled        = row["backtesting_enabled"],
            kelly_position_sizing      = row["kelly_position_sizing"],
            walk_forward_validation    = row["walk_forward_validation"],
            telegram_alerts            = row["telegram_alerts"],
            email_alerts               = row["email_alerts"],
            tradingview_webhooks       = row["tradingview_webhooks"],
            alpha_decay_monitoring     = row["alpha_decay_monitoring"],
            max_team_seats             = row["max_team_seats"],
            priority_support           = row["priority_support"],
            dedicated_onboarding       = row["dedicated_onboarding"],
            custom_regime_tuning       = row["custom_regime_tuning"],
            sla_support                = row["sla_support"],
            white_label                = row["white_label"],
        )


# ─── Static tier lookup (mirrors DB seed in 001_initial_billing_tables.sql) ───
# Update BOTH here and in the migration when adding features.

TIER_ENTITLEMENTS: dict[str, Entitlements] = {

    "starter": Entitlements(
        tier                    = "starter",
        monthly_price_usd_cents = 1900,
        annual_price_usd_cents  = 19000,
        max_symbols             = 5,
        scan_interval_minutes   = 240,   # 4h
        max_alerts_per_day      = 3,
        journal_retention_days  = 30,
        api_access              = False,
        api_rate_limit_rpm      = None,
        ml_signals_v3           = False,
        regime_detection        = False,
        multi_exchange          = False,
        cvd_whale_signals       = False,
        backtesting_enabled     = False,
        kelly_position_sizing   = False,
        walk_forward_validation = False,
        telegram_alerts         = True,
        email_alerts            = False,
        tradingview_webhooks    = False,
        alpha_decay_monitoring  = False,
        max_team_seats          = 1,
        priority_support        = False,
        dedicated_onboarding    = False,
        custom_regime_tuning    = False,
        sla_support             = False,
        white_label             = False,
    ),

    "pro": Entitlements(
        tier                    = "pro",
        monthly_price_usd_cents = 4900,
        annual_price_usd_cents  = 49000,
        max_symbols             = 25,
        scan_interval_minutes   = 60,    # 1h
        max_alerts_per_day      = 20,
        journal_retention_days  = -1,    # unlimited
        api_access              = False,
        api_rate_limit_rpm      = None,
        ml_signals_v3           = True,
        regime_detection        = True,
        multi_exchange          = False,
        cvd_whale_signals       = False,
        backtesting_enabled     = True,
        kelly_position_sizing   = True,
        walk_forward_validation = True,
        telegram_alerts         = True,
        email_alerts            = True,
        tradingview_webhooks    = False,
        alpha_decay_monitoring  = False,
        max_team_seats          = 1,
        priority_support        = False,
        dedicated_onboarding    = False,
        custom_regime_tuning    = False,
        sla_support             = False,
        white_label             = False,
    ),

    "elite": Entitlements(
        tier                    = "elite",
        monthly_price_usd_cents = 9900,
        annual_price_usd_cents  = 99000,
        max_symbols             = -1,    # unlimited
        scan_interval_minutes   = 15,
        max_alerts_per_day      = -1,    # unlimited
        journal_retention_days  = -1,
        api_access              = True,
        api_rate_limit_rpm      = 300,
        ml_signals_v3           = True,
        regime_detection        = True,
        multi_exchange          = True,
        cvd_whale_signals       = True,
        backtesting_enabled     = True,
        kelly_position_sizing   = True,
        walk_forward_validation = True,
        telegram_alerts         = True,
        email_alerts            = True,
        tradingview_webhooks    = True,
        alpha_decay_monitoring  = True,
        max_team_seats          = 3,
        priority_support        = True,
        dedicated_onboarding    = False,
        custom_regime_tuning    = False,
        sla_support             = False,
        white_label             = False,
    ),

    "team": Entitlements(
        tier                    = "team",
        monthly_price_usd_cents = 29900,
        annual_price_usd_cents  = 299000,
        max_symbols             = -1,
        scan_interval_minutes   = 15,
        max_alerts_per_day      = -1,
        journal_retention_days  = -1,
        api_access              = True,
        api_rate_limit_rpm      = 1000,
        ml_signals_v3           = True,
        regime_detection        = True,
        multi_exchange          = True,
        cvd_whale_signals       = True,
        backtesting_enabled     = True,
        kelly_position_sizing   = True,
        walk_forward_validation = True,
        telegram_alerts         = True,
        email_alerts            = True,
        tradingview_webhooks    = True,
        alpha_decay_monitoring  = True,
        max_team_seats          = 10,
        priority_support        = True,
        dedicated_onboarding    = True,
        custom_regime_tuning    = True,
        sla_support             = True,
        white_label             = False,
    ),

    "unknown": Entitlements(
        tier                    = "unknown",
        monthly_price_usd_cents = 0,
        annual_price_usd_cents  = 0,
        max_symbols             = 0,
        scan_interval_minutes   = 0,
        max_alerts_per_day      = 0,
        journal_retention_days  = 0,
        api_access              = False,
        api_rate_limit_rpm      = None,
        ml_signals_v3           = False,
        regime_detection        = False,
        multi_exchange          = False,
        cvd_whale_signals       = False,
        backtesting_enabled     = False,
        kelly_position_sizing   = False,
        walk_forward_validation = False,
        telegram_alerts         = False,
        email_alerts            = False,
        tradingview_webhooks    = False,
        alpha_decay_monitoring  = False,
        max_team_seats          = 0,
        priority_support        = False,
        dedicated_onboarding    = False,
        custom_regime_tuning    = False,
        sla_support             = False,
        white_label             = False,
    ),
}


# ─── Upgrade path helpers ─────────────────────────────────────────────────────

_TIER_ORDER = ["unknown", "starter", "pro", "elite", "team"]


def tier_rank(tier: str) -> int:
    """Return an ordinal for comparing tiers. Higher = more capable."""
    try:
        return _TIER_ORDER.index(tier)
    except ValueError:
        return 0


def is_upgrade(from_tier: str, to_tier: str) -> bool:
    """Return True if moving from_tier → to_tier is an upgrade."""
    return tier_rank(to_tier) > tier_rank(from_tier)


def is_downgrade(from_tier: str, to_tier: str) -> bool:
    """Return True if moving from_tier → to_tier is a downgrade."""
    return tier_rank(to_tier) < tier_rank(from_tier)

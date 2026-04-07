"""
Tests for CoinScopeAI Phase 2 — Regime Enricher

Tests the RegimeEnricher's ability to classify market regimes from
various combinations of data inputs, including graceful degradation
when data sources are missing.
"""

import time

import pytest

from services.market_data.models import (
    AggregatedBasis,
    AggregatedOI,
    AlphaSignal,
    AssetContext,
    BasisData,
    Exchange,
    FundingSnapshot,
    L2OrderBook,
    LiquidationSnapshot,
    MarketRegime,
    OrderBookLevel,
    SignalDirection,
)
from services.market_data.regime.enricher import RegimeConfig, RegimeEnricher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_oi_expanding(n=10, start=100000, growth=0.05):
    """Create OI snapshots with expanding OI."""
    now = time.time()
    return [
        AggregatedOI(
            symbol="BTC",
            timestamp=now - (n - i) * 3600,
            by_exchange={"Binance": start * (1 + growth) ** i},
        )
        for i in range(n)
    ]


def make_oi_contracting(n=10, start=100000, shrink=0.05):
    now = time.time()
    return [
        AggregatedOI(
            symbol="BTC",
            timestamp=now - (n - i) * 3600,
            by_exchange={"Binance": start * (1 - shrink) ** i},
        )
        for i in range(n)
    ]


def make_liq_snapshots(totals):
    now = time.time()
    return [
        LiquidationSnapshot(
            symbol="BTC",
            timestamp=now - (len(totals) - i) * 3600,
            window_seconds=3600,
            long_liquidations_usd=t * 0.5,
            short_liquidations_usd=t * 0.5,
            total_count=int(t / 10000),
        )
        for i, t in enumerate(totals)
    ]


def make_thin_book():
    return L2OrderBook(
        symbol="BTC",
        exchange=Exchange.HYPERLIQUID,
        timestamp=time.time(),
        bids=[OrderBookLevel(price=100, size=0.1)],
        asks=[OrderBookLevel(price=102, size=0.1)],  # 200 bps spread
    )


def make_normal_book():
    return L2OrderBook(
        symbol="BTC",
        exchange=Exchange.HYPERLIQUID,
        timestamp=time.time(),
        bids=[
            OrderBookLevel(price=100.00, size=10),
            OrderBookLevel(price=99.99, size=8),
            OrderBookLevel(price=99.98, size=6),
            OrderBookLevel(price=99.97, size=5),
            OrderBookLevel(price=99.96, size=4),
        ],
        asks=[
            OrderBookLevel(price=100.01, size=10),
            OrderBookLevel(price=100.02, size=8),
            OrderBookLevel(price=100.03, size=6),
            OrderBookLevel(price=100.04, size=5),
            OrderBookLevel(price=100.05, size=4),
        ],
    )


# ---------------------------------------------------------------------------
# Tests: Regime Classification
# ---------------------------------------------------------------------------

class TestRegimeEnricher:
    @pytest.fixture
    def enricher(self):
        return RegimeEnricher()

    # -- No data → UNKNOWN ---------------------------------------------------

    def test_no_data_returns_unknown(self, enricher):
        result = enricher.classify("BTC")
        assert result.regime == MarketRegime.UNKNOWN
        assert result.confidence == 0.0
        assert result.symbol == "BTC"

    # -- Trending regime -----------------------------------------------------

    def test_trending_regime(self, enricher):
        """Expanding OI + normal funding + directional price = trending."""
        oi = make_oi_expanding(10, growth=0.05)
        funding = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0001},  # within normal range
        )
        prices = [50000 + i * 200 for i in range(10)]  # steady uptrend

        result = enricher.classify(
            "BTC",
            funding_snapshot=funding,
            oi_snapshots=oi,
            prices=prices,
        )
        assert result.regime == MarketRegime.TRENDING
        assert result.confidence > 0

    # -- Mean-reverting regime -----------------------------------------------

    def test_mean_reverting_regime(self, enricher):
        """Contracting OI + extreme funding = mean-reverting."""
        oi = make_oi_contracting(10, shrink=0.04)
        funding = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.001},  # extreme funding
        )
        # Choppy prices
        prices = [50000, 50100, 49900, 50050, 49950, 50000, 50100, 49900, 50050, 49950]

        result = enricher.classify(
            "BTC",
            funding_snapshot=funding,
            oi_snapshots=oi,
            prices=prices,
        )
        assert result.regime == MarketRegime.MEAN_REVERTING

    # -- Volatile regime -----------------------------------------------------

    def test_volatile_regime(self, enricher):
        """High liquidations + rapid OI changes = volatile."""
        # Normal liquidations then a massive spike
        liq_totals = [100000] * 8 + [5000000, 10000000]
        liqs = make_liq_snapshots(liq_totals)

        # Rapidly changing OI
        oi = [
            AggregatedOI(
                symbol="BTC",
                timestamp=time.time() - i * 3600,
                by_exchange={"Binance": 100000 * (1 + 0.15 * ((-1) ** i))},
            )
            for i in range(10, 0, -1)
        ]

        result = enricher.classify(
            "BTC",
            liquidation_snapshots=liqs,
            oi_snapshots=oi,
        )
        assert result.regime == MarketRegime.VOLATILE

    # -- Low-liquidity regime ------------------------------------------------

    def test_low_liquidity_regime(self, enricher):
        """Thin book + wide spread = low-liquidity."""
        book = make_thin_book()

        result = enricher.classify("BTC", book=book)
        assert result.regime == MarketRegime.LOW_LIQUIDITY

    # -- Graceful degradation ------------------------------------------------

    def test_partial_data_oi_only(self, enricher):
        oi = make_oi_expanding(10, growth=0.06)
        result = enricher.classify("BTC", oi_snapshots=oi)
        assert result.regime != MarketRegime.UNKNOWN

    def test_partial_data_funding_only(self, enricher):
        funding = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.001},
        )
        result = enricher.classify("BTC", funding_snapshot=funding)
        assert result.regime != MarketRegime.UNKNOWN

    def test_partial_data_book_only(self, enricher):
        book = make_normal_book()
        result = enricher.classify("BTC", book=book)
        # Normal book shouldn't strongly indicate any regime
        assert result.regime is not None

    def test_partial_data_prices_only(self, enricher):
        prices = [50000 + i * 300 for i in range(20)]
        result = enricher.classify("BTC", prices=prices)
        assert result.regime == MarketRegime.TRENDING

    # -- Asset context as funding source -------------------------------------

    def test_asset_context_funding(self, enricher):
        ctx = AssetContext(
            symbol="BTC",
            funding_rate=0.001,  # extreme
            mark_price=83000,
            mid_price=83000,
            oracle_price=83000,
            open_interest=50000,
            day_notional_volume=1e9,
            premium=0.001,
            prev_day_price=82000,
        )
        result = enricher.classify("BTC", asset_context=ctx)
        assert result.regime != MarketRegime.UNKNOWN

    # -- Alpha signals input -------------------------------------------------

    def test_alpha_signals_input(self, enricher):
        signals = [
            AlphaSignal(
                signal_name="liquidation_cascade",
                symbol="BTC",
                value=5000000,
                z_score=3.0,
                timestamp=time.time(),
                confidence=0.9,
            ),
            AlphaSignal(
                signal_name="orderbook_spread_z",
                symbol="BTC",
                value=20,
                z_score=2.5,
                timestamp=time.time(),
                confidence=0.8,
            ),
        ]
        result = enricher.classify("BTC", alpha_signals=signals)
        assert result.regime == MarketRegime.VOLATILE

    def test_alpha_signals_mean_reverting(self, enricher):
        signals = [
            AlphaSignal(
                signal_name="funding_mean_reversion",
                symbol="BTC",
                value=0.005,
                z_score=3.0,
                timestamp=time.time(),
                confidence=0.9,
            ),
            AlphaSignal(
                signal_name="basis_premium_extreme",
                symbol="BTC",
                value=0.5,
                z_score=2.5,
                timestamp=time.time(),
                confidence=0.8,
            ),
            AlphaSignal(
                signal_name="oi_expansion_rate",
                symbol="BTC",
                value=-0.05,
                z_score=-1.5,
                timestamp=time.time(),
                confidence=0.6,
            ),
        ]
        result = enricher.classify("BTC", alpha_signals=signals)
        assert result.regime == MarketRegime.MEAN_REVERTING

    # -- Metadata and scores -------------------------------------------------

    def test_result_contains_scores(self, enricher):
        prices = [50000 + i * 300 for i in range(20)]
        result = enricher.classify("BTC", prices=prices)
        assert MarketRegime.TRENDING.value in result.scores
        assert MarketRegime.MEAN_REVERTING.value in result.scores
        assert MarketRegime.VOLATILE.value in result.scores
        assert MarketRegime.LOW_LIQUIDITY.value in result.scores

    def test_result_contains_contributors(self, enricher):
        oi = make_oi_expanding(10, growth=0.06)
        result = enricher.classify("BTC", oi_snapshots=oi)
        assert len(result.contributing_signals) > 0

    def test_result_metadata(self, enricher):
        oi = make_oi_expanding(10, growth=0.06)
        result = enricher.classify("BTC", oi_snapshots=oi)
        assert "total_weight" in result.metadata

    # -- Custom config -------------------------------------------------------

    def test_custom_config(self):
        config = RegimeConfig(
            funding_extreme_threshold=0.001,
            spread_wide_bps=50.0,
        )
        enricher = RegimeEnricher(config=config)

        # With higher threshold, 0.0005 funding is no longer extreme
        funding = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0005},
        )
        result = enricher.classify("BTC", funding_snapshot=funding)
        # Should classify as trending (normal funding)
        assert result.scores[MarketRegime.TRENDING.value] >= result.scores[MarketRegime.MEAN_REVERTING.value]

    # -- Confidence properties -----------------------------------------------

    def test_high_confidence_with_strong_signals(self, enricher):
        # All signals point to trending
        oi = make_oi_expanding(10, growth=0.08)
        funding = FundingSnapshot(
            symbol="BTC", timestamp=time.time(),
            rates={"Binance": 0.0001},
        )
        prices = [50000 + i * 500 for i in range(10)]
        result = enricher.classify(
            "BTC",
            funding_snapshot=funding,
            oi_snapshots=oi,
            prices=prices,
        )
        assert result.confidence > 0.3

    def test_low_confidence_with_conflicting_signals(self, enricher):
        # OI expanding (trending) but extreme funding (mean-reverting)
        oi = make_oi_expanding(10, growth=0.06)
        funding = FundingSnapshot(
            symbol="BTC", timestamp=time.time(),
            rates={"Binance": 0.001},
        )
        result = enricher.classify(
            "BTC",
            funding_snapshot=funding,
            oi_snapshots=oi,
        )
        # Confidence should be lower due to conflicting signals
        assert result.confidence < 1.0

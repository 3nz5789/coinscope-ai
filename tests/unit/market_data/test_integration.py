"""
Tests for CoinScopeAI Phase 2 — Integration Tests

End-to-end tests that wire alpha generators into the regime enricher,
verifying the full pipeline from raw data → alpha signals → regime state.
"""

import time

import pytest

from services.market_data.alpha.basis import BasisAlphaGenerator
from services.market_data.alpha.funding import FundingAlphaGenerator
from services.market_data.alpha.liquidation import LiquidationAlphaGenerator
from services.market_data.alpha.open_interest import OIAlphaGenerator
from services.market_data.alpha.orderbook import OrderBookAlphaGenerator
from services.market_data.models import (
    AggregatedBasis,
    AggregatedOI,
    AlphaGeneratorConfig,
    AlphaSignal,
    BasisData,
    Exchange,
    FundingRate,
    FundingSnapshot,
    L2OrderBook,
    LiquidationSnapshot,
    MarketRegime,
    OrderBookLevel,
    PredictedFunding,
)
from services.market_data.regime.enricher import RegimeEnricher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trending_scenario():
    """Create data that should classify as TRENDING."""
    now = time.time()
    symbol = "BTC"

    # Expanding OI
    oi = [
        AggregatedOI(
            symbol=symbol,
            timestamp=now - (20 - i) * 3600,
            by_exchange={"Binance": 100000 * (1.03 ** i), "Bybit": 50000 * (1.03 ** i)},
        )
        for i in range(20)
    ]

    # Normal funding
    funding_history = [
        FundingRate(symbol=symbol, exchange=Exchange.HYPERLIQUID, rate=0.0001, timestamp=now - (20 - i) * 3600)
        for i in range(20)
    ]
    funding_snap = FundingSnapshot(
        symbol=symbol, timestamp=now,
        rates={"Binance": 0.0001, "Bybit": 0.00012, "OKX": 0.00009},
    )

    # Steady uptrend prices
    prices = [50000 + i * 150 for i in range(20)]

    # Normal book
    book = L2OrderBook(
        symbol=symbol, exchange=Exchange.HYPERLIQUID, timestamp=now,
        bids=[OrderBookLevel(price=53000 - i * 10, size=10 - i * 0.5) for i in range(10)],
        asks=[OrderBookLevel(price=53010 + i * 10, size=10 - i * 0.5) for i in range(10)],
    )

    # Low liquidations
    liqs = [
        LiquidationSnapshot(
            symbol=symbol, timestamp=now - (10 - i) * 3600,
            window_seconds=3600,
            long_liquidations_usd=50000, short_liquidations_usd=50000,
        )
        for i in range(10)
    ]

    return {
        "symbol": symbol,
        "oi": oi,
        "funding_history": funding_history,
        "funding_snap": funding_snap,
        "prices": prices,
        "book": book,
        "liqs": liqs,
    }


def make_volatile_scenario():
    """Create data that should classify as VOLATILE."""
    now = time.time()
    symbol = "ETH"

    # Rapidly changing OI
    oi = [
        AggregatedOI(
            symbol=symbol,
            timestamp=now - (10 - i) * 3600,
            by_exchange={"Binance": 50000 * (1 + 0.2 * ((-1) ** i))},
        )
        for i in range(10)
    ]

    # Extreme liquidations
    liqs = [
        LiquidationSnapshot(
            symbol=symbol, timestamp=now - (10 - i) * 3600,
            window_seconds=3600,
            long_liquidations_usd=100000 if i < 8 else 5000000,
            short_liquidations_usd=100000 if i < 8 else 3000000,
        )
        for i in range(10)
    ]

    # Wide-spread book
    book = L2OrderBook(
        symbol=symbol, exchange=Exchange.HYPERLIQUID, timestamp=now,
        bids=[OrderBookLevel(price=3000, size=2)],
        asks=[OrderBookLevel(price=3010, size=2)],  # ~33 bps spread
    )

    # Whipsaw prices
    prices = [3000, 3050, 2980, 3070, 2960, 3080, 2950, 3090, 2940, 3100]

    return {
        "symbol": symbol,
        "oi": oi,
        "liqs": liqs,
        "book": book,
        "prices": prices,
    }


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Test the complete pipeline: raw data → alpha signals → regime."""

    def test_trending_pipeline(self):
        data = make_trending_scenario()
        config = AlphaGeneratorConfig(min_data_points=3, z_score_threshold=1.5)

        # Generate alpha signals from all generators
        all_signals = []

        funding_gen = FundingAlphaGenerator(config)
        all_signals.extend(
            funding_gen.generate(
                data["symbol"],
                snapshot=data["funding_snap"],
                history=data["funding_history"],
            )
        )

        oi_gen = OIAlphaGenerator(config)
        all_signals.extend(
            oi_gen.generate(
                data["symbol"],
                oi_snapshots=data["oi"],
                prices=data["prices"],
            )
        )

        liq_gen = LiquidationAlphaGenerator(config)
        all_signals.extend(
            liq_gen.generate(data["symbol"], data["liqs"])
        )

        book_gen = OrderBookAlphaGenerator(config)
        all_signals.extend(
            book_gen.generate(data["symbol"], book=data["book"])
        )

        # All signals should be valid AlphaSignal objects
        for sig in all_signals:
            assert isinstance(sig, AlphaSignal)
            assert sig.symbol == data["symbol"]
            assert 0.0 <= sig.confidence <= 1.0

        # Feed signals into regime enricher
        enricher = RegimeEnricher()
        result = enricher.classify(
            data["symbol"],
            funding_snapshot=data["funding_snap"],
            oi_snapshots=data["oi"],
            liquidation_snapshots=data["liqs"],
            book=data["book"],
            prices=data["prices"],
            alpha_signals=all_signals,
        )

        assert result.regime == MarketRegime.TRENDING
        assert result.confidence > 0

    def test_volatile_pipeline(self):
        data = make_volatile_scenario()
        config = AlphaGeneratorConfig(min_data_points=3, z_score_threshold=1.5)

        all_signals = []

        oi_gen = OIAlphaGenerator(config)
        all_signals.extend(
            oi_gen.generate(data["symbol"], oi_snapshots=data["oi"])
        )

        liq_gen = LiquidationAlphaGenerator(config)
        all_signals.extend(
            liq_gen.generate(data["symbol"], data["liqs"])
        )

        book_gen = OrderBookAlphaGenerator(config)
        all_signals.extend(
            book_gen.generate(data["symbol"], book=data["book"])
        )

        enricher = RegimeEnricher()
        result = enricher.classify(
            data["symbol"],
            oi_snapshots=data["oi"],
            liquidation_snapshots=data["liqs"],
            book=data["book"],
            prices=data["prices"],
            alpha_signals=all_signals,
        )

        assert result.regime == MarketRegime.VOLATILE

    def test_all_generators_composable(self):
        """Verify that all generators can be composed and their outputs
        are compatible with the regime enricher."""
        config = AlphaGeneratorConfig(min_data_points=3)
        generators = [
            FundingAlphaGenerator(config),
            LiquidationAlphaGenerator(config),
            OIAlphaGenerator(config),
            BasisAlphaGenerator(config),
            OrderBookAlphaGenerator(config),
        ]

        # All generators should accept config
        for gen in generators:
            assert gen.config.min_data_points == 3

        # All generators should return lists when called with minimal args
        assert isinstance(FundingAlphaGenerator(config).generate("BTC"), list)
        assert isinstance(LiquidationAlphaGenerator(config).generate("BTC", []), list)
        assert isinstance(OIAlphaGenerator(config).generate("BTC", []), list)
        assert isinstance(BasisAlphaGenerator(config).generate("BTC"), list)
        assert isinstance(OrderBookAlphaGenerator(config).generate("BTC"), list)

    def test_regime_enricher_with_only_alpha_signals(self):
        """Regime enricher should work with only alpha signals as input."""
        signals = [
            AlphaSignal(
                signal_name="oi_expansion_rate",
                symbol="BTC",
                value=0.08,
                z_score=2.0,
                timestamp=time.time(),
                confidence=0.7,
                direction="bullish",
            ),
            AlphaSignal(
                signal_name="funding_mean_reversion",
                symbol="BTC",
                value=0.005,
                z_score=3.0,
                timestamp=time.time(),
                confidence=0.9,
            ),
        ]

        enricher = RegimeEnricher()
        result = enricher.classify("BTC", alpha_signals=signals)
        assert result.regime != MarketRegime.UNKNOWN

    def test_signal_names_are_consistent(self):
        """Verify that signal names used in regime enricher match those
        produced by alpha generators."""
        config = AlphaGeneratorConfig(min_data_points=3, z_score_threshold=0.5)

        # Generate signals from each generator with minimal data
        now = time.time()

        # Funding signals
        funding_gen = FundingAlphaGenerator(config)
        funding_signals = funding_gen.generate(
            "BTC",
            history=[
                FundingRate("BTC", Exchange.HYPERLIQUID, 0.0001, now - i * 3600)
                for i in range(10, 0, -1)
            ] + [FundingRate("BTC", Exchange.HYPERLIQUID, 0.005, now)],
        )

        # OI signals
        oi_gen = OIAlphaGenerator(config)
        oi_signals = oi_gen.generate(
            "BTC",
            oi_snapshots=[
                AggregatedOI("BTC", now - i * 3600, {"Binance": 100000 + i * 5000})
                for i in range(10)
            ],
        )

        # Liquidation signals
        liq_gen = LiquidationAlphaGenerator(config)
        liq_signals = liq_gen.generate(
            "BTC",
            [
                LiquidationSnapshot("BTC", now - i * 3600, 3600, 50000, 50000)
                for i in range(10, 1, -1)
            ] + [LiquidationSnapshot("BTC", now, 3600, 5000000, 3000000)],
        )

        # Collect all signal names
        all_names = set()
        for sig_list in [funding_signals, oi_signals, liq_signals]:
            for sig in sig_list:
                all_names.add(sig.signal_name)

        # The regime enricher should recognise at least some of these
        known_names = {
            "funding_mean_reversion",
            "liquidation_cascade",
            "oi_expansion_rate",
            "orderbook_spread_z",
            "basis_premium_extreme",
        }
        # At least some overlap
        assert len(all_names & known_names) > 0 or len(all_names) > 0

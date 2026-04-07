"""
Tests for CoinScopeAI Phase 2 — Alpha Feature Generators

Tests all five alpha generators: Funding, Liquidation, OI, Basis, OrderBook.
"""

import math
import time

import pytest

from services.market_data.alpha.base import BaseAlphaGenerator
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
    OrderBookLevel,
    PredictedFunding,
    SignalDirection,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_funding_history(rates, symbol="BTC"):
    """Create a list of FundingRate objects from a list of rate values."""
    now = time.time()
    return [
        FundingRate(
            symbol=symbol,
            exchange=Exchange.HYPERLIQUID,
            rate=r,
            timestamp=now - (len(rates) - i) * 3600,
        )
        for i, r in enumerate(rates)
    ]


def make_liq_snapshots(totals, long_pcts=None, symbol="BTC"):
    """Create LiquidationSnapshot objects from total USD values."""
    now = time.time()
    if long_pcts is None:
        long_pcts = [0.5] * len(totals)
    return [
        LiquidationSnapshot(
            symbol=symbol,
            timestamp=now - (len(totals) - i) * 3600,
            window_seconds=3600,
            long_liquidations_usd=t * lp,
            short_liquidations_usd=t * (1 - lp),
            total_count=int(t / 10000),
        )
        for i, (t, lp) in enumerate(zip(totals, long_pcts))
    ]


def make_oi_snapshots(totals, symbol="BTC"):
    """Create AggregatedOI objects from total OI values."""
    now = time.time()
    return [
        AggregatedOI(
            symbol=symbol,
            timestamp=now - (len(totals) - i) * 3600,
            by_exchange={"Binance": t * 0.5, "Bybit": t * 0.3, "OKX": t * 0.2},
        )
        for i, t in enumerate(totals)
    ]


def make_book(bids, asks, symbol="BTC"):
    """Create an L2OrderBook from price/size tuples."""
    return L2OrderBook(
        symbol=symbol,
        exchange=Exchange.HYPERLIQUID,
        timestamp=time.time(),
        bids=[OrderBookLevel(price=p, size=s) for p, s in bids],
        asks=[OrderBookLevel(price=p, size=s) for p, s in asks],
    )


def make_basis_snapshots(basis_pcts, symbol="BTC"):
    """Create AggregatedBasis objects from basis percentage values."""
    now = time.time()
    result = []
    for i, bp in enumerate(basis_pcts):
        spot = 50000.0
        futures = spot * (1 + bp / 100)
        bd = BasisData(
            symbol=symbol,
            exchange=Exchange.BINANCE,
            spot_price=spot,
            futures_price=futures,
            timestamp=now - (len(basis_pcts) - i) * 3600,
        )
        result.append(
            AggregatedBasis(
                symbol=symbol,
                timestamp=bd.timestamp,
                by_exchange={"Binance": bd},
            )
        )
    return result


# ---------------------------------------------------------------------------
# Tests: BaseAlphaGenerator utilities
# ---------------------------------------------------------------------------

class TestBaseAlphaGeneratorUtils:
    def test_mean(self):
        assert BaseAlphaGenerator.mean([1, 2, 3, 4, 5]) == 3.0
        assert BaseAlphaGenerator.mean([]) == 0.0

    def test_std(self):
        s = BaseAlphaGenerator.std([2, 4, 4, 4, 5, 5, 7, 9])
        assert abs(s - 2.0) < 0.2  # sample std with ddof=1

    def test_std_single_value(self):
        assert BaseAlphaGenerator.std([5.0]) == 0.0

    def test_z_score(self):
        values = [10, 12, 14, 16, 18]
        z = BaseAlphaGenerator.z_score(20, values)
        assert z > 0

    def test_z_score_zero_std(self):
        assert BaseAlphaGenerator.z_score(5, [5, 5, 5]) == 0.0

    def test_ema(self):
        result = BaseAlphaGenerator.ema([1, 2, 3, 4, 5], alpha=0.5)
        assert result > 3.0  # should be weighted toward recent values

    def test_rate_of_change(self):
        assert BaseAlphaGenerator.rate_of_change(110, 100) == 0.1
        assert BaseAlphaGenerator.rate_of_change(100, 0) == 0.0

    def test_direction_from_value(self):
        assert BaseAlphaGenerator.direction_from_value(1.0) == SignalDirection.BULLISH
        assert BaseAlphaGenerator.direction_from_value(-1.0) == SignalDirection.BEARISH
        assert BaseAlphaGenerator.direction_from_value(0.0) == SignalDirection.NEUTRAL

    def test_confidence_from_z(self):
        assert BaseAlphaGenerator.confidence_from_z(0) == 0.0
        assert BaseAlphaGenerator.confidence_from_z(4.0) == 1.0
        assert 0 < BaseAlphaGenerator.confidence_from_z(2.0) < 1.0


# ---------------------------------------------------------------------------
# Tests: FundingAlphaGenerator
# ---------------------------------------------------------------------------

class TestFundingAlphaGenerator:
    @pytest.fixture
    def gen(self):
        return FundingAlphaGenerator(
            AlphaGeneratorConfig(min_data_points=3, z_score_threshold=1.5)
        )

    def test_divergence_signals(self, gen):
        snapshot = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0001, "Bybit": 0.0005, "OKX": 0.0002},
        )
        signals = gen.generate("BTC", snapshot=snapshot)
        names = [s.signal_name for s in signals]
        assert "funding_cross_exchange_divergence" in names

        div_sig = next(s for s in signals if s.signal_name == "funding_cross_exchange_divergence")
        assert div_sig.metadata["max_exchange"] == "Bybit"
        assert div_sig.metadata["min_exchange"] == "Binance"

    def test_divergence_single_exchange(self, gen):
        snapshot = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0001},
        )
        signals = gen.generate("BTC", snapshot=snapshot)
        names = [s.signal_name for s in signals]
        assert "funding_cross_exchange_divergence" not in names

    def test_mean_reversion_extreme(self, gen):
        # Create history with extreme last value
        rates = [0.0001] * 20 + [0.005]  # spike at the end
        history = make_funding_history(rates)
        signals = gen.generate("BTC", history=history)
        names = [s.signal_name for s in signals]
        assert "funding_mean_reversion" in names
        assert "funding_z_score" in names

    def test_mean_reversion_normal(self, gen):
        rates = [0.0001] * 10
        history = make_funding_history(rates)
        signals = gen.generate("BTC", history=history)
        names = [s.signal_name for s in signals]
        assert "funding_mean_reversion" not in names  # not extreme enough
        assert "funding_z_score" in names

    def test_predicted_extreme(self, gen):
        predicted = [
            PredictedFunding("BTC", "BinPerp", 0.0001, 1700000000000),
            PredictedFunding("BTC", "HlPerp", 0.005, 1700000000000),
            PredictedFunding("BTC", "BybitPerp", 0.0002, 1700000000000),
        ]
        signals = gen.generate("BTC", predicted=predicted)
        names = [s.signal_name for s in signals]
        assert "funding_predicted_extreme" in names

    def test_empty_inputs(self, gen):
        signals = gen.generate("BTC")
        assert signals == []

    def test_insufficient_history(self, gen):
        history = make_funding_history([0.0001, 0.0002])  # less than min_data_points
        signals = gen.generate("BTC", history=history)
        assert signals == []


# ---------------------------------------------------------------------------
# Tests: LiquidationAlphaGenerator
# ---------------------------------------------------------------------------

class TestLiquidationAlphaGenerator:
    @pytest.fixture
    def gen(self):
        return LiquidationAlphaGenerator(
            AlphaGeneratorConfig(min_data_points=3, z_score_threshold=1.5)
        )

    def test_cascade_detection(self, gen):
        # Normal values then a spike
        totals = [100000] * 10 + [1000000]
        snapshots = make_liq_snapshots(totals)
        signals = gen.generate("BTC", snapshots)
        names = [s.signal_name for s in signals]
        assert "liquidation_cascade" in names

    def test_no_cascade(self, gen):
        totals = [100000] * 10
        snapshots = make_liq_snapshots(totals)
        signals = gen.generate("BTC", snapshots)
        names = [s.signal_name for s in signals]
        assert "liquidation_cascade" not in names

    def test_cluster_bearish(self, gen):
        totals = [100000] * 5
        long_pcts = [0.5] * 4 + [0.9]  # 90% longs liquidated in latest
        snapshots = make_liq_snapshots(totals, long_pcts)
        signals = gen.generate("BTC", snapshots)

        cluster = [s for s in signals if s.signal_name == "liquidation_cluster"]
        assert len(cluster) == 1
        assert cluster[0].direction == SignalDirection.BEARISH

    def test_cluster_bullish(self, gen):
        totals = [100000] * 5
        long_pcts = [0.5] * 4 + [0.1]  # 90% shorts liquidated in latest
        snapshots = make_liq_snapshots(totals, long_pcts)
        signals = gen.generate("BTC", snapshots)

        cluster = [s for s in signals if s.signal_name == "liquidation_cluster"]
        assert len(cluster) == 1
        assert cluster[0].direction == SignalDirection.BULLISH

    def test_ratio_signal(self, gen):
        snapshots = make_liq_snapshots([200000], [0.6])
        signals = gen.generate("BTC", snapshots)
        ratio_sigs = [s for s in signals if s.signal_name == "liquidation_long_short_ratio"]
        assert len(ratio_sigs) == 1
        assert ratio_sigs[0].value == 0.6 * 200000 / (0.4 * 200000)

    def test_empty_input(self, gen):
        assert gen.generate("BTC", []) == []


# ---------------------------------------------------------------------------
# Tests: OIAlphaGenerator
# ---------------------------------------------------------------------------

class TestOIAlphaGenerator:
    @pytest.fixture
    def gen(self):
        return OIAlphaGenerator(
            AlphaGeneratorConfig(min_data_points=3)
        )

    def test_expansion_signal(self, gen):
        totals = [100000, 105000, 110000, 115000, 130000]  # expanding
        snapshots = make_oi_snapshots(totals)
        signals = gen.generate("BTC", snapshots)
        names = [s.signal_name for s in signals]
        assert "oi_expansion_rate" in names

    def test_contraction_signal(self, gen):
        totals = [130000, 120000, 110000, 100000, 80000]  # contracting
        snapshots = make_oi_snapshots(totals)
        signals = gen.generate("BTC", snapshots)
        exp_sig = [s for s in signals if s.signal_name == "oi_expansion_rate"]
        assert len(exp_sig) == 1
        assert exp_sig[0].value < 0

    def test_divergence_signal(self, gen):
        totals = [100000, 100000]
        snapshots = make_oi_snapshots(totals)
        signals = gen.generate("BTC", snapshots)
        names = [s.signal_name for s in signals]
        assert "oi_cross_exchange_divergence" in names

    def test_price_divergence(self, gen):
        totals = [100000, 100000, 100000, 90000, 80000]  # OI declining
        prices = [50000, 51000, 52000, 53000, 54000]  # price rising
        snapshots = make_oi_snapshots(totals)
        signals = gen.generate("BTC", snapshots, prices=prices)
        div_sigs = [s for s in signals if s.signal_name == "oi_price_divergence"]
        assert len(div_sigs) == 1
        assert div_sigs[0].metadata["divergence_type"] == "price_up_oi_down"
        assert div_sigs[0].direction == SignalDirection.BEARISH

    def test_empty_input(self, gen):
        assert gen.generate("BTC", []) == []


# ---------------------------------------------------------------------------
# Tests: BasisAlphaGenerator
# ---------------------------------------------------------------------------

class TestBasisAlphaGenerator:
    @pytest.fixture
    def gen(self):
        return BasisAlphaGenerator(
            AlphaGeneratorConfig(min_data_points=3, z_score_threshold=1.5)
        )

    def test_premium_extreme(self, gen):
        # Normal basis then a spike
        basis_pcts = [0.05] * 10 + [0.5]
        snapshots = make_basis_snapshots(basis_pcts)
        signals = gen.generate("BTC", basis_snapshots=snapshots)
        names = [s.signal_name for s in signals]
        assert "basis_premium_extreme" in names
        assert "basis_z_score" in names

    def test_no_extreme(self, gen):
        basis_pcts = [0.05] * 10
        snapshots = make_basis_snapshots(basis_pcts)
        signals = gen.generate("BTC", basis_snapshots=snapshots)
        names = [s.signal_name for s in signals]
        assert "basis_premium_extreme" not in names
        assert "basis_z_score" in names

    def test_convergence(self, gen):
        basis_pcts = [0.1, 0.08, 0.06, 0.04, 0.02]  # narrowing
        snapshots = make_basis_snapshots(basis_pcts)
        signals = gen.generate("BTC", basis_snapshots=snapshots)
        names = [s.signal_name for s in signals]
        assert "basis_convergence" in names

    def test_history_signals(self, gen):
        history = [
            BasisData("BTC", Exchange.BINANCE, 50000, 50025, time.time() - i * 3600)
            for i in range(10, 0, -1)
        ]
        # Add an extreme one at the end
        history.append(BasisData("BTC", Exchange.BINANCE, 50000, 50500, time.time()))
        signals = gen.generate("BTC", basis_history=history)
        names = [s.signal_name for s in signals]
        assert "basis_history_z" in names

    def test_empty_input(self, gen):
        assert gen.generate("BTC") == []


# ---------------------------------------------------------------------------
# Tests: OrderBookAlphaGenerator
# ---------------------------------------------------------------------------

class TestOrderBookAlphaGenerator:
    @pytest.fixture
    def gen(self):
        return OrderBookAlphaGenerator(
            AlphaGeneratorConfig(min_data_points=3, extra={"cliff_threshold": 0.5})
        )

    def test_imbalance_bullish(self, gen):
        book = make_book(
            bids=[(100, 50), (99, 30), (98, 20)],
            asks=[(101, 5), (102, 3), (103, 2)],
        )
        signals = gen.generate("BTC", book=book)
        imb = [s for s in signals if s.signal_name == "orderbook_imbalance"]
        assert len(imb) == 1
        assert imb[0].value > 0  # more bids
        assert imb[0].direction == SignalDirection.BULLISH

    def test_imbalance_bearish(self, gen):
        book = make_book(
            bids=[(100, 5), (99, 3), (98, 2)],
            asks=[(101, 50), (102, 30), (103, 20)],
        )
        signals = gen.generate("BTC", book=book)
        imb = [s for s in signals if s.signal_name == "orderbook_imbalance"]
        assert len(imb) == 1
        assert imb[0].value < 0  # more asks
        assert imb[0].direction == SignalDirection.BEARISH

    def test_depth_weighted_mid(self, gen):
        book = make_book(
            bids=[(100, 10), (99, 5), (98, 3), (97, 2), (96, 1)],
            asks=[(101, 10), (102, 5), (103, 3), (104, 2), (105, 1)],
        )
        signals = gen.generate("BTC", book=book)
        dwm = [s for s in signals if s.signal_name == "orderbook_depth_weighted_mid"]
        assert len(dwm) == 1
        assert dwm[0].value > 0

    def test_liquidity_cliff(self, gen):
        # Big size at level 0, then cliff at level 1
        book = make_book(
            bids=[(100, 50), (99, 5), (98, 4)],  # 90% drop from level 0 to 1
            asks=[(101, 10), (102, 9), (103, 8)],
        )
        signals = gen.generate("BTC", book=book)
        cliffs = [s for s in signals if "liquidity_cliff" in s.signal_name]
        assert len(cliffs) >= 1
        bid_cliff = [s for s in cliffs if "bid" in s.signal_name]
        assert len(bid_cliff) == 1
        assert bid_cliff[0].direction == SignalDirection.BEARISH

    def test_temporal_spread(self, gen):
        books = []
        for i in range(10):
            spread = 1.0 + (i * 0.1)  # widening spread
            mid = 100.0
            books.append(make_book(
                bids=[(mid - spread / 2, 10)],
                asks=[(mid + spread / 2, 10)],
            ))
        signals = gen.generate("BTC", book_history=books)
        spread_sigs = [s for s in signals if s.signal_name == "orderbook_spread_z"]
        assert len(spread_sigs) == 1

    def test_empty_book(self, gen):
        book = L2OrderBook(
            symbol="BTC",
            exchange=Exchange.HYPERLIQUID,
            timestamp=time.time(),
        )
        signals = gen.generate("BTC", book=book)
        assert signals == []

    def test_empty_input(self, gen):
        assert gen.generate("BTC") == []

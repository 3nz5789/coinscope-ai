"""
Tests for CoinScopeAI Phase 2 — Data Models
"""

import time
import pytest

from services.market_data.models import (
    AggregatedBasis,
    AggregatedOI,
    AlphaGeneratorConfig,
    AlphaSignal,
    AssetContext,
    BasisData,
    Exchange,
    FundingRate,
    FundingSnapshot,
    L2OrderBook,
    Liquidation,
    LiquidationSnapshot,
    MarketRegime,
    OpenInterest,
    OrderBookLevel,
    PredictedFunding,
    RegimeState,
    Side,
    SignalDirection,
    Trade,
)


# ---------------------------------------------------------------------------
# OrderBookLevel
# ---------------------------------------------------------------------------

class TestOrderBookLevel:
    def test_creation(self):
        lvl = OrderBookLevel(price=100.0, size=5.0, num_orders=3)
        assert lvl.price == 100.0
        assert lvl.size == 5.0
        assert lvl.num_orders == 3

    def test_frozen(self):
        lvl = OrderBookLevel(price=100.0, size=5.0)
        with pytest.raises(AttributeError):
            lvl.price = 200.0  # type: ignore


# ---------------------------------------------------------------------------
# L2OrderBook
# ---------------------------------------------------------------------------

class TestL2OrderBook:
    def _make_book(self):
        return L2OrderBook(
            symbol="BTC",
            exchange=Exchange.HYPERLIQUID,
            timestamp=time.time(),
            bids=[
                OrderBookLevel(price=100.0, size=10.0),
                OrderBookLevel(price=99.0, size=5.0),
            ],
            asks=[
                OrderBookLevel(price=101.0, size=8.0),
                OrderBookLevel(price=102.0, size=3.0),
            ],
        )

    def test_best_bid_ask(self):
        book = self._make_book()
        assert book.best_bid == 100.0
        assert book.best_ask == 101.0

    def test_mid_price(self):
        book = self._make_book()
        assert book.mid_price == 100.5

    def test_spread(self):
        book = self._make_book()
        assert book.spread == 1.0

    def test_spread_bps(self):
        book = self._make_book()
        expected = (1.0 / 100.5) * 10_000
        assert abs(book.spread_bps - expected) < 0.01

    def test_empty_book(self):
        book = L2OrderBook(
            symbol="BTC",
            exchange=Exchange.HYPERLIQUID,
            timestamp=time.time(),
        )
        assert book.best_bid is None
        assert book.best_ask is None
        assert book.mid_price is None
        assert book.spread is None
        assert book.spread_bps is None


# ---------------------------------------------------------------------------
# FundingSnapshot
# ---------------------------------------------------------------------------

class TestFundingSnapshot:
    def test_mean_rate(self):
        snap = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0001, "Bybit": 0.0003, "OKX": 0.0002},
        )
        assert abs(snap.mean_rate - 0.0002) < 1e-10

    def test_max_divergence(self):
        snap = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0001, "Bybit": 0.0005},
        )
        assert abs(snap.max_divergence - 0.0004) < 1e-10

    def test_empty_rates(self):
        snap = FundingSnapshot(symbol="BTC", timestamp=time.time())
        assert snap.mean_rate == 0.0
        assert snap.max_divergence == 0.0

    def test_single_rate(self):
        snap = FundingSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            rates={"Binance": 0.0001},
        )
        assert snap.max_divergence == 0.0


# ---------------------------------------------------------------------------
# LiquidationSnapshot
# ---------------------------------------------------------------------------

class TestLiquidationSnapshot:
    def test_total_usd(self):
        snap = LiquidationSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            window_seconds=3600,
            long_liquidations_usd=1_000_000,
            short_liquidations_usd=500_000,
        )
        assert snap.total_usd == 1_500_000

    def test_long_short_ratio(self):
        snap = LiquidationSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            window_seconds=3600,
            long_liquidations_usd=1_000_000,
            short_liquidations_usd=500_000,
        )
        assert snap.long_short_ratio == 2.0

    def test_long_short_ratio_zero_short(self):
        snap = LiquidationSnapshot(
            symbol="BTC",
            timestamp=time.time(),
            window_seconds=3600,
            long_liquidations_usd=1_000_000,
            short_liquidations_usd=0,
        )
        assert snap.long_short_ratio is None


# ---------------------------------------------------------------------------
# BasisData
# ---------------------------------------------------------------------------

class TestBasisData:
    def test_basis(self):
        bd = BasisData(
            symbol="BTC",
            exchange=Exchange.BINANCE,
            spot_price=50000.0,
            futures_price=50100.0,
            timestamp=time.time(),
        )
        assert bd.basis == 100.0
        assert abs(bd.basis_pct - 0.2) < 0.001

    def test_annualized_basis(self):
        bd = BasisData(
            symbol="BTC",
            exchange=Exchange.BINANCE,
            spot_price=50000.0,
            futures_price=50100.0,
            timestamp=time.time(),
        )
        # 0.2% * 365.25 * 3 = ~219.15%
        assert bd.annualized_basis > 200


# ---------------------------------------------------------------------------
# AggregatedOI
# ---------------------------------------------------------------------------

class TestAggregatedOI:
    def test_total_oi(self):
        aoi = AggregatedOI(
            symbol="BTC",
            timestamp=time.time(),
            by_exchange={"Binance": 1000, "Bybit": 2000, "OKX": 500},
        )
        assert aoi.total_oi == 3500


# ---------------------------------------------------------------------------
# AlphaSignal
# ---------------------------------------------------------------------------

class TestAlphaSignal:
    def test_confidence_clamped(self):
        sig = AlphaSignal(
            signal_name="test",
            symbol="BTC",
            value=1.0,
            z_score=2.0,
            timestamp=time.time(),
            confidence=1.5,  # should be clamped to 1.0
        )
        assert sig.confidence == 1.0

        sig2 = AlphaSignal(
            signal_name="test",
            symbol="BTC",
            value=1.0,
            z_score=2.0,
            timestamp=time.time(),
            confidence=-0.5,  # should be clamped to 0.0
        )
        assert sig2.confidence == 0.0


# ---------------------------------------------------------------------------
# RegimeState
# ---------------------------------------------------------------------------

class TestRegimeState:
    def test_high_confidence(self):
        rs = RegimeState(
            symbol="BTC",
            regime=MarketRegime.TRENDING,
            confidence=0.8,
            timestamp=time.time(),
        )
        assert rs.is_high_confidence is True

    def test_low_confidence(self):
        rs = RegimeState(
            symbol="BTC",
            regime=MarketRegime.UNKNOWN,
            confidence=0.3,
            timestamp=time.time(),
        )
        assert rs.is_high_confidence is False


# ---------------------------------------------------------------------------
# AlphaGeneratorConfig
# ---------------------------------------------------------------------------

class TestAlphaGeneratorConfig:
    def test_defaults(self):
        cfg = AlphaGeneratorConfig()
        assert cfg.lookback_periods == 24
        assert cfg.z_score_threshold == 2.0
        assert cfg.min_data_points == 5
        assert cfg.decay_factor == 0.94

    def test_custom(self):
        cfg = AlphaGeneratorConfig(lookback_periods=48, z_score_threshold=3.0)
        assert cfg.lookback_periods == 48
        assert cfg.z_score_threshold == 3.0

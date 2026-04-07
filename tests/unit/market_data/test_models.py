"""
Tests for unified data models.
"""

import time
import pytest
from services.market_data.models import (
    Exchange, Side, ConnectionState,
    MarkPrice, OrderBook, OrderBookLevel, Trade,
    FundingRate, OpenInterest, Ticker,
    ConnectionMetrics, ScanSignal, EventType, MarketEvent,
)


class TestMarkPrice:
    def test_creation(self):
        mp = MarkPrice(
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
            mark_price=50000.0,
            index_price=49999.0,
            raw={"p": "50000.0"},
        )
        assert mp.exchange == Exchange.BINANCE
        assert mp.symbol == "BTCUSDT"
        assert mp.mark_price == 50000.0
        assert mp.index_price == 49999.0
        assert mp.raw == {"p": "50000.0"}
        assert mp.timestamp > 0

    def test_optional_fields(self):
        mp = MarkPrice(exchange=Exchange.OKX, symbol="ETHUSDT", mark_price=3000.0)
        assert mp.index_price is None
        assert mp.estimated_settle_price is None


class TestOrderBook:
    def test_best_bid_ask(self):
        ob = OrderBook(
            exchange=Exchange.BYBIT,
            symbol="BTCUSDT",
            bids=[OrderBookLevel(50000, 1.5), OrderBookLevel(49999, 2.0)],
            asks=[OrderBookLevel(50001, 0.5), OrderBookLevel(50002, 1.0)],
        )
        assert ob.best_bid.price == 50000
        assert ob.best_ask.price == 50001
        assert ob.mid_price == 50000.5
        assert ob.spread == 1.0

    def test_spread_bps(self):
        ob = OrderBook(
            exchange=Exchange.BINANCE,
            symbol="ETHUSDT",
            bids=[OrderBookLevel(3000, 10)],
            asks=[OrderBookLevel(3003, 10)],
        )
        # spread = 3, mid = 3001.5, bps = 3/3001.5 * 10000 ≈ 9.995
        assert ob.spread_bps is not None
        assert abs(ob.spread_bps - 9.995) < 0.1

    def test_empty_book(self):
        ob = OrderBook(exchange=Exchange.OKX, symbol="BTCUSDT")
        assert ob.best_bid is None
        assert ob.best_ask is None
        assert ob.mid_price is None
        assert ob.spread is None
        assert ob.spread_bps is None


class TestTrade:
    def test_creation(self):
        t = Trade(
            exchange=Exchange.HYPERLIQUID,
            symbol="BTCUSDT",
            trade_id="12345",
            price=50000.0,
            quantity=0.1,
            side=Side.BUY,
            raw={"px": "50000"},
        )
        assert t.side == Side.BUY
        assert t.quantity == 0.1


class TestFundingRate:
    def test_annualized(self):
        fr = FundingRate(
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
            funding_rate=0.0001,
        )
        # 0.0001 * 3 * 365 = 0.1095
        assert abs(fr.annualized_rate - 0.1095) < 0.001

    def test_negative_funding(self):
        fr = FundingRate(
            exchange=Exchange.BYBIT,
            symbol="ETHUSDT",
            funding_rate=-0.0005,
        )
        assert fr.annualized_rate < 0


class TestOpenInterest:
    def test_creation(self):
        oi = OpenInterest(
            exchange=Exchange.OKX,
            symbol="BTCUSDT",
            open_interest=15000.0,
            open_interest_value=750_000_000.0,
        )
        assert oi.open_interest == 15000.0
        assert oi.open_interest_value == 750_000_000.0


class TestTicker:
    def test_creation(self):
        t = Ticker(
            exchange=Exchange.OKX,
            symbol="BTCUSDT",
            last_price=50000.0,
            high_24h=51000.0,
            low_24h=49000.0,
            volume_24h=1000.0,
        )
        assert t.last_price == 50000.0


class TestConnectionMetrics:
    def test_uptime(self):
        m = ConnectionMetrics(exchange=Exchange.BINANCE)
        assert m.uptime_seconds is None
        m.connected_at = time.time() - 60
        assert m.uptime_seconds is not None
        assert m.uptime_seconds >= 59

    def test_mps(self):
        m = ConnectionMetrics(exchange=Exchange.BYBIT)
        m.connected_at = time.time() - 10
        m.messages_received = 100
        mps = m.messages_per_second
        assert mps is not None
        assert mps >= 9  # ~10


class TestScanSignal:
    def test_creation(self):
        sig = ScanSignal(
            scanner_name="breakout_oi",
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
            signal_type="breakout_oi_long",
            strength=0.75,
            details={"direction": "long"},
        )
        assert sig.strength == 0.75


class TestMarketEvent:
    def test_creation(self):
        mp = MarkPrice(exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000.0)
        event = MarketEvent(
            event_type=EventType.MARK_PRICE,
            data=mp,
            exchange=Exchange.BINANCE,
            symbol="BTCUSDT",
        )
        assert event.event_type == EventType.MARK_PRICE
        assert isinstance(event.data, MarkPrice)


class TestEnums:
    def test_exchange_values(self):
        assert Exchange.BINANCE.value == "binance"
        assert Exchange.BYBIT.value == "bybit"
        assert Exchange.OKX.value == "okx"
        assert Exchange.HYPERLIQUID.value == "hyperliquid"

    def test_side_values(self):
        assert Side.BUY.value == "buy"
        assert Side.SELL.value == "sell"

    def test_event_types(self):
        assert EventType.MARK_PRICE.value == "mark_price"
        assert EventType.SCAN_SIGNAL.value == "scan_signal"

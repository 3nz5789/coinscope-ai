"""
Tests for all scan engines.
"""

import time
import pytest
from services.market_data.base import EventBus
from services.market_data.models import (
    EventType, Exchange, MarkPrice, OpenInterest, FundingRate,
    OrderBook, OrderBookLevel, Trade, Side, MarketEvent, ScanSignal,
)
from services.market_data.scanner.base_scanner import ScannerConfig
from services.market_data.scanner.breakout_oi import BreakoutOIScanner
from services.market_data.scanner.funding_extreme import FundingExtremeScanner
from services.market_data.scanner.spread_divergence import SpreadDivergenceScanner
from services.market_data.scanner.liquidity_deterioration import LiquidityDeteriorationScanner


@pytest.fixture
def bus():
    return EventBus()


def _make_config(**overrides):
    defaults = dict(
        symbols=["BTCUSDT"],
        exchanges=[Exchange.BINANCE],
        window_seconds=300,
        scan_interval=1.0,
        thresholds={},
    )
    defaults.update(overrides)
    return ScannerConfig(**defaults)


def _make_event(event_type, data, exchange=Exchange.BINANCE, symbol="BTCUSDT", ts=None):
    return MarketEvent(
        event_type=event_type,
        data=data,
        exchange=exchange,
        symbol=symbol,
        timestamp=ts or time.time(),
    )


# =====================================================================
# Breakout + OI Scanner
# =====================================================================

class TestBreakoutOIScanner:
    @pytest.mark.asyncio
    async def test_no_signal_insufficient_data(self, bus):
        config = _make_config(thresholds={"min_data_points": 5})
        scanner = BreakoutOIScanner(config, bus)
        scanner.subscribe()

        # Only 2 data points — not enough
        for price in [50000, 50010]:
            event = _make_event(EventType.MARK_PRICE, MarkPrice(
                exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=price))
            await scanner._on_event(event)

        signals = await scanner.evaluate()
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_breakout_long_with_oi_expansion(self, bus):
        config = _make_config(thresholds={
            "price_breakout_pct": 0.5,
            "oi_expansion_pct": 2.0,
            "min_data_points": 3,
        })
        scanner = BreakoutOIScanner(config, bus)
        scanner.subscribe()

        # Feed mark prices: gradually rising then breakout
        base_ts = time.time()
        for i, price in enumerate([50000, 50100, 50200, 50300, 50600]):
            event = _make_event(EventType.MARK_PRICE, MarkPrice(
                exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=price),
                ts=base_ts + i)
            await scanner._on_event(event)

        # Feed OI: expanding
        for i, oi_val in enumerate([10000, 10300]):
            event = _make_event(EventType.OPEN_INTEREST, OpenInterest(
                exchange=Exchange.BINANCE, symbol="BTCUSDT", open_interest=oi_val),
                ts=base_ts + i)
            await scanner._on_event(event)

        signals = await scanner.evaluate()
        assert len(signals) >= 1
        assert signals[0].signal_type == "breakout_oi_long"
        assert signals[0].strength > 0

    @pytest.mark.asyncio
    async def test_no_signal_without_oi_expansion(self, bus):
        config = _make_config(thresholds={
            "price_breakout_pct": 0.5,
            "oi_expansion_pct": 2.0,
            "min_data_points": 3,
        })
        scanner = BreakoutOIScanner(config, bus)
        scanner.subscribe()

        base_ts = time.time()
        for i, price in enumerate([50000, 50100, 50200, 50300, 50600]):
            event = _make_event(EventType.MARK_PRICE, MarkPrice(
                exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=price),
                ts=base_ts + i)
            await scanner._on_event(event)

        # OI flat — no expansion
        for i, oi_val in enumerate([10000, 10000]):
            event = _make_event(EventType.OPEN_INTEREST, OpenInterest(
                exchange=Exchange.BINANCE, symbol="BTCUSDT", open_interest=oi_val),
                ts=base_ts + i)
            await scanner._on_event(event)

        signals = await scanner.evaluate()
        assert len(signals) == 0


# =====================================================================
# Funding Extreme Scanner
# =====================================================================

class TestFundingExtremeScanner:
    @pytest.mark.asyncio
    async def test_high_funding_signal(self, bus):
        config = _make_config(thresholds={"high_funding_pct": 0.05, "low_funding_pct": -0.05})
        scanner = FundingExtremeScanner(config, bus)
        scanner.subscribe()

        # Funding rate of 0.001 = 0.1% → above 0.05% threshold
        event = _make_event(EventType.FUNDING_RATE, FundingRate(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", funding_rate=0.001))
        await scanner._on_event(event)

        signals = await scanner.evaluate()
        assert len(signals) >= 1
        assert signals[0].signal_type == "funding_extreme_high"

    @pytest.mark.asyncio
    async def test_low_funding_signal(self, bus):
        config = _make_config(thresholds={"high_funding_pct": 0.05, "low_funding_pct": -0.05})
        scanner = FundingExtremeScanner(config, bus)
        scanner.subscribe()

        event = _make_event(EventType.FUNDING_RATE, FundingRate(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", funding_rate=-0.001))
        await scanner._on_event(event)

        signals = await scanner.evaluate()
        assert len(signals) >= 1
        assert signals[0].signal_type == "funding_extreme_low"

    @pytest.mark.asyncio
    async def test_normal_funding_no_signal(self, bus):
        config = _make_config(thresholds={"high_funding_pct": 0.05, "low_funding_pct": -0.05})
        scanner = FundingExtremeScanner(config, bus)
        scanner.subscribe()

        # 0.0001 = 0.01% → within normal range
        event = _make_event(EventType.FUNDING_RATE, FundingRate(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", funding_rate=0.0001))
        await scanner._on_event(event)

        signals = await scanner.evaluate()
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_cross_exchange_divergence(self, bus):
        config = _make_config(
            exchanges=[Exchange.BINANCE, Exchange.BYBIT],
            thresholds={"high_funding_pct": 1.0, "low_funding_pct": -1.0, "cross_exchange_spread_pct": 0.03, "min_exchanges": 2},
        )
        scanner = FundingExtremeScanner(config, bus)
        scanner.subscribe()

        # Binance: high funding
        event1 = _make_event(EventType.FUNDING_RATE, FundingRate(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", funding_rate=0.001),
            exchange=Exchange.BINANCE)
        await scanner._on_event(event1)

        # Bybit: low funding
        event2 = _make_event(EventType.FUNDING_RATE, FundingRate(
            exchange=Exchange.BYBIT, symbol="BTCUSDT", funding_rate=-0.001),
            exchange=Exchange.BYBIT)
        await scanner._on_event(event2)

        signals = await scanner.evaluate()
        divergence_signals = [s for s in signals if s.signal_type == "funding_cross_exchange_divergence"]
        assert len(divergence_signals) >= 1


# =====================================================================
# Spread Divergence Scanner
# =====================================================================

class TestSpreadDivergenceScanner:
    @pytest.mark.asyncio
    async def test_mark_mid_divergence(self, bus):
        config = _make_config(thresholds={"mark_mid_divergence_bps": 10.0, "cross_exchange_divergence_bps": 100.0})
        scanner = SpreadDivergenceScanner(config, bus)
        scanner.subscribe()

        # Mark price at 50000, mid at 49990 → ~2 bps divergence? No, 10/49995*10000 = 2 bps
        # Need bigger divergence: mark=50000, mid=49950 → 50/49975*10000 ≈ 10 bps
        event_mp = _make_event(EventType.MARK_PRICE, MarkPrice(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000))
        await scanner._on_event(event_mp)

        event_ob = _make_event(EventType.ORDER_BOOK, OrderBook(
            exchange=Exchange.BINANCE, symbol="BTCUSDT",
            bids=[OrderBookLevel(49940, 1)],
            asks=[OrderBookLevel(49960, 1)],
        ))
        await scanner._on_event(event_ob)

        signals = await scanner.evaluate()
        div_signals = [s for s in signals if s.signal_type == "mark_mid_divergence"]
        assert len(div_signals) >= 1

    @pytest.mark.asyncio
    async def test_cross_exchange_mark_divergence(self, bus):
        config = _make_config(
            exchanges=[Exchange.BINANCE, Exchange.OKX],
            thresholds={"mark_mid_divergence_bps": 100.0, "cross_exchange_divergence_bps": 10.0},
        )
        scanner = SpreadDivergenceScanner(config, bus)
        scanner.subscribe()

        event1 = _make_event(EventType.MARK_PRICE, MarkPrice(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000),
            exchange=Exchange.BINANCE)
        await scanner._on_event(event1)

        event2 = _make_event(EventType.MARK_PRICE, MarkPrice(
            exchange=Exchange.OKX, symbol="BTCUSDT", mark_price=50100),
            exchange=Exchange.OKX)
        await scanner._on_event(event2)

        signals = await scanner.evaluate()
        cross_signals = [s for s in signals if s.signal_type == "cross_exchange_mark_divergence"]
        assert len(cross_signals) >= 1

    @pytest.mark.asyncio
    async def test_no_divergence(self, bus):
        config = _make_config(thresholds={"mark_mid_divergence_bps": 10.0, "cross_exchange_divergence_bps": 100.0})
        scanner = SpreadDivergenceScanner(config, bus)
        scanner.subscribe()

        event_mp = _make_event(EventType.MARK_PRICE, MarkPrice(
            exchange=Exchange.BINANCE, symbol="BTCUSDT", mark_price=50000))
        await scanner._on_event(event_mp)

        event_ob = _make_event(EventType.ORDER_BOOK, OrderBook(
            exchange=Exchange.BINANCE, symbol="BTCUSDT",
            bids=[OrderBookLevel(49999.5, 1)],
            asks=[OrderBookLevel(50000.5, 1)],
        ))
        await scanner._on_event(event_ob)

        signals = await scanner.evaluate()
        assert len(signals) == 0


# =====================================================================
# Liquidity Deterioration Scanner
# =====================================================================

class TestLiquidityDeteriorationScanner:
    @pytest.mark.asyncio
    async def test_spread_widening(self, bus):
        config = _make_config(thresholds={
            "spread_multiplier": 3.0,
            "min_spread_samples": 5,
            "depth_thin_pct": 90.0,
            "trade_imbalance_ratio": 100.0,
            "min_trade_samples": 100,
        })
        scanner = LiquidityDeteriorationScanner(config, bus)
        scanner.subscribe()

        base_ts = time.time()
        # Normal spreads
        for i in range(10):
            event = _make_event(EventType.ORDER_BOOK, OrderBook(
                exchange=Exchange.BINANCE, symbol="BTCUSDT",
                bids=[OrderBookLevel(50000, 1)],
                asks=[OrderBookLevel(50001, 1)],  # spread = 1
            ), ts=base_ts + i)
            await scanner._on_event(event)

        # Sudden wide spread
        event = _make_event(EventType.ORDER_BOOK, OrderBook(
            exchange=Exchange.BINANCE, symbol="BTCUSDT",
            bids=[OrderBookLevel(49990, 0.1)],
            asks=[OrderBookLevel(50010, 0.1)],  # spread = 20
        ), ts=base_ts + 11)
        await scanner._on_event(event)

        signals = await scanner.evaluate()
        spread_signals = [s for s in signals if s.signal_type == "spread_widening"]
        assert len(spread_signals) >= 1

    @pytest.mark.asyncio
    async def test_depth_thinning(self, bus):
        config = _make_config(thresholds={
            "spread_multiplier": 100.0,
            "min_spread_samples": 100,
            "depth_thin_pct": 50.0,
            "trade_imbalance_ratio": 100.0,
            "min_trade_samples": 100,
        })
        scanner = LiquidityDeteriorationScanner(config, bus)
        scanner.subscribe()

        base_ts = time.time()
        # Initial: thick book
        event1 = _make_event(EventType.ORDER_BOOK, OrderBook(
            exchange=Exchange.BINANCE, symbol="BTCUSDT",
            bids=[OrderBookLevel(50000, 10.0)],
            asks=[OrderBookLevel(50001, 10.0)],
        ), ts=base_ts)
        await scanner._on_event(event1)

        # Later: thin book
        event2 = _make_event(EventType.ORDER_BOOK, OrderBook(
            exchange=Exchange.BINANCE, symbol="BTCUSDT",
            bids=[OrderBookLevel(50000, 2.0)],
            asks=[OrderBookLevel(50001, 2.0)],
        ), ts=base_ts + 10)
        await scanner._on_event(event2)

        signals = await scanner.evaluate()
        depth_signals = [s for s in signals if "depth_thinning" in s.signal_type]
        assert len(depth_signals) >= 1

    @pytest.mark.asyncio
    async def test_trade_imbalance_buy(self, bus):
        config = _make_config(thresholds={
            "spread_multiplier": 100.0,
            "min_spread_samples": 100,
            "depth_thin_pct": 99.0,
            "trade_imbalance_ratio": 3.0,
            "min_trade_samples": 5,
        })
        scanner = LiquidityDeteriorationScanner(config, bus)
        scanner.subscribe()

        base_ts = time.time()
        # Heavy buy-side aggression
        for i in range(10):
            event = _make_event(EventType.TRADE, Trade(
                exchange=Exchange.BINANCE, symbol="BTCUSDT",
                trade_id=str(i), price=50000, quantity=1.0, side=Side.BUY),
                ts=base_ts + i)
            await scanner._on_event(event)

        # A few sells
        for i in range(2):
            event = _make_event(EventType.TRADE, Trade(
                exchange=Exchange.BINANCE, symbol="BTCUSDT",
                trade_id=str(100 + i), price=50000, quantity=1.0, side=Side.SELL),
                ts=base_ts + 10 + i)
            await scanner._on_event(event)

        signals = await scanner.evaluate()
        imbalance_signals = [s for s in signals if s.signal_type == "trade_imbalance_buy"]
        assert len(imbalance_signals) >= 1

    @pytest.mark.asyncio
    async def test_no_signal_balanced_market(self, bus):
        config = _make_config(thresholds={
            "spread_multiplier": 3.0,
            "min_spread_samples": 5,
            "depth_thin_pct": 50.0,
            "trade_imbalance_ratio": 3.0,
            "min_trade_samples": 5,
        })
        scanner = LiquidityDeteriorationScanner(config, bus)
        scanner.subscribe()

        base_ts = time.time()
        # Consistent spreads
        for i in range(10):
            event = _make_event(EventType.ORDER_BOOK, OrderBook(
                exchange=Exchange.BINANCE, symbol="BTCUSDT",
                bids=[OrderBookLevel(50000, 5.0)],
                asks=[OrderBookLevel(50001, 5.0)],
            ), ts=base_ts + i)
            await scanner._on_event(event)

        # Balanced trades
        for i in range(5):
            await scanner._on_event(_make_event(EventType.TRADE, Trade(
                exchange=Exchange.BINANCE, symbol="BTCUSDT",
                trade_id=str(i), price=50000, quantity=1.0, side=Side.BUY),
                ts=base_ts + i))
            await scanner._on_event(_make_event(EventType.TRADE, Trade(
                exchange=Exchange.BINANCE, symbol="BTCUSDT",
                trade_id=str(100 + i), price=50000, quantity=1.0, side=Side.SELL),
                ts=base_ts + i))

        signals = await scanner.evaluate()
        assert len(signals) == 0

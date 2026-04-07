"""
Comprehensive test suite for CoinScopeAI market data streams.

Tests cover:
- Data models and EventBus
- LocalOrderBook state management
- Trade, OrderBook, Funding, Liquidation stream parsing (via mock injection)
- StreamRecorder write/flush/rotate
- ReplayEngine playback, time-windowing, pause/resume
- BybitPortalDownloader URL construction and ZIP conversion
- BybitPublicTradesDownloader URL construction and CSV conversion
- Date helper utilities
- RateLimiter token-bucket behaviour
- Record -> Replay round-trip
- Edge cases and error handling
"""
from __future__ import annotations

import asyncio
import gzip
import io
import json
import struct
import tempfile
import zipfile
import zlib
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import orjson
import pytest

from services.market_data.streams.base import (
    EventBus,
    EventType,
    Exchange,
    FundingRate,
    Liquidation,
    OrderBookLevel,
    OrderBookUpdate,
    RateLimiter,
    StreamStatus,
    Trade,
    get_event_bus,
    normalize_symbol,
    now_ms,
    to_binance_symbol,
    to_bybit_symbol,
    to_hyperliquid_coin,
    to_okx_symbol,
)
from services.market_data.streams.downloader import (
    BybitPortalDownloader,
    BybitPublicTradesDownloader,
    HistoricalDownloader,
    _date_range,
    _date_to_ms,
    _ms_to_date,
)
from services.market_data.streams.funding import FundingStream
from services.market_data.streams.liquidation import LiquidationStream
from services.market_data.streams.orderbook import LocalOrderBook, OrderBookStream
from services.market_data.streams.recorder import StreamRecorder
from services.market_data.streams.replay import ReplayEngine
from services.market_data.streams.trades import TradeStream


# ===========================================================================
# Helpers: capture on_msg closure and run one REST poll iteration
# ===========================================================================

async def _capture_ws_on_msg(stream, method_name: str, symbol: str):
    """
    Intercept _ws_connect_loop to capture the on_msg closure that the
    named stream method passes to it, then return that closure.
    """
    captured = {}

    async def mock_ws_connect_loop(url, on_message, *args, **kwargs):
        captured["on_msg"] = on_message

    stream._ws_connect_loop = mock_ws_connect_loop
    stream._running = True
    stream._session = MagicMock()

    method = getattr(stream, method_name)
    task = asyncio.create_task(method(symbol))
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    return captured.get("on_msg")


async def _run_rest_poll_once(stream, method_name: str, symbol: str, mock_response):
    """
    Run one iteration of a REST-polling stream method by mocking _rest_get
    and _rest_post, then stopping after the first asyncio.sleep call.
    """
    stream._running = True
    stream._session = MagicMock()

    async def mock_rest_get(url, exchange, params=None):
        return mock_response

    async def mock_rest_post(url, exchange, json_data=None):
        return mock_response

    stream._rest_get = mock_rest_get
    stream._rest_post = mock_rest_post

    async def mock_sleep(_delay):
        stream._running = False

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("asyncio.sleep", mock_sleep)
        method = getattr(stream, method_name)
        await method(symbol)


# ===========================================================================
# 1. Data Models
# ===========================================================================

class TestDataModels:

    def test_trade_creation(self):
        t = Trade(
            exchange="binance", symbol="BTCUSDT", trade_id="123",
            price=50000.0, quantity=1.5, side="buy",
            timestamp_ms=1_700_000_000_000, received_ms=1_700_000_000_001,
        )
        assert t.exchange == "binance"
        assert t.price == 50000.0
        assert t.side == "buy"

    def test_trade_to_dict(self):
        t = Trade(
            exchange="bybit", symbol="ETHUSDT", trade_id="456",
            price=3000.0, quantity=2.0, side="sell",
            timestamp_ms=1_700_000_000_000, received_ms=1_700_000_000_001,
        )
        d = t.to_dict()
        assert d["exchange"] == "bybit"
        assert d["price"] == 3000.0
        assert "timestamp_ms" in d

    def test_trade_to_json(self):
        t = Trade(
            exchange="okx", symbol="BTCUSDT", trade_id="xyz",
            price=45000.0, quantity=2.0, side="buy",
            timestamp_ms=2_000, received_ms=2_001,
        )
        raw = t.to_json()
        parsed = orjson.loads(raw)
        assert parsed["price"] == 45000.0

    def test_funding_rate_creation(self):
        fr = FundingRate(
            exchange="binance", symbol="BTCUSDT",
            funding_rate=0.0001, predicted_rate=0.00012,
            funding_time_ms=1_700_000_000_000,
            timestamp_ms=1_700_000_000_000, received_ms=1_700_000_000_001,
            mark_price=50000.0, index_price=49998.0,
        )
        assert fr.funding_rate == 0.0001
        assert fr.mark_price == 50000.0

    def test_liquidation_creation(self):
        liq = Liquidation(
            exchange="binance", symbol="BTCUSDT",
            side="sell", price=48000.0, quantity=1.0,
            usd_value=48000.0,
            timestamp_ms=1_700_000_000_000, received_ms=1_700_000_000_001,
        )
        assert liq.usd_value == 48000.0
        assert liq.is_derived is False

    def test_orderbook_update_creation(self):
        bids = [OrderBookLevel(price=50000.0, quantity=1.0)]
        asks = [OrderBookLevel(price=50001.0, quantity=0.5)]
        ob = OrderBookUpdate(
            exchange="binance", symbol="BTCUSDT",
            bids=bids, asks=asks,
            timestamp_ms=1_700_000_000_000, received_ms=1_700_000_000_001,
            is_snapshot=True, sequence=12345,
        )
        assert ob.is_snapshot is True
        assert ob.bids[0].price == 50000.0

    def test_orderbook_update_to_dict(self):
        bids = [OrderBookLevel(price=100.0, quantity=5.0)]
        asks = [OrderBookLevel(price=101.0, quantity=3.0)]
        ob = OrderBookUpdate(
            exchange="bybit", symbol="ETHUSDT",
            bids=bids, asks=asks,
            timestamp_ms=3_000, received_ms=3_001,
        )
        d = ob.to_dict()
        assert d["bids"] == [[100.0, 5.0]]
        assert d["asks"] == [[101.0, 3.0]]
        assert d["is_snapshot"] is False

    def test_stream_status_creation(self):
        ss = StreamStatus(
            exchange="okx", stream_type="trades",
            symbol="BTCUSDT", connected=True,
            message="connected", timestamp_ms=1_000,
        )
        assert ss.connected is True
        d = ss.to_dict()
        assert d["stream_type"] == "trades"


# ===========================================================================
# 2. Symbol Normalisation
# ===========================================================================

class TestSymbolNormalisation:

    def test_normalize_symbol_uppercase(self):
        assert normalize_symbol("btcusdt") == "BTCUSDT"

    def test_normalize_symbol_strips_separators(self):
        assert normalize_symbol("BTC-USDT") == "BTCUSDT"
        assert normalize_symbol("BTC_USDT") == "BTCUSDT"
        assert normalize_symbol("BTC/USDT") == "BTCUSDT"

    def test_to_binance_symbol_lowercase(self):
        assert to_binance_symbol("BTCUSDT") == "btcusdt"

    def test_to_bybit_symbol_uppercase(self):
        assert to_bybit_symbol("btcusdt") == "BTCUSDT"

    def test_to_okx_symbol_swap_format(self):
        result = to_okx_symbol("BTCUSDT")
        assert result == "BTC-USDT-SWAP"

    def test_to_okx_symbol_eth(self):
        result = to_okx_symbol("ETHUSDT")
        assert result == "ETH-USDT-SWAP"

    def test_to_hyperliquid_coin_strips_quote(self):
        assert to_hyperliquid_coin("BTCUSDT") == "BTC"
        assert to_hyperliquid_coin("ETHUSDT") == "ETH"


# ===========================================================================
# 3. EventBus
# ===========================================================================

class TestEventBus:

    async def test_subscribe_and_receive(self):
        bus = EventBus()
        received = []

        async def handler(event_type, data):
            received.append((event_type, data))

        await bus.subscribe(EventType.TRADE, handler)
        trade = Trade(
            exchange="binance", symbol="BTCUSDT", trade_id="1",
            price=50000.0, quantity=1.0, side="buy",
            timestamp_ms=1000, received_ms=1001,
        )
        await bus.publish(EventType.TRADE, trade)
        assert len(received) == 1
        assert received[0][0] == EventType.TRADE
        assert received[0][1].price == 50000.0

    async def test_subscribe_all_receives_all_event_types(self):
        bus = EventBus()
        received = []

        async def handler(event_type, data):
            received.append(event_type)

        await bus.subscribe_all(handler)

        trade = Trade(
            exchange="binance", symbol="BTCUSDT", trade_id="1",
            price=50000.0, quantity=1.0, side="buy",
            timestamp_ms=1000, received_ms=1001,
        )
        fr = FundingRate(
            exchange="binance", symbol="BTCUSDT",
            funding_rate=0.0001, predicted_rate=None,
            funding_time_ms=1000, timestamp_ms=1000, received_ms=1001,
        )
        await bus.publish(EventType.TRADE, trade)
        await bus.publish(EventType.FUNDING_RATE, fr)
        assert EventType.TRADE in received
        assert EventType.FUNDING_RATE in received

    async def test_multiple_subscribers(self):
        bus = EventBus()
        results_a, results_b = [], []

        async def handler_a(et, data):
            results_a.append(data)

        async def handler_b(et, data):
            results_b.append(data)

        await bus.subscribe(EventType.TRADE, handler_a)
        await bus.subscribe(EventType.TRADE, handler_b)

        trade = Trade(
            exchange="binance", symbol="BTCUSDT", trade_id="1",
            price=50000.0, quantity=1.0, side="buy",
            timestamp_ms=1000, received_ms=1001,
        )
        await bus.publish(EventType.TRADE, trade)
        assert len(results_a) == 1
        assert len(results_b) == 1

    async def test_no_cross_event_type_delivery(self):
        bus = EventBus()
        trade_received = []
        funding_received = []

        async def trade_handler(et, data):
            trade_received.append(data)

        async def funding_handler(et, data):
            funding_received.append(data)

        await bus.subscribe(EventType.TRADE, trade_handler)
        await bus.subscribe(EventType.FUNDING_RATE, funding_handler)

        fr = FundingRate(
            exchange="binance", symbol="BTCUSDT",
            funding_rate=0.0001, predicted_rate=None,
            funding_time_ms=1000, timestamp_ms=1000, received_ms=1001,
        )
        await bus.publish(EventType.FUNDING_RATE, fr)
        assert len(trade_received) == 0
        assert len(funding_received) == 1

    def test_get_event_bus_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2


# ===========================================================================
# 4. LocalOrderBook
# ===========================================================================

class TestLocalOrderBook:

    def test_initial_state(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        assert book.synced is False
        bids, asks = book.get_snapshot()
        assert bids == []
        assert asks == []

    def test_set_snapshot_syncs_book(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        bids = [(50000.0, 1.0), (49999.0, 2.0)]
        asks = [(50001.0, 1.5), (50002.0, 0.8)]
        book.set_snapshot(bids, asks, update_id=100)
        assert book.synced is True
        snap_bids, snap_asks = book.get_snapshot()
        assert len(snap_bids) == 2
        assert len(snap_asks) == 2
        assert snap_bids[0].price == 50000.0
        assert snap_asks[0].price == 50001.0

    def test_apply_delta_add_new_level(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        book.set_snapshot([(50000.0, 1.0)], [(50001.0, 1.0)], update_id=1)
        book.apply_delta([(49999.0, 3.0)], [], update_id=2)
        bids, _ = book.get_snapshot()
        prices = [b.price for b in bids]
        assert 50000.0 in prices
        assert 49999.0 in prices

    def test_apply_delta_remove_level(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        book.set_snapshot(
            [(50000.0, 1.0), (49999.0, 2.0)],
            [(50001.0, 1.5)],
            update_id=1,
        )
        book.apply_delta([(49999.0, 0.0)], [], update_id=2)
        bids, _ = book.get_snapshot()
        prices = [b.price for b in bids]
        assert 49999.0 not in prices
        assert 50000.0 in prices

    def test_apply_delta_update_quantity(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        book.set_snapshot([(50000.0, 1.0)], [(50001.0, 1.0)], update_id=1)
        book.apply_delta([(50000.0, 5.0)], [], update_id=2)
        bids, _ = book.get_snapshot()
        assert bids[0].quantity == 5.0

    def test_crossed_book_detection(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        book.set_snapshot([(50000.0, 1.0)], [(50001.0, 1.0)])
        assert book.is_crossed() is False
        book.set_snapshot([(50002.0, 1.0)], [(50001.0, 1.0)])
        assert book.is_crossed() is True

    def test_max_depth_trimming(self):
        # max_depth trimming is enforced by _trim() which fires on apply_delta.
        # set_snapshot stores all levels; after a delta _trim() caps the store.
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=5)
        bids = [(50000.0 - i, 1.0) for i in range(10)]
        asks = [(50001.0 + i, 1.0) for i in range(10)]
        book.set_snapshot(bids, asks)
        # Trigger _trim() via apply_delta
        book.apply_delta([(49990.0, 1.0)], [(50011.0, 1.0)], update_id=2)
        snap_bids, snap_asks = book.get_snapshot(depth=100)
        assert len(snap_bids) <= 5
        assert len(snap_asks) <= 5

    def test_snapshot_resets_state(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        book.set_snapshot([(50000.0, 1.0)], [(50001.0, 1.0)])
        book.apply_delta([(49998.0, 5.0)], [], update_id=2)
        book.set_snapshot([(60000.0, 2.0)], [(60001.0, 1.0)])
        bids, asks = book.get_snapshot()
        assert len(bids) == 1
        assert bids[0].price == 60000.0

    def test_get_snapshot_depth_limit(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        bids = [(50000.0 - i, 1.0) for i in range(20)]
        asks = [(50001.0 + i, 1.0) for i in range(20)]
        book.set_snapshot(bids, asks)
        snap_bids, snap_asks = book.get_snapshot(depth=5)
        assert len(snap_bids) == 5
        assert len(snap_asks) == 5

    def test_empty_snapshot_syncs(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=100)
        book.set_snapshot([], [], update_id=1)
        assert book.synced is True
        bids, asks = book.get_snapshot()
        assert bids == []
        assert asks == []


# ===========================================================================
# 5. Trade Stream Parsing
# ===========================================================================

class TestTradeStreamParsing:

    async def test_binance_aggtrade_buy_side(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_binance_trades", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "e": "aggTrade", "E": 1700000000001, "s": "BTCUSDT",
            "a": 999888, "p": "50000.00", "q": "0.500",
            "T": 1700000000000,
            "m": False,  # m=False → taker is buyer → side='buy'
        }
        await on_msg(msg)
        assert len(received) == 1
        t = received[0]
        assert t.exchange == Exchange.BINANCE.value
        assert t.price == 50000.0
        assert t.quantity == 0.5
        assert t.side == "buy"
        assert t.timestamp_ms == 1700000000000

    async def test_binance_aggtrade_sell_side(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_binance_trades", "BTCUSDT")
        msg = {
            "e": "aggTrade", "s": "BTCUSDT",
            "a": 1, "p": "50000.00", "q": "1.0",
            "T": 1700000000000,
            "m": True,  # m=True → taker is seller → side='sell'
        }
        await on_msg(msg)
        assert received[0].side == "sell"

    async def test_binance_aggtrade_wrong_event_ignored(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_binance_trades", "BTCUSDT")
        await on_msg({"e": "kline", "s": "BTCUSDT"})
        assert len(received) == 0

    async def test_bybit_trade_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.BYBIT], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_bybit_trades", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "topic": "publicTrade.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000001,
            "data": [
                {
                    "T": 1700000000000,
                    "s": "BTCUSDT",
                    "S": "Buy",
                    "v": "0.300",
                    "p": "51000.00",
                    "i": "trade-abc-123",
                }
            ],
        }
        await on_msg(msg)
        assert len(received) == 1
        t = received[0]
        assert t.exchange == Exchange.BYBIT.value
        assert t.price == 51000.0
        assert t.quantity == 0.3
        assert t.side == "buy"

    async def test_okx_trade_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.OKX], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_okx_trades", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "arg": {"channel": "trades", "instId": "BTC-USDT-SWAP"},
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "tradeId": "trade-999",
                    "px": "49500.00",
                    "sz": "0.800",
                    "side": "sell",
                    "ts": "1700000000000",
                }
            ],
        }
        await on_msg(msg)
        assert len(received) == 1
        t = received[0]
        assert t.exchange == Exchange.OKX.value
        assert t.price == 49500.0
        assert t.side == "sell"

    async def test_hyperliquid_trade_buy_side(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.HYPERLIQUID], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_hyperliquid_trades", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "channel": "trades",
            "data": [
                {
                    "coin": "BTC",
                    "side": "B",
                    "px": "52000.00",
                    "sz": "0.100",
                    "time": 1700000000000,
                    "tid": "hl-trade-1",
                }
            ],
        }
        await on_msg(msg)
        assert len(received) == 1
        t = received[0]
        assert t.exchange == Exchange.HYPERLIQUID.value
        assert t.price == 52000.0
        assert t.side == "buy"

    async def test_hyperliquid_trade_sell_side(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.HYPERLIQUID], event_bus=bus)

        on_msg = await _capture_ws_on_msg(stream, "_hyperliquid_trades", "BTCUSDT")
        msg = {
            "channel": "trades",
            "data": [
                {
                    "coin": "BTC",
                    "side": "A",
                    "px": "52000.00",
                    "sz": "0.100",
                    "time": 1700000000000,
                    "tid": "hl-trade-2",
                }
            ],
        }
        await on_msg(msg)
        assert received[0].side == "sell"

    async def test_none_message_ignored(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.TRADE, handler)
        stream = TradeStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_binance_trades", "BTCUSDT")

        await on_msg(None)
        await on_msg("not a dict")
        await on_msg({})
        assert len(received) == 0


# ===========================================================================
# 6. Order Book Stream Parsing
# ===========================================================================

class TestOrderBookStreamParsing:

    async def test_bybit_snapshot_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append((et, data))

        await bus.subscribe(EventType.ORDERBOOK_SNAPSHOT, handler)
        await bus.subscribe(EventType.ORDERBOOK_UPDATE, handler)

        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.BYBIT], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_bybit_orderbook", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "cts": 1700000000000,
            "data": {
                "s": "BTCUSDT",
                "b": [["50000.00", "1.000"], ["49999.00", "2.000"]],
                "a": [["50001.00", "1.500"], ["50002.00", "0.800"]],
                "u": 12345,
            },
        }
        await on_msg(msg)
        assert len(received) == 1
        et, ob = received[0]
        assert et == EventType.ORDERBOOK_SNAPSHOT
        assert ob.exchange == Exchange.BYBIT.value
        assert ob.is_snapshot is True
        assert ob.bids[0].price == 50000.0
        assert ob.asks[0].price == 50001.0

    async def test_bybit_delta_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append((et, data))

        await bus.subscribe(EventType.ORDERBOOK_SNAPSHOT, handler)
        await bus.subscribe(EventType.ORDERBOOK_UPDATE, handler)

        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.BYBIT], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_bybit_orderbook", "BTCUSDT")

        # First send a snapshot to sync the book
        await on_msg({
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "cts": 1700000000000,
            "data": {
                "s": "BTCUSDT",
                "b": [["50000.00", "1.000"]],
                "a": [["50001.00", "1.500"]],
                "u": 100,
            },
        })
        received.clear()

        # Now send a delta
        await on_msg({
            "topic": "orderbook.50.BTCUSDT",
            "type": "delta",
            "ts": 1700000000100,
            "cts": 1700000000100,
            "data": {
                "s": "BTCUSDT",
                "b": [["49999.00", "3.000"]],
                "a": [["50001.00", "2.000"]],
                "u": 101,
            },
        })
        assert len(received) == 1
        et, ob = received[0]
        assert et == EventType.ORDERBOOK_UPDATE
        assert ob.is_snapshot is False

    async def test_okx_books5_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append((et, data))

        await bus.subscribe(EventType.ORDERBOOK_SNAPSHOT, handler)

        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.OKX], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_okx_orderbook", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "arg": {"channel": "books5", "instId": "BTC-USDT-SWAP"},
            "data": [
                {
                    "bids": [["50000.00", "1.000", "0", "1"]],
                    "asks": [["50001.00", "1.500", "0", "2"]],
                    "ts": "1700000000000",
                }
            ],
        }
        await on_msg(msg)
        assert len(received) == 1
        et, ob = received[0]
        assert et == EventType.ORDERBOOK_SNAPSHOT
        assert ob.bids[0].price == 50000.0

    async def test_hyperliquid_l2book_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append((et, data))

        await bus.subscribe(EventType.ORDERBOOK_SNAPSHOT, handler)

        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.HYPERLIQUID], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_hyperliquid_orderbook", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "channel": "l2Book",
            "data": {
                "coin": "BTC",
                "levels": [
                    [{"px": "50000.00", "sz": "1.000", "n": 1}],
                    [{"px": "50001.00", "sz": "1.500", "n": 1}],
                ],
                "time": 1700000000000,
            },
        }
        await on_msg(msg)
        assert len(received) == 1
        et, ob = received[0]
        assert et == EventType.ORDERBOOK_SNAPSHOT
        assert ob.bids[0].price == 50000.0

    def test_orderbook_stream_get_book_none_before_first_msg(self):
        bus = EventBus()
        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)
        book = stream.get_book(Exchange.BINANCE, "BTCUSDT")
        assert book is None

    def test_orderbook_stream_get_book_after_internal_creation(self):
        bus = EventBus()
        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)
        stream._get_book(Exchange.BINANCE, "BTCUSDT")
        book = stream.get_book(Exchange.BINANCE, "BTCUSDT")
        assert book is not None
        assert book.exchange == Exchange.BINANCE.value


# ===========================================================================
# 7. Funding Rate Stream Parsing
# ===========================================================================

class TestFundingStreamParsing:

    async def test_binance_premium_index_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.FUNDING_RATE, handler)

        stream = FundingStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)
        response = {
            "symbol": "BTCUSDT",
            "markPrice": "50000.00",
            "indexPrice": "49998.00",
            "lastFundingRate": "0.00010000",
            "nextFundingTime": 1700000000000,
            "interestRate": "0.00010000",
            "time": 1700000000000,
        }
        await _run_rest_poll_once(stream, "_binance_funding", "BTCUSDT", response)
        assert len(received) == 1
        fr = received[0]
        assert fr.exchange == Exchange.BINANCE.value
        assert abs(fr.funding_rate - 0.0001) < 1e-10
        assert fr.mark_price == 50000.0

    async def test_bybit_funding_history_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.FUNDING_RATE, handler)

        stream = FundingStream(symbols=["BTCUSDT"], exchanges=[Exchange.BYBIT], event_bus=bus)
        response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "fundingRate": "0.00015000",
                        "fundingRateTimestamp": "1700000000000",
                    }
                ]
            },
        }
        await _run_rest_poll_once(stream, "_bybit_funding", "BTCUSDT", response)
        assert len(received) == 1
        fr = received[0]
        assert fr.exchange == Exchange.BYBIT.value
        assert abs(fr.funding_rate - 0.00015) < 1e-10

    async def test_okx_funding_rate_ws_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.FUNDING_RATE, handler)

        stream = FundingStream(symbols=["BTCUSDT"], exchanges=[Exchange.OKX], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_okx_funding", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "arg": {"channel": "funding-rate", "instId": "BTC-USDT-SWAP"},
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "instType": "SWAP",
                    "fundingRate": "0.00020000",
                    "nextFundingRate": "0.00018000",
                    "fundingTime": "1700000000000",
                    "ts": "1700000000000",
                }
            ],
        }
        await on_msg(msg)
        assert len(received) == 1
        fr = received[0]
        assert fr.exchange == Exchange.OKX.value
        assert abs(fr.funding_rate - 0.0002) < 1e-10

    async def test_hyperliquid_funding_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.FUNDING_RATE, handler)

        stream = FundingStream(symbols=["BTCUSDT"], exchanges=[Exchange.HYPERLIQUID], event_bus=bus)
        response = [
            {
                "universe": [
                    {"name": "BTC", "szDecimals": 5},
                    {"name": "ETH", "szDecimals": 4},
                ]
            },
            [
                {
                    "funding": "0.00012500",
                    "markPx": "50500.00",
                    "openInterest": "1234.56",
                },
                {
                    "funding": "0.00008000",
                    "markPx": "3200.00",
                    "openInterest": "5678.90",
                },
            ],
        ]
        await _run_rest_poll_once(stream, "_hyperliquid_funding", "BTCUSDT", response)
        assert len(received) == 1
        fr = received[0]
        assert fr.exchange == Exchange.HYPERLIQUID.value
        assert abs(fr.funding_rate - 0.000125) < 1e-10
        assert fr.mark_price == 50500.0


# ===========================================================================
# 8. Liquidation Stream Parsing
# ===========================================================================

class TestLiquidationStreamParsing:

    async def test_binance_force_order_short_liquidation(self):
        """Binance forceOrder S='BUY' means exchange buys to close short → side='sell'."""
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.LIQUIDATION, handler)

        stream = LiquidationStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_binance_liquidations", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "e": "forceOrder",
            "E": 1700000000001,
            "o": {
                "s": "BTCUSDT",
                "S": "BUY",
                "q": "0.014",
                "p": "48000.00",
                "T": 1700000000000,
            },
        }
        await on_msg(msg)
        assert len(received) == 1
        liq = received[0]
        assert liq.exchange == Exchange.BINANCE.value
        assert liq.price == 48000.0
        assert liq.side == "sell"  # BUY order → short was liquidated → side='sell'

    async def test_binance_force_order_long_liquidation(self):
        """Binance forceOrder S='SELL' means exchange sells to close long → side='buy'."""
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.LIQUIDATION, handler)

        stream = LiquidationStream(symbols=["BTCUSDT"], exchanges=[Exchange.BINANCE], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_binance_liquidations", "BTCUSDT")

        msg = {
            "e": "forceOrder",
            "o": {
                "s": "BTCUSDT",
                "S": "SELL",
                "q": "0.014",
                "p": "48000.00",
                "T": 1700000000000,
            },
        }
        await on_msg(msg)
        assert received[0].side == "buy"

    async def test_bybit_liquidation_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.LIQUIDATION, handler)

        stream = LiquidationStream(symbols=["BTCUSDT"], exchanges=[Exchange.BYBIT], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_bybit_liquidations", "BTCUSDT")
        assert on_msg is not None

        msg = {
            "topic": "liquidation.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000001,
            "data": {
                "symbol": "BTCUSDT",
                "side": "Sell",
                "price": "47000.00",
                "size": "0.500",
                "updatedTime": 1700000000000,
            },
        }
        await on_msg(msg)
        assert len(received) == 1
        liq = received[0]
        assert liq.exchange == Exchange.BYBIT.value
        assert liq.price == 47000.0
        assert liq.quantity == 0.5

    async def test_okx_liquidation_rest_parsing(self):
        bus = EventBus()
        received = []

        async def handler(et, data):
            received.append(data)

        await bus.subscribe(EventType.LIQUIDATION, handler)

        stream = LiquidationStream(symbols=["BTCUSDT"], exchanges=[Exchange.OKX], event_bus=bus)
        response = {
            "code": "0",
            "data": [
                {
                    "uly": "BTC-USDT",
                    "details": [
                        {
                            "side": "buy",
                            "posSide": "short",
                            "bkPx": "46000.00",
                            "sz": "2.000",
                            "bkLoss": "92000.00",
                            "ts": "1700000000000",
                        }
                    ],
                }
            ],
        }
        await _run_rest_poll_once(stream, "_okx_liquidations", "BTCUSDT", response)
        assert len(received) == 1
        liq = received[0]
        assert liq.exchange == Exchange.OKX.value
        assert liq.price == 46000.0
        assert liq.side == "buy"


# ===========================================================================
# 9. StreamRecorder
# ===========================================================================

class TestStreamRecorder:

    async def test_recorder_writes_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = EventBus()
            recorder = StreamRecorder(output_dir=tmp, event_bus=bus, flush_interval=60.0)
            await recorder.start()

            trade = Trade(
                exchange="binance", symbol="BTCUSDT", trade_id="1",
                price=50000.0, quantity=1.0, side="buy",
                timestamp_ms=1_700_000_000_000, received_ms=1_700_000_000_001,
            )
            await bus.publish(EventType.TRADE, trade)
            await recorder._flush_all()
            await recorder.stop()

            files = list(Path(tmp).rglob("*.jsonl.gz"))
            assert len(files) >= 1

            with gzip.open(str(files[0]), "rb") as f:
                lines = [ln for ln in f.read().split(b"\n") if ln.strip()]
            assert len(lines) >= 1
            record = orjson.loads(lines[0])
            assert record["event_type"] == EventType.TRADE.value
            assert record["data"]["price"] == 50000.0

    async def test_recorder_all_200_events_flushed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = EventBus()
            recorder = StreamRecorder(output_dir=tmp, event_bus=bus, flush_interval=3600.0)
            await recorder.start()

            for i in range(200):
                trade = Trade(
                    exchange="binance", symbol="BTCUSDT", trade_id=str(i),
                    price=50000.0 + i, quantity=1.0, side="buy",
                    timestamp_ms=1_000 + i, received_ms=1_001 + i,
                )
                await bus.publish(EventType.TRADE, trade)

            await recorder.stop()
            files = list(Path(tmp).rglob("*.jsonl.gz"))
            assert len(files) >= 1
            total = 0
            for f in files:
                with gzip.open(str(f), "rb") as gz:
                    total += sum(1 for ln in gz.read().split(b"\n") if ln.strip())
            assert total == 200

    async def test_recorder_multiple_event_types_separate_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = EventBus()
            recorder = StreamRecorder(output_dir=tmp, event_bus=bus, flush_interval=60.0)
            await recorder.start()

            trade = Trade(
                exchange="binance", symbol="BTCUSDT", trade_id="1",
                price=50000.0, quantity=1.0, side="buy",
                timestamp_ms=1_000, received_ms=1_001,
            )
            fr = FundingRate(
                exchange="binance", symbol="BTCUSDT",
                funding_rate=0.0001, predicted_rate=None,
                funding_time_ms=1_000, timestamp_ms=1_000, received_ms=1_001,
            )
            await bus.publish(EventType.TRADE, trade)
            await bus.publish(EventType.FUNDING_RATE, fr)
            await recorder._flush_all()
            await recorder.stop()

            files = list(Path(tmp).rglob("*.jsonl.gz"))
            assert len(files) >= 2

    async def test_recorder_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = EventBus()
            recorder = StreamRecorder(output_dir=tmp, event_bus=bus, flush_interval=60.0)
            await recorder.start()

            for i in range(5):
                trade = Trade(
                    exchange="binance", symbol="BTCUSDT", trade_id=str(i),
                    price=50000.0 + i, quantity=1.0, side="buy",
                    timestamp_ms=1_000 + i, received_ms=1_001 + i,
                )
                await bus.publish(EventType.TRADE, trade)

            await recorder._flush_all()
            stats = recorder.stats
            assert stats["event_count"] == 5
            assert stats["bytes_written"] > 0
            await recorder.stop()

    async def test_recorder_stop_flushes_buffer(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = EventBus()
            recorder = StreamRecorder(output_dir=tmp, event_bus=bus, flush_interval=3600.0)
            await recorder.start()

            trade = Trade(
                exchange="bybit", symbol="ETHUSDT", trade_id="99",
                price=3000.0, quantity=2.0, side="sell",
                timestamp_ms=2_000, received_ms=2_001,
            )
            await bus.publish(EventType.TRADE, trade)
            await recorder.stop()

            files = list(Path(tmp).rglob("*.jsonl.gz"))
            assert len(files) >= 1


# ===========================================================================
# 10. ReplayEngine
# ===========================================================================

def _write_test_recordings(tmp_dir: str, n_trades: int = 10, base_ts: int = 1_700_000_000_000):
    out_file = Path(tmp_dir) / "test_trades.jsonl.gz"
    with gzip.open(str(out_file), "wb") as f:
        for i in range(n_trades):
            trade = Trade(
                exchange="binance", symbol="BTCUSDT", trade_id=str(i),
                price=50000.0 + i, quantity=1.0, side="buy",
                timestamp_ms=base_ts + i * 1000,
                received_ms=base_ts + i * 1000 + 1,
            )
            record = {
                "event_type": EventType.TRADE.value,
                "timestamp_ms": base_ts + i * 1000,
                "data": trade.to_dict(),
            }
            f.write(orjson.dumps(record) + b"\n")
    return out_file


class TestReplayEngine:

    async def test_replay_all_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_test_recordings(tmp, n_trades=10)

            bus = EventBus()
            received = []

            async def handler(et, data):
                received.append(data)

            await bus.subscribe(EventType.TRADE, handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            await engine.wait()

            assert len(received) == 10
            assert received[0].price == 50000.0
            assert received[-1].price == 50009.0

    async def test_replay_time_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = 1_700_000_000_000
            _write_test_recordings(tmp, n_trades=10, base_ts=base_ts)

            bus = EventBus()
            received = []

            async def handler(et, data):
                received.append(data)

            await bus.subscribe(EventType.TRADE, handler)

            start_ms = base_ts + 3000
            end_ms = base_ts + 6000

            engine = ReplayEngine(
                data_dir=tmp, event_bus=bus, speed=0,
                start_time_ms=start_ms, end_time_ms=end_ms,
            )
            await engine.start()
            await engine.wait()

            assert len(received) == 4
            assert received[0].timestamp_ms == base_ts + 3000
            assert received[-1].timestamp_ms == base_ts + 6000

    async def test_replay_preserves_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = 1_700_000_000_000
            _write_test_recordings(tmp, n_trades=5, base_ts=base_ts)

            bus = EventBus()
            received = []

            async def handler(et, data):
                received.append(data)

            await bus.subscribe(EventType.TRADE, handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            await engine.wait()

            timestamps = [t.timestamp_ms for t in received]
            assert timestamps == sorted(timestamps)

    async def test_replay_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            bus = EventBus()
            received = []

            async def handler(et, data):
                received.append(data)

            await bus.subscribe(EventType.TRADE, handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            await engine.wait()

            assert len(received) == 0

    async def test_replay_mixed_event_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_ts = 1_700_000_000_000
            out_file = Path(tmp) / "mixed.jsonl.gz"
            with gzip.open(str(out_file), "wb") as f:
                trade = Trade(
                    exchange="binance", symbol="BTCUSDT", trade_id="1",
                    price=50000.0, quantity=1.0, side="buy",
                    timestamp_ms=base_ts, received_ms=base_ts + 1,
                )
                f.write(orjson.dumps({
                    "event_type": EventType.TRADE.value,
                    "timestamp_ms": base_ts,
                    "data": trade.to_dict(),
                }) + b"\n")
                fr = FundingRate(
                    exchange="binance", symbol="BTCUSDT",
                    funding_rate=0.0001, predicted_rate=None,
                    funding_time_ms=base_ts + 1000,
                    timestamp_ms=base_ts + 1000,
                    received_ms=base_ts + 1001,
                )
                f.write(orjson.dumps({
                    "event_type": EventType.FUNDING_RATE.value,
                    "timestamp_ms": base_ts + 1000,
                    "data": fr.to_dict(),
                }) + b"\n")

            bus = EventBus()
            trades_received = []
            funding_received = []

            async def trade_handler(et, data):
                trades_received.append(data)

            async def funding_handler(et, data):
                funding_received.append(data)

            await bus.subscribe(EventType.TRADE, trade_handler)
            await bus.subscribe(EventType.FUNDING_RATE, funding_handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            await engine.wait()

            assert len(trades_received) == 1
            assert len(funding_received) == 1

    async def test_replay_pause_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_test_recordings(tmp, n_trades=5)

            bus = EventBus()
            received = []

            async def handler(et, data):
                received.append(data)

            await bus.subscribe(EventType.TRADE, handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            engine.pause()
            assert engine._paused is True
            engine.resume()
            assert engine._paused is False
            await engine.wait()
            assert len(received) == 5

    async def test_replay_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_test_recordings(tmp, n_trades=7)

            bus = EventBus()
            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            await engine.wait()

            stats = engine.stats
            assert stats["events_replayed"] == 7
            assert stats["running"] is False


# ===========================================================================
# 11. Bybit Portal Downloader
# ===========================================================================

class TestBybitPortalDownloader:

    def test_cdn_url_linear(self):
        dl = BybitPortalDownloader(market_type="linear")
        url = dl._cdn_url("BTCUSDT", date(2025, 1, 15))
        expected = "https://quote-saver.bycsi.com/orderbook/linear/BTCUSDT/2025-01-15_BTCUSDT_ob500.data.zip"
        assert url == expected

    def test_cdn_url_inverse(self):
        dl = BybitPortalDownloader(market_type="inverse")
        url = dl._cdn_url("BTCUSD", date(2025, 3, 20))
        assert "inverse" in url
        assert "BTCUSD" in url
        assert "2025-03-20" in url
        assert url.endswith("_ob500.data.zip")

    def test_output_path(self):
        dl = BybitPortalDownloader(output_dir="/tmp/test_ob")
        path = dl._output_path("BTCUSDT", date(2025, 1, 15))
        assert str(path).endswith("BTCUSDT/2025-01-15_BTCUSDT_ob500.jsonl.gz")

    def test_convert_ob_message_snapshot(self):
        msg = {
            "topic": "orderbook.500.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "data": {
                "s": "BTCUSDT",
                "b": [["50000.00", "1.000"], ["49999.00", "2.000"]],
                "a": [["50001.00", "1.500"]],
                "u": 12345,
            },
        }
        record = BybitPortalDownloader._convert_ob_message(msg, "BTCUSDT")
        assert record is not None
        assert record["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value
        assert record["data"]["is_snapshot"] is True
        assert record["data"]["bids"][0][0] == 50000.0

    def test_convert_ob_message_delta(self):
        msg = {
            "topic": "orderbook.500.BTCUSDT",
            "type": "delta",
            "ts": 1700000000100,
            "data": {
                "s": "BTCUSDT",
                "b": [["50000.00", "0.000"]],
                "a": [["50001.00", "2.000"]],
                "u": 12346,
            },
        }
        record = BybitPortalDownloader._convert_ob_message(msg, "BTCUSDT")
        assert record is not None
        assert record["event_type"] == EventType.ORDERBOOK_UPDATE.value
        assert record["data"]["is_snapshot"] is False

    def test_convert_ob_message_invalid_type_returns_none(self):
        msg = {
            "topic": "orderbook.500.BTCUSDT",
            "type": "unknown_type",
            "ts": 1700000000000,
            "data": {"s": "BTCUSDT", "b": [], "a": [], "u": 1},
        }
        record = BybitPortalDownloader._convert_ob_message(msg, "BTCUSDT")
        assert record is None

    def test_convert_zip_to_jsonl_gz(self):
        ndjson_lines = []
        for i in range(5):
            msg = {
                "topic": "orderbook.500.BTCUSDT",
                "type": "snapshot" if i == 0 else "delta",
                "ts": 1700000000000 + i * 100,
                "data": {
                    "s": "BTCUSDT",
                    "b": [[str(50000.0 - i), "1.000"]],
                    "a": [[str(50001.0 + i), "1.500"]],
                    "u": 100 + i,
                },
            }
            ndjson_lines.append(json.dumps(msg).encode())

        ndjson_bytes = b"\n".join(ndjson_lines)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("2025-01-15_BTCUSDT_ob500.data", ndjson_bytes)
        zip_data = zip_buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.jsonl.gz"
            n = BybitPortalDownloader._convert_zip_to_jsonl_gz(
                zip_data, out_path, "BTCUSDT", date(2025, 1, 15)
            )
            assert n == 5
            assert out_path.exists()

            with gzip.open(str(out_path), "rb") as f:
                lines = [ln for ln in f.read().split(b"\n") if ln.strip()]
            assert len(lines) == 5
            first = orjson.loads(lines[0])
            assert first["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value

    def test_deflate_zip_stream_parsing(self):
        raw_data = b"Hello, Bybit orderbook data!"
        compressed = zlib.compress(raw_data)[2:-4]  # strip zlib header/trailer

        fname = b"test.data"
        header = (
            b"PK\x03\x04"
            + b"\x14\x00"
            + b"\x00\x00"
            + b"\x08\x00"
            + b"\x00\x00\x00\x00"
            + b"\x00\x00\x00\x00"
            + struct.pack("<I", len(compressed))
            + struct.pack("<I", len(raw_data))
            + struct.pack("<H", len(fname))
            + b"\x00\x00"
            + fname
            + compressed
        )
        result = BybitPortalDownloader._deflate_zip_stream(header)
        assert result == raw_data

    def test_deflate_zip_stream_invalid_data(self):
        result = BybitPortalDownloader._deflate_zip_stream(b"not a zip file")
        assert result is None


# ===========================================================================
# 12. Bybit Public Trades Downloader
# ===========================================================================

class TestBybitPublicTradesDownloader:

    def test_cdn_url_construction(self):
        dl = BybitPublicTradesDownloader()
        url = dl._cdn_url("BTCUSDT", date(2025, 1, 15))
        assert url.startswith("https://public.bybit.com/trading/")
        assert "BTCUSDT" in url
        assert "2025-01-15" in url
        assert url.endswith(".csv.gz")

    def test_convert_csv_to_jsonl_gz(self):
        csv_content = (
            "timestamp,symbol,side,size,price,tickDirection,trdMatchID,"
            "grossValue,homeNotional,foreignNotional\n"
            "1700000000.123,BTCUSDT,Buy,0.500,50000.00,PlusTick,match-001,"
            "25000000,0.5,25000\n"
            "1700000001.456,BTCUSDT,Sell,1.000,49999.00,MinusTick,match-002,"
            "49999000,1.0,49999\n"
        )
        csv_bytes = csv_content.encode("utf-8")

        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(csv_bytes)
        csv_gz_data = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.jsonl.gz"
            n = BybitPublicTradesDownloader._convert_csv_to_jsonl_gz(
                csv_gz_data, out_path, "BTCUSDT"
            )
            assert n == 2
            assert out_path.exists()

            with gzip.open(str(out_path), "rb") as f:
                lines = [ln for ln in f.read().split(b"\n") if ln.strip()]
            assert len(lines) == 2

            first = orjson.loads(lines[0])
            assert first["event_type"] == EventType.TRADE.value
            assert first["data"]["price"] == 50000.0
            assert first["data"]["side"] == "buy"

    def test_convert_csv_malformed_rows_skipped(self):
        csv_content = (
            "timestamp,symbol,side,size,price,tickDirection,trdMatchID,"
            "grossValue,homeNotional,foreignNotional\n"
            "not_a_number,BTCUSDT,Buy,0.5,50000.00,PlusTick,match-001,"
            "25000000,0.5,25000\n"
            "1700000001.456,BTCUSDT,Sell,1.000,49999.00,MinusTick,match-002,"
            "49999000,1.0,49999\n"
        )
        csv_bytes = csv_content.encode("utf-8")
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(csv_bytes)
        csv_gz_data = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.jsonl.gz"
            n = BybitPublicTradesDownloader._convert_csv_to_jsonl_gz(
                csv_gz_data, out_path, "BTCUSDT"
            )
            assert n == 1


# ===========================================================================
# 13. Date Helper Utilities
# ===========================================================================

class TestDateHelpers:

    def test_date_range_single_day(self):
        result = _date_range(date(2025, 1, 15), date(2025, 1, 15))
        assert result == [date(2025, 1, 15)]

    def test_date_range_multiple_days(self):
        result = _date_range(date(2025, 1, 13), date(2025, 1, 15))
        assert result == [date(2025, 1, 13), date(2025, 1, 14), date(2025, 1, 15)]

    def test_date_range_empty_when_start_after_end(self):
        result = _date_range(date(2025, 1, 15), date(2025, 1, 14))
        assert result == []

    def test_date_to_ms_epoch(self):
        ms = _date_to_ms(date(1970, 1, 1))
        assert ms == 0

    def test_date_to_ms_known_date(self):
        ms = _date_to_ms(date(2025, 1, 15))
        assert ms == 1736899200000

    def test_ms_to_date(self):
        d = _ms_to_date(1736899200000)
        assert d == date(2025, 1, 15)

    def test_date_range_one_week(self):
        start = date(2025, 1, 1)
        end = date(2025, 1, 7)
        result = _date_range(start, end)
        assert len(result) == 7
        assert result[0] == start
        assert result[-1] == end


# ===========================================================================
# 14. RateLimiter
# ===========================================================================

class TestRateLimiter:

    async def test_rate_limiter_allows_burst(self):
        limiter = RateLimiter(calls_per_second=100.0)
        start = asyncio.get_event_loop().time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.5

    async def test_rate_limiter_throttles_at_limit(self):
        limiter = RateLimiter(calls_per_second=10.0)
        # Exhaust the bucket
        for _ in range(10):
            await limiter.acquire()
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.05

    def test_rate_limiter_constructor(self):
        limiter = RateLimiter(calls_per_second=5.0)
        assert limiter._rate == 5.0


# ===========================================================================
# 15. Record -> Replay Round-Trip
# ===========================================================================

class TestRecordReplayRoundTrip:

    async def test_full_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            record_bus = EventBus()
            recorder = StreamRecorder(
                output_dir=tmp, event_bus=record_bus, flush_interval=3600.0,
            )
            await recorder.start()

            original_trades = []
            for i in range(5):
                trade = Trade(
                    exchange="binance", symbol="BTCUSDT", trade_id=str(i),
                    price=50000.0 + i * 100, quantity=float(i + 1),
                    side="buy" if i % 2 == 0 else "sell",
                    timestamp_ms=1_700_000_000_000 + i * 1000,
                    received_ms=1_700_000_000_001 + i * 1000,
                )
                original_trades.append(trade)
                await record_bus.publish(EventType.TRADE, trade)

            await recorder.stop()

            replay_bus = EventBus()
            replayed = []

            async def handler(et, data):
                replayed.append(data)

            await replay_bus.subscribe(EventType.TRADE, handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=replay_bus, speed=0)
            await engine.start()
            await engine.wait()

            assert len(replayed) == 5
            for orig, rep in zip(original_trades, replayed):
                assert rep.price == orig.price
                assert rep.quantity == orig.quantity
                assert rep.side == orig.side
                assert rep.timestamp_ms == orig.timestamp_ms


# ===========================================================================
# 16. Edge Cases
# ===========================================================================

class TestEdgeCases:

    async def test_eventbus_handles_subscriber_exception(self):
        bus = EventBus()
        results = []

        async def bad_handler(et, data):
            raise RuntimeError("intentional error")

        async def good_handler(et, data):
            results.append(data)

        await bus.subscribe(EventType.TRADE, bad_handler)
        await bus.subscribe(EventType.TRADE, good_handler)

        trade = Trade(
            exchange="binance", symbol="BTCUSDT", trade_id="1",
            price=50000.0, quantity=1.0, side="buy",
            timestamp_ms=1000, received_ms=1001,
        )
        await bus.publish(EventType.TRADE, trade)
        assert len(results) == 1

    def test_local_orderbook_large_update(self):
        book = LocalOrderBook("binance", "BTCUSDT", max_depth=500)
        bids = [(50000.0 - i * 0.1, float(i + 1)) for i in range(500)]
        asks = [(50001.0 + i * 0.1, float(i + 1)) for i in range(500)]
        book.set_snapshot(bids, asks)
        assert book.synced is True
        snap_bids, snap_asks = book.get_snapshot(depth=500)
        assert len(snap_bids) == 500
        assert len(snap_asks) == 500
        assert snap_bids[0].price == max(p for p, _ in bids)

    def test_bybit_portal_convert_empty_zip(self):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("empty.data", b"")
        zip_data = zip_buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.jsonl.gz"
            n = BybitPortalDownloader._convert_zip_to_jsonl_gz(
                zip_data, out_path, "BTCUSDT", date(2025, 1, 15)
            )
            assert n == 0

    def test_bybit_portal_convert_invalid_json_lines(self):
        ndjson_bytes = b"not valid json\n{\"also\": \"not a valid ob message\"}\n"
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data.data", ndjson_bytes)
        zip_data = zip_buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.jsonl.gz"
            n = BybitPortalDownloader._convert_zip_to_jsonl_gz(
                zip_data, out_path, "BTCUSDT", date(2025, 1, 15)
            )
            assert n == 0

    async def test_replay_with_corrupted_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_file = Path(tmp) / "corrupted.jsonl.gz"
            base_ts = 1_700_000_000_000
            with gzip.open(str(out_file), "wb") as f:
                trade = Trade(
                    exchange="binance", symbol="BTCUSDT", trade_id="1",
                    price=50000.0, quantity=1.0, side="buy",
                    timestamp_ms=base_ts, received_ms=base_ts + 1,
                )
                f.write(orjson.dumps({
                    "event_type": EventType.TRADE.value,
                    "timestamp_ms": base_ts,
                    "data": trade.to_dict(),
                }) + b"\n")
                f.write(b"this is not valid json at all\n")
                trade2 = Trade(
                    exchange="binance", symbol="BTCUSDT", trade_id="2",
                    price=50001.0, quantity=1.0, side="sell",
                    timestamp_ms=base_ts + 1000, received_ms=base_ts + 1001,
                )
                f.write(orjson.dumps({
                    "event_type": EventType.TRADE.value,
                    "timestamp_ms": base_ts + 1000,
                    "data": trade2.to_dict(),
                }) + b"\n")

            bus = EventBus()
            received = []

            async def handler(et, data):
                received.append(data)

            await bus.subscribe(EventType.TRADE, handler)

            engine = ReplayEngine(data_dir=tmp, event_bus=bus, speed=0)
            await engine.start()
            await engine.wait()

            assert len(received) == 2
            assert received[0].price == 50000.0
            assert received[1].price == 50001.0

    def test_trade_stream_normalizes_symbol(self):
        bus = EventBus()
        stream = TradeStream(symbols=["BTC-USDT"], event_bus=bus)
        assert "BTCUSDT" in stream.symbols

    def test_historical_downloader_init(self):
        dl = HistoricalDownloader(output_dir="/tmp/test_hist")
        assert dl.bybit_portal is not None
        assert dl.bybit_trades is not None
        assert dl.bybit_funding is not None
        assert dl.binance is not None

    async def test_orderbook_stream_crossed_book_desyncs(self):
        bus = EventBus()
        stream = OrderBookStream(symbols=["BTCUSDT"], exchanges=[Exchange.BYBIT], event_bus=bus)
        on_msg = await _capture_ws_on_msg(stream, "_bybit_orderbook", "BTCUSDT")

        await on_msg({
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1700000000000,
            "cts": 1700000000000,
            "data": {
                "s": "BTCUSDT",
                "b": [["50000.00", "1.000"]],
                "a": [["50001.00", "1.500"]],
                "u": 100,
            },
        })

        book = stream.get_book(Exchange.BYBIT, "BTCUSDT")
        assert book is not None
        assert book.synced is True

        # Delta that creates a crossed book (bid > ask) → should desync
        await on_msg({
            "topic": "orderbook.50.BTCUSDT",
            "type": "delta",
            "ts": 1700000000100,
            "cts": 1700000000100,
            "data": {
                "s": "BTCUSDT",
                "b": [["50002.00", "5.000"]],  # bid > ask → crossed
                "a": [],
                "u": 101,
            },
        })

        assert book.synced is False

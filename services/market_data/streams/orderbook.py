"""
Unified L2 Order Book Stream — maintains local order book state per exchange.

Each exchange connection:
1. Subscribes to WebSocket depth/book updates
2. Fetches an initial REST snapshot (where needed)
3. Applies incremental deltas to maintain a consistent local book
4. Detects desync and re-snapshots automatically
5. Publishes OrderBookUpdate events to the EventBus

Exchanges:
- Binance: depth@100ms + REST snapshot
- Bybit: orderbook.50 (snapshot + delta)
- OKX: books5 channel (periodic snapshots)
- Hyperliquid: l2Book subscription
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sortedcontainers import SortedDict

from .base import (
    BaseStream,
    EventBus,
    EventType,
    Exchange,
    OrderBookLevel,
    OrderBookUpdate,
    normalize_symbol,
    now_ms,
    to_binance_symbol,
    to_bybit_symbol,
    to_hyperliquid_coin,
    to_okx_symbol,
)

logger = logging.getLogger("coinscopeai.streams.orderbook")


class LocalOrderBook:
    """Thread-safe local order book with sorted price levels."""

    def __init__(self, exchange: str, symbol: str, max_depth: int = 50):
        self.exchange = exchange
        self.symbol = symbol
        self.max_depth = max_depth
        # bids: price → qty (descending), asks: price → qty (ascending)
        self._bids: SortedDict = SortedDict()  # negative key for descending
        self._asks: SortedDict = SortedDict()
        self._last_update_id: Optional[int] = None
        self._synced = False

    @property
    def synced(self) -> bool:
        return self._synced

    def set_snapshot(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], update_id: Optional[int] = None) -> None:
        self._bids.clear()
        self._asks.clear()
        for price, qty in bids:
            if qty > 0:
                self._bids[-price] = qty  # negative for descending sort
        for price, qty in asks:
            if qty > 0:
                self._asks[price] = qty
        self._last_update_id = update_id
        self._synced = True

    def apply_delta(self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]], update_id: Optional[int] = None) -> None:
        for price, qty in bids:
            key = -price
            if qty == 0:
                self._bids.pop(key, None)
            else:
                self._bids[key] = qty
        for price, qty in asks:
            if qty == 0:
                self._asks.pop(price, None)
            else:
                self._asks[price] = qty
        if update_id is not None:
            self._last_update_id = update_id
        self._trim()

    def _trim(self) -> None:
        while len(self._bids) > self.max_depth:
            self._bids.popitem()  # remove worst bid
        while len(self._asks) > self.max_depth:
            self._asks.popitem()  # remove worst ask

    def get_snapshot(self, depth: int = 20) -> Tuple[List[OrderBookLevel], List[OrderBookLevel]]:
        bids = [OrderBookLevel(price=-k, quantity=v) for k, v in self._bids.items()[:depth]]
        asks = [OrderBookLevel(price=k, quantity=v) for k, v in self._asks.items()[:depth]]
        return bids, asks

    def is_crossed(self) -> bool:
        """Detect crossed book (best bid >= best ask) → desync."""
        if not self._bids or not self._asks:
            return False
        best_bid = -self._bids.keys()[0]
        best_ask = self._asks.keys()[0]
        return best_bid >= best_ask


class OrderBookStream(BaseStream):
    """
    Unified L2 order book stream across 4 exchanges.

    Maintains local order book state and publishes updates/snapshots to EventBus.
    """

    def __init__(self, symbols: List[str], exchanges: Optional[List[Exchange]] = None,
                 event_bus: Optional[EventBus] = None, depth: int = 50):
        super().__init__(symbols, exchanges, event_bus)
        self.depth = depth
        self._books: Dict[str, LocalOrderBook] = {}
        self._snapshot_publish_interval = 1.0  # seconds between full snapshot publishes

    def _book_key(self, exchange: Exchange, symbol: str) -> str:
        return f"{exchange.value}:{normalize_symbol(symbol)}"

    def _get_book(self, exchange: Exchange, symbol: str) -> LocalOrderBook:
        key = self._book_key(exchange, symbol)
        if key not in self._books:
            self._books[key] = LocalOrderBook(exchange.value, normalize_symbol(symbol), self.depth)
        return self._books[key]

    def get_book(self, exchange: Exchange, symbol: str) -> Optional[LocalOrderBook]:
        """Public accessor for the local order book."""
        key = self._book_key(exchange, symbol)
        return self._books.get(key)

    def _create_tasks(self) -> List[asyncio.Task]:
        tasks: List[asyncio.Task] = []
        for symbol in self.symbols:
            for exchange in self.exchanges:
                if exchange == Exchange.BINANCE:
                    tasks.append(asyncio.create_task(self._binance_orderbook(symbol)))
                elif exchange == Exchange.BYBIT:
                    tasks.append(asyncio.create_task(self._bybit_orderbook(symbol)))
                elif exchange == Exchange.OKX:
                    tasks.append(asyncio.create_task(self._okx_orderbook(symbol)))
                elif exchange == Exchange.HYPERLIQUID:
                    tasks.append(asyncio.create_task(self._hyperliquid_orderbook(symbol)))
        return tasks

    async def _publish_book_update(self, book: LocalOrderBook, is_snapshot: bool = False, sequence: Optional[int] = None) -> None:
        bids, asks = book.get_snapshot(20)
        update = OrderBookUpdate(
            exchange=book.exchange,
            symbol=book.symbol,
            bids=bids,
            asks=asks,
            timestamp_ms=now_ms(),
            received_ms=now_ms(),
            is_snapshot=is_snapshot,
            sequence=sequence,
        )
        event = EventType.ORDERBOOK_SNAPSHOT if is_snapshot else EventType.ORDERBOOK_UPDATE
        await self.bus.publish(event, update)

    # ------------------------------------------------------------------
    # Binance: depth@100ms + REST snapshot
    # ------------------------------------------------------------------
    async def _binance_orderbook(self, symbol: str) -> None:
        ws_sym = to_binance_symbol(symbol)
        url = f"wss://fstream.binance.com/ws/{ws_sym}@depth@100ms"
        book = self._get_book(Exchange.BINANCE, symbol)
        buffer: List[dict] = []
        snapshot_fetched = asyncio.Event()

        async def fetch_snapshot() -> None:
            """Fetch REST snapshot and apply buffered updates."""
            try:
                snap = await self._rest_get(
                    f"https://fapi.binance.com/fapi/v1/depth",
                    Exchange.BINANCE,
                    params={"symbol": normalize_symbol(symbol), "limit": "100"},
                )
                last_update_id = snap["lastUpdateId"]
                bids = [(float(p), float(q)) for p, q in snap["bids"]]
                asks = [(float(p), float(q)) for p, q in snap["asks"]]
                book.set_snapshot(bids, asks, last_update_id)
                # Apply buffered deltas
                for msg in buffer:
                    final_id = msg.get("u", 0)
                    first_id = msg.get("U", 0)
                    if final_id <= last_update_id:
                        continue
                    if first_id <= last_update_id + 1:
                        delta_bids = [(float(p), float(q)) for p, q in msg.get("b", [])]
                        delta_asks = [(float(p), float(q)) for p, q in msg.get("a", [])]
                        book.apply_delta(delta_bids, delta_asks, final_id)
                buffer.clear()
                await self._publish_book_update(book, is_snapshot=True, sequence=last_update_id)
                snapshot_fetched.set()
                logger.info("Binance OB snapshot applied for %s (lastUpdateId=%d)", symbol, last_update_id)
            except Exception as exc:
                logger.error("Binance snapshot fetch failed for %s: %s", symbol, exc)

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict) or "e" not in data:
                return
            if data["e"] != "depthUpdate":
                return

            if not snapshot_fetched.is_set():
                buffer.append(data)
                if len(buffer) == 1:
                    asyncio.create_task(fetch_snapshot())
                return

            final_id = data.get("u", 0)
            delta_bids = [(float(p), float(q)) for p, q in data.get("b", [])]
            delta_asks = [(float(p), float(q)) for p, q in data.get("a", [])]
            book.apply_delta(delta_bids, delta_asks, final_id)

            if book.is_crossed():
                logger.warning("Binance book crossed for %s — re-snapshotting", symbol)
                book._synced = False
                snapshot_fetched.clear()
                buffer.clear()
                asyncio.create_task(fetch_snapshot())
                return

            await self._publish_book_update(book, sequence=final_id)

        await self._ws_connect_loop(
            url, on_msg, Exchange.BINANCE, symbol, stream_type="depth",
        )

    # ------------------------------------------------------------------
    # Bybit: orderbook.50.<symbol> (snapshot + delta)
    # ------------------------------------------------------------------
    async def _bybit_orderbook(self, symbol: str) -> None:
        url = "wss://stream.bybit.com/v5/public/linear"
        bybit_sym = to_bybit_symbol(symbol)
        sub = {
            "op": "subscribe",
            "args": [f"orderbook.50.{bybit_sym}"],
        }
        book = self._get_book(Exchange.BYBIT, symbol)

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            topic = data.get("topic", "")
            if not topic.startswith("orderbook."):
                return

            msg_type = data.get("type", "")
            ob_data = data.get("data", {})
            seq = data.get("cts", data.get("ts"))
            if isinstance(seq, str):
                seq = int(seq)

            bids = [(float(p), float(q)) for p, q in ob_data.get("b", [])]
            asks = [(float(p), float(q)) for p, q in ob_data.get("a", [])]

            if msg_type == "snapshot":
                book.set_snapshot(bids, asks, seq)
                await self._publish_book_update(book, is_snapshot=True, sequence=seq)
            elif msg_type == "delta":
                book.apply_delta(bids, asks, seq)
                if book.is_crossed():
                    logger.warning("Bybit book crossed for %s — waiting for next snapshot", symbol)
                    book._synced = False
                else:
                    await self._publish_book_update(book, sequence=seq)

        await self._ws_connect_loop(
            url, on_msg, Exchange.BYBIT, symbol,
            subscribe_msg=sub, stream_type="orderbook",
        )

    # ------------------------------------------------------------------
    # OKX: books5 channel (5-level snapshots)
    # ------------------------------------------------------------------
    async def _okx_orderbook(self, symbol: str) -> None:
        url = "wss://ws.okx.com:8443/ws/v5/public"
        okx_inst = to_okx_symbol(symbol)
        sub = {
            "op": "subscribe",
            "args": [{"channel": "books5", "instId": okx_inst}],
        }
        book = self._get_book(Exchange.OKX, symbol)

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            if "data" not in data:
                return
            for item in data["data"]:
                ts = int(item.get("ts", now_ms()))
                bids = [(float(p), float(q)) for p, q, *_ in item.get("bids", [])]
                asks = [(float(p), float(q)) for p, q, *_ in item.get("asks", [])]
                # books5 always sends full 5-level snapshot
                book.set_snapshot(bids, asks)
                await self._publish_book_update(book, is_snapshot=True)

        await self._ws_connect_loop(
            url, on_msg, Exchange.OKX, symbol,
            subscribe_msg=sub, stream_type="books5",
        )

    # ------------------------------------------------------------------
    # Hyperliquid: l2Book subscription
    # ------------------------------------------------------------------
    async def _hyperliquid_orderbook(self, symbol: str) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        coin = to_hyperliquid_coin(symbol)
        sub = {
            "method": "subscribe",
            "subscription": {"type": "l2Book", "coin": coin},
        }
        book = self._get_book(Exchange.HYPERLIQUID, symbol)

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            channel = data.get("channel")
            if channel != "l2Book":
                return
            book_data = data.get("data", {})
            levels = book_data.get("levels", [[], []])
            if len(levels) < 2:
                return
            bids = [(float(l.get("px", 0)), float(l.get("sz", 0))) for l in levels[0]]
            asks = [(float(l.get("px", 0)), float(l.get("sz", 0))) for l in levels[1]]
            # Hyperliquid sends full book snapshots
            book.set_snapshot(bids, asks)
            await self._publish_book_update(book, is_snapshot=True)

        await self._ws_connect_loop(
            url, on_msg, Exchange.HYPERLIQUID, symbol,
            subscribe_msg=sub, stream_type="l2Book",
        )

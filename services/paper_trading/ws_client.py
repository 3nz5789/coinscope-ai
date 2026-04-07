"""
CoinScopeAI Paper Trading — WebSocket Client
===============================================
Real-time market data and user data streams from Binance Futures Testnet.

Features:
- Kline (candlestick) streams for real-time OHLCV data
- User data stream for order updates and position changes
- Automatic reconnection with exponential backoff
- Heartbeat/keepalive management
- Thread-safe callback dispatch
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import websockets

from .config import BINANCE_FUTURES_TESTNET_WS, ExchangeConfig

logger = logging.getLogger("coinscopeai.paper_trading.ws")


@dataclass
class KlineEvent:
    """Parsed kline/candlestick event."""
    symbol: str
    interval: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool
    trades: int
    timestamp: int


@dataclass
class OrderUpdateEvent:
    """Parsed order update event."""
    symbol: str
    side: str
    order_type: str
    status: str
    order_id: int
    client_order_id: str
    price: float
    avg_price: float
    quantity: float
    executed_qty: float
    timestamp: int
    raw: Dict[str, Any]


@dataclass
class AccountUpdateEvent:
    """Parsed account update event."""
    event_reason: str
    balances: List[Dict[str, float]]
    positions: List[Dict[str, Any]]
    timestamp: int


class BinanceFuturesWebSocket:
    """
    Binance Futures Testnet WebSocket client.

    Manages market data streams (klines) and user data streams
    (order updates, account changes) with automatic reconnection.
    """

    MAX_RECONNECT_ATTEMPTS = 50
    INITIAL_RECONNECT_DELAY = 1.0
    MAX_RECONNECT_DELAY = 60.0
    KEEPALIVE_INTERVAL = 300  # 5 minutes

    def __init__(self, config: Optional[ExchangeConfig] = None):
        self._config = config or ExchangeConfig()
        self._ws_base = BINANCE_FUTURES_TESTNET_WS
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._connections: Dict[str, Any] = {}
        self._reconnect_count = 0

        # Callbacks
        self._on_kline: Optional[Callable[[KlineEvent], None]] = None
        self._on_order_update: Optional[Callable[[OrderUpdateEvent], None]] = None
        self._on_account_update: Optional[Callable[[AccountUpdateEvent], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None

        # Subscriptions
        self._kline_subscriptions: List[str] = []  # ["btcusdt@kline_4h", ...]

    def on_kline(self, callback: Callable[[KlineEvent], None]):
        """Register kline event callback."""
        self._on_kline = callback

    def on_order_update(self, callback: Callable[[OrderUpdateEvent], None]):
        """Register order update callback."""
        self._on_order_update = callback

    def on_account_update(self, callback: Callable[[AccountUpdateEvent], None]):
        """Register account update callback."""
        self._on_account_update = callback

    def on_error(self, callback: Callable[[Exception], None]):
        """Register error callback."""
        self._on_error = callback

    def on_disconnect(self, callback: Callable[[], None]):
        """Register disconnect callback."""
        self._on_disconnect = callback

    def subscribe_klines(self, symbols: List[str], interval: str = "4h"):
        """Subscribe to kline streams for multiple symbols."""
        for symbol in symbols:
            stream = f"{symbol.lower()}@kline_{interval}"
            if stream not in self._kline_subscriptions:
                self._kline_subscriptions.append(stream)

    def start(self):
        """Start WebSocket connections in a background thread."""
        if self._running:
            logger.warning("WebSocket already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("WebSocket client started")

    def stop(self):
        """Stop all WebSocket connections."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("WebSocket client stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def _run_loop(self):
        """Run the asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_all())
        except Exception as e:
            logger.error("WebSocket loop error: %s", e)
        finally:
            self._loop.close()

    async def _connect_all(self):
        """Connect to all subscribed streams."""
        tasks = []

        if self._kline_subscriptions:
            tasks.append(self._connect_market_stream())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect_market_stream(self):
        """Connect to combined market data stream."""
        streams = "/".join(self._kline_subscriptions)
        url = f"{self._ws_base}/stream?streams={streams}"

        while self._running:
            try:
                logger.info("Connecting to market stream: %s", url)
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._reconnect_count = 0
                    logger.info("Market stream connected (%d streams)",
                                len(self._kline_subscriptions))

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self._handle_market_message(data)
                        except Exception as e:
                            logger.error("Error handling market message: %s", e)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("Market stream disconnected: %s", e)
            except Exception as e:
                logger.error("Market stream error: %s", e)
                if self._on_error:
                    self._on_error(e)

            if self._running:
                await self._reconnect_delay()

    async def _connect_user_stream(self, listen_key: str):
        """Connect to user data stream for order/account updates."""
        url = f"{self._ws_base}/ws/{listen_key}"

        while self._running:
            try:
                logger.info("Connecting to user data stream")
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    logger.info("User data stream connected")

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self._handle_user_message(data)
                        except Exception as e:
                            logger.error("Error handling user message: %s", e)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("User stream disconnected: %s", e)
            except Exception as e:
                logger.error("User stream error: %s", e)

            if self._running:
                await self._reconnect_delay()

    async def _reconnect_delay(self):
        """Exponential backoff for reconnection."""
        self._reconnect_count += 1
        if self._reconnect_count > self.MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached, stopping")
            self._running = False
            if self._on_disconnect:
                self._on_disconnect()
            return

        delay = min(
            self.INITIAL_RECONNECT_DELAY * (2 ** (self._reconnect_count - 1)),
            self.MAX_RECONNECT_DELAY,
        )
        logger.info("Reconnecting in %.1fs (attempt %d/%d)",
                     delay, self._reconnect_count, self.MAX_RECONNECT_ATTEMPTS)
        await asyncio.sleep(delay)

    def _handle_market_message(self, data: Dict):
        """Parse and dispatch market data messages."""
        stream_data = data.get("data", data)
        event_type = stream_data.get("e")

        if event_type == "kline":
            kline = stream_data.get("k", {})
            event = KlineEvent(
                symbol=stream_data.get("s", ""),
                interval=kline.get("i", ""),
                open_time=kline.get("t", 0),
                close_time=kline.get("T", 0),
                open=float(kline.get("o", 0)),
                high=float(kline.get("h", 0)),
                low=float(kline.get("l", 0)),
                close=float(kline.get("c", 0)),
                volume=float(kline.get("v", 0)),
                is_closed=kline.get("x", False),
                trades=kline.get("n", 0),
                timestamp=stream_data.get("E", 0),
            )

            if self._on_kline:
                try:
                    self._on_kline(event)
                except Exception as e:
                    logger.error("Kline callback error: %s", e)

    def _handle_user_message(self, data: Dict):
        """Parse and dispatch user data messages."""
        event_type = data.get("e")

        if event_type == "ORDER_TRADE_UPDATE":
            order = data.get("o", {})
            event = OrderUpdateEvent(
                symbol=order.get("s", ""),
                side=order.get("S", ""),
                order_type=order.get("o", ""),
                status=order.get("X", ""),
                order_id=order.get("i", 0),
                client_order_id=order.get("c", ""),
                price=float(order.get("p", 0)),
                avg_price=float(order.get("ap", 0)),
                quantity=float(order.get("q", 0)),
                executed_qty=float(order.get("z", 0)),
                timestamp=data.get("E", 0),
                raw=data,
            )
            if self._on_order_update:
                try:
                    self._on_order_update(event)
                except Exception as e:
                    logger.error("Order update callback error: %s", e)

        elif event_type == "ACCOUNT_UPDATE":
            update = data.get("a", {})
            balances = [
                {"asset": b.get("a", ""), "balance": float(b.get("wb", 0)),
                 "cross_wallet": float(b.get("cw", 0))}
                for b in update.get("B", [])
            ]
            positions = [
                {"symbol": p.get("s", ""), "amount": float(p.get("pa", 0)),
                 "entry_price": float(p.get("ep", 0)),
                 "unrealized_pnl": float(p.get("up", 0))}
                for p in update.get("P", [])
            ]
            event = AccountUpdateEvent(
                event_reason=update.get("m", ""),
                balances=balances,
                positions=positions,
                timestamp=data.get("E", 0),
            )
            if self._on_account_update:
                try:
                    self._on_account_update(event)
                except Exception as e:
                    logger.error("Account update callback error: %s", e)

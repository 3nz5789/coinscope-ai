"""
Base stream infrastructure for CoinScopeAI market data.

Provides:
- Unified data models (Trade, OrderBookUpdate, FundingRate, Liquidation)
- EventBus for pub/sub across all streams
- Abstract BaseStream with auto-reconnect WebSocket management
- Rate limiter for REST endpoints
"""

from __future__ import annotations

import asyncio
import enum
import gzip
import json
import logging
import signal
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

import aiohttp
import orjson

logger = logging.getLogger("coinscopeai.streams")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Exchange(str, enum.Enum):
    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    HYPERLIQUID = "hyperliquid"


class Side(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class EventType(str, enum.Enum):
    TRADE = "trade"
    ORDERBOOK_UPDATE = "orderbook_update"
    ORDERBOOK_SNAPSHOT = "orderbook_snapshot"
    FUNDING_RATE = "funding_rate"
    LIQUIDATION = "liquidation"
    STREAM_STATUS = "stream_status"


# ---------------------------------------------------------------------------
# Unified Data Models
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Trade:
    exchange: str
    symbol: str
    trade_id: str
    price: float
    quantity: float
    side: str          # "buy" | "sell"
    timestamp_ms: int  # exchange timestamp in milliseconds
    received_ms: int   # local receive timestamp in milliseconds
    raw: Optional[dict] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())


@dataclass(slots=True)
class OrderBookLevel:
    price: float
    quantity: float


@dataclass(slots=True)
class OrderBookUpdate:
    exchange: str
    symbol: str
    bids: List[OrderBookLevel]  # sorted best→worst (desc price)
    asks: List[OrderBookLevel]  # sorted best→worst (asc price)
    timestamp_ms: int
    received_ms: int
    is_snapshot: bool = False
    sequence: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "bids": [[l.price, l.quantity] for l in self.bids],
            "asks": [[l.price, l.quantity] for l in self.asks],
            "timestamp_ms": self.timestamp_ms,
            "received_ms": self.received_ms,
            "is_snapshot": self.is_snapshot,
            "sequence": self.sequence,
        }

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())


@dataclass(slots=True)
class FundingRate:
    exchange: str
    symbol: str
    funding_rate: float
    predicted_rate: Optional[float]
    funding_time_ms: int       # next funding timestamp
    timestamp_ms: int          # when this data was produced
    received_ms: int
    mark_price: Optional[float] = None
    index_price: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())


@dataclass(slots=True)
class Liquidation:
    exchange: str
    symbol: str
    side: str          # "buy" | "sell" — the side that was liquidated
    price: float
    quantity: float
    usd_value: float
    timestamp_ms: int
    received_ms: int
    is_derived: bool = False  # True if inferred (e.g., Hyperliquid)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())


@dataclass(slots=True)
class StreamStatus:
    exchange: str
    stream_type: str
    symbol: str
    connected: bool
    message: str
    timestamp_ms: int

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())


# ---------------------------------------------------------------------------
# EventBus — lightweight async pub/sub
# ---------------------------------------------------------------------------

Callback = Callable[[EventType, Any], Awaitable[None]]


class EventBus:
    """Simple async event bus for decoupling streams from consumers."""

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Callback]] = {}
        self._global_subscribers: List[Callback] = []
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: EventType, callback: Callback) -> None:
        async with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    async def subscribe_all(self, callback: Callback) -> None:
        """Subscribe to every event type."""
        async with self._lock:
            self._global_subscribers.append(callback)

    async def unsubscribe(self, event_type: EventType, callback: Callback) -> None:
        async with self._lock:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)

    async def publish(self, event_type: EventType, data: Any) -> None:
        callbacks: List[Callback] = []
        async with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))
            callbacks.extend(self._global_subscribers)
        for cb in callbacks:
            try:
                await cb(event_type, data)
            except Exception:
                logger.exception("EventBus callback error for %s", event_type)

    def publish_nowait(self, event_type: EventType, data: Any, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Fire-and-forget publish (schedules coroutine on the loop)."""
        _loop = loop or asyncio.get_event_loop()
        _loop.create_task(self.publish(event_type, data))


# Singleton-ish default bus
_default_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def set_event_bus(bus: EventBus) -> None:
    global _default_bus
    _default_bus = bus


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Token-bucket rate limiter for REST calls."""

    def __init__(self, calls_per_second: float = 5.0):
        self._rate = calls_per_second
        self._tokens = calls_per_second
        self._max_tokens = calls_per_second
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._last = now
            self._tokens = min(self._max_tokens, self._tokens + elapsed * self._rate)
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


# ---------------------------------------------------------------------------
# Symbol Normalisation helpers
# ---------------------------------------------------------------------------

def normalize_symbol(symbol: str) -> str:
    """Normalize to uppercase without separators: BTCUSDT"""
    return symbol.upper().replace("-", "").replace("_", "").replace("/", "")


def to_binance_symbol(symbol: str) -> str:
    return normalize_symbol(symbol).lower()


def to_bybit_symbol(symbol: str) -> str:
    return normalize_symbol(symbol)


def to_okx_symbol(symbol: str) -> str:
    """OKX uses BTC-USDT-SWAP for perpetuals."""
    s = normalize_symbol(symbol)
    # Try to split base/quote
    for quote in ("USDT", "USDC", "USD", "BUSD"):
        if s.endswith(quote):
            base = s[: -len(quote)]
            return f"{base}-{quote}-SWAP"
    return s


def to_hyperliquid_coin(symbol: str) -> str:
    """Hyperliquid uses just the base coin: BTC, ETH, etc."""
    s = normalize_symbol(symbol)
    for quote in ("USDT", "USDC", "USD", "BUSD", "PERP"):
        if s.endswith(quote):
            return s[: -len(quote)]
    return s


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Abstract Base Stream
# ---------------------------------------------------------------------------

class BaseStream(ABC):
    """
    Abstract base for all market data streams.

    Provides:
    - Auto-reconnect WebSocket management with exponential backoff
    - Graceful shutdown
    - EventBus integration
    """

    MAX_RECONNECT_DELAY = 60.0
    INITIAL_RECONNECT_DELAY = 1.0

    def __init__(
        self,
        symbols: List[str],
        exchanges: Optional[List[Exchange]] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.symbols = [normalize_symbol(s) for s in symbols]
        self.exchanges = exchanges or list(Exchange)
        self.bus = event_bus or get_event_bus()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start all exchange connections."""
        if self._running:
            return
        self._running = True
        self._session = aiohttp.ClientSession()
        self._tasks = self._create_tasks()
        logger.info("%s started for %s on %s", self.__class__.__name__, self.symbols, [e.value for e in self.exchanges])

    async def stop(self) -> None:
        """Gracefully stop all connections."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("%s stopped", self.__class__.__name__)

    @abstractmethod
    def _create_tasks(self) -> List[asyncio.Task]:
        """Return list of asyncio.Tasks for each exchange/symbol combo."""
        ...

    # ---- WebSocket helpers ----

    async def _ws_connect_loop(
        self,
        url: str,
        on_message: Callable[[Any], Awaitable[None]],
        exchange: Exchange,
        symbol: str,
        subscribe_msg: Optional[Any] = None,
        ping_interval: float = 20.0,
        stream_type: str = "",
    ) -> None:
        """Connect to a WebSocket with auto-reconnect and exponential backoff."""
        delay = self.INITIAL_RECONNECT_DELAY
        while self._running:
            try:
                async with self._session.ws_connect(
                    url,
                    heartbeat=ping_interval,
                    max_msg_size=10 * 1024 * 1024,
                ) as ws:
                    delay = self.INITIAL_RECONNECT_DELAY  # reset on success
                    logger.info("WS connected: %s %s %s", exchange.value, stream_type, symbol)
                    await self.bus.publish(
                        EventType.STREAM_STATUS,
                        StreamStatus(
                            exchange=exchange.value,
                            stream_type=stream_type,
                            symbol=symbol,
                            connected=True,
                            message="connected",
                            timestamp_ms=now_ms(),
                        ),
                    )
                    if subscribe_msg is not None:
                        if isinstance(subscribe_msg, (dict, list)):
                            await ws.send_json(subscribe_msg)
                        else:
                            await ws.send_str(str(subscribe_msg))

                    async for msg in ws:
                        if not self._running:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = orjson.loads(msg.data)
                            except Exception:
                                data = msg.data
                            await on_message(data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            try:
                                raw = gzip.decompress(msg.data)
                                data = orjson.loads(raw)
                            except Exception:
                                data = msg.data
                            await on_message(data)
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                            break

            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("WS error %s %s %s: %s", exchange.value, stream_type, symbol, exc)

            if self._running:
                await self.bus.publish(
                    EventType.STREAM_STATUS,
                    StreamStatus(
                        exchange=exchange.value,
                        stream_type=stream_type,
                        symbol=symbol,
                        connected=False,
                        message=f"reconnecting in {delay:.1f}s",
                        timestamp_ms=now_ms(),
                    ),
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, self.MAX_RECONNECT_DELAY)

    # ---- REST helpers ----

    _rate_limiters: Dict[str, RateLimiter] = {}

    def _get_rate_limiter(self, exchange: Exchange) -> RateLimiter:
        key = exchange.value
        if key not in BaseStream._rate_limiters:
            # Conservative defaults per exchange
            rates = {
                Exchange.BINANCE.value: 8.0,
                Exchange.BYBIT.value: 5.0,
                Exchange.OKX.value: 5.0,
                Exchange.HYPERLIQUID.value: 5.0,
            }
            BaseStream._rate_limiters[key] = RateLimiter(rates.get(key, 5.0))
        return BaseStream._rate_limiters[key]

    async def _rest_get(self, url: str, exchange: Exchange, params: Optional[dict] = None) -> Any:
        limiter = self._get_rate_limiter(exchange)
        await limiter.acquire()
        async with self._session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _rest_post(self, url: str, exchange: Exchange, json_data: Any = None) -> Any:
        limiter = self._get_rate_limiter(exchange)
        await limiter.acquire()
        async with self._session.post(url, json=json_data) as resp:
            resp.raise_for_status()
            return await resp.json()

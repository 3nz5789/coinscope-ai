"""
CoinScopeAI — Abstract Base Exchange Client

Provides:
- WebSocket lifecycle (connect / reconnect with exponential backoff)
- REST polling with rate-limit awareness
- Internal event bus (publish / subscribe)
- Connection health & metrics tracking
- Configurable symbol lists
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

from .models import (
    ConnectionMetrics,
    ConnectionState,
    EventType,
    Exchange,
    MarketEvent,
)

logger = logging.getLogger("coinscopeai.market_data")

# Type alias for event callbacks
EventCallback = Callable[[MarketEvent], Coroutine[Any, Any, None]]


class RateLimiter:
    """Token-bucket rate limiter for REST endpoints."""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period          # seconds
        self._tokens = max_calls
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            refill = elapsed / self.period * self.max_calls
            self._tokens = min(self.max_calls, self._tokens + refill)
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) / self.max_calls * self.period
                logger.debug("Rate limiter: sleeping %.2fs", wait)
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1


class EventBus:
    """Simple async publish / subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[EventCallback]] = defaultdict(list)
        self._global_subscribers: List[EventCallback] = []

    def subscribe(self, event_type: EventType, callback: EventCallback) -> None:
        self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        self._global_subscribers.append(callback)

    async def publish(self, event: MarketEvent) -> None:
        callbacks = self._subscribers.get(event.event_type, []) + self._global_subscribers
        for cb in callbacks:
            try:
                await cb(event)
            except Exception:
                logger.exception("Event callback error for %s", event.event_type)


class BaseExchangeClient(abc.ABC):
    """Abstract base class for all exchange feed clients."""

    # Subclasses must set these
    EXCHANGE: Exchange = NotImplemented  # type: ignore[assignment]
    WS_BASE_URL: str = ""
    REST_BASE_URL: str = ""

    # Reconnect settings
    INITIAL_BACKOFF: float = 1.0
    MAX_BACKOFF: float = 60.0
    BACKOFF_FACTOR: float = 2.0
    HEARTBEAT_INTERVAL: float = 30.0
    HEARTBEAT_TIMEOUT: float = 10.0

    def __init__(
        self,
        symbols: List[str],
        event_bus: Optional[EventBus] = None,
        rest_rate_limit: int = 10,
        rest_rate_period: float = 1.0,
    ) -> None:
        self.symbols: List[str] = [s.upper() for s in symbols]
        self.event_bus: EventBus = event_bus or EventBus()
        self.rate_limiter = RateLimiter(rest_rate_limit, rest_rate_period)
        self.metrics = ConnectionMetrics(exchange=self.EXCHANGE)
        self._ws = None
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._backoff = self.INITIAL_BACKOFF
        self._session = None  # aiohttp session

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start all WebSocket streams and REST pollers."""
        logger.info("[%s] Starting client for symbols: %s", self.EXCHANGE.value, self.symbols)
        self._running = True
        self._tasks = []
        self._tasks.extend(self._create_ws_tasks())
        self._tasks.extend(self._create_rest_tasks())
        # Don't await — let caller manage the event loop
        for t in self._tasks:
            t.add_done_callback(self._task_done_callback)

    async def stop(self) -> None:
        """Gracefully shut down all tasks and connections."""
        logger.info("[%s] Stopping client", self.EXCHANGE.value)
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._session and not self._session.closed:
            await self._session.close()
        self.metrics.state = ConnectionState.DISCONNECTED
        logger.info("[%s] Client stopped", self.EXCHANGE.value)

    def _task_done_callback(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("[%s] Task failed: %s", self.EXCHANGE.value, exc)

    # ------------------------------------------------------------------
    # Abstract methods — subclasses must implement
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _create_ws_tasks(self) -> List[asyncio.Task]:
        """Return a list of asyncio Tasks for WebSocket streams."""
        ...

    @abc.abstractmethod
    def _create_rest_tasks(self) -> List[asyncio.Task]:
        """Return a list of asyncio Tasks for REST polling loops."""
        ...

    # ------------------------------------------------------------------
    # WebSocket helpers
    # ------------------------------------------------------------------

    async def _ws_connect_loop(
        self,
        url: str,
        on_message: Callable[[str], Coroutine[Any, Any, None]],
        subscribe_msg: Optional[Any] = None,
        label: str = "ws",
    ) -> None:
        """
        Generic WebSocket connection loop with:
        - auto-reconnect on disconnect
        - exponential backoff
        - heartbeat monitoring
        """
        import websockets
        import json

        backoff = self.INITIAL_BACKOFF
        while self._running:
            try:
                self.metrics.state = ConnectionState.CONNECTING
                logger.info("[%s][%s] Connecting to %s", self.EXCHANGE.value, label, url)

                async with websockets.connect(
                    url,
                    ping_interval=self.HEARTBEAT_INTERVAL,
                    ping_timeout=self.HEARTBEAT_TIMEOUT,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,  # 10 MB
                ) as ws:
                    self.metrics.state = ConnectionState.CONNECTED
                    self.metrics.connected_at = time.time()
                    backoff = self.INITIAL_BACKOFF
                    logger.info("[%s][%s] Connected", self.EXCHANGE.value, label)

                    # Send subscription message if provided
                    if subscribe_msg is not None:
                        payload = json.dumps(subscribe_msg) if isinstance(subscribe_msg, (dict, list)) else str(subscribe_msg)
                        await ws.send(payload)
                        logger.debug("[%s][%s] Sent subscription: %s", self.EXCHANGE.value, label, payload[:200])

                    async for raw_msg in ws:
                        if not self._running:
                            break
                        self.metrics.messages_received += 1
                        self.metrics.last_message_at = time.time()
                        try:
                            await on_message(raw_msg)
                        except Exception:
                            logger.exception("[%s][%s] Error processing message", self.EXCHANGE.value, label)
                            self.metrics.errors += 1

            except asyncio.CancelledError:
                logger.info("[%s][%s] Task cancelled", self.EXCHANGE.value, label)
                return
            except Exception as exc:
                self.metrics.errors += 1
                self.metrics.reconnect_count += 1
                self.metrics.state = ConnectionState.RECONNECTING
                logger.warning(
                    "[%s][%s] Disconnected (%s). Reconnecting in %.1fs",
                    self.EXCHANGE.value, label, exc, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * self.BACKOFF_FACTOR, self.MAX_BACKOFF)

    # ------------------------------------------------------------------
    # REST helpers
    # ------------------------------------------------------------------

    async def _get_session(self):
        import aiohttp
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _rest_get(self, url: str, params: Optional[Dict] = None) -> Any:
        """Rate-limited GET request returning parsed JSON."""
        import aiohttp
        await self.rate_limiter.acquire()
        session = await self._get_session()
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception:
            self.metrics.errors += 1
            raise

    async def _rest_poll_loop(
        self,
        label: str,
        interval: float,
        poll_fn: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Generic REST polling loop with error handling."""
        while self._running:
            try:
                await poll_fn()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("[%s][%s] REST poll error", self.EXCHANGE.value, label)
                self.metrics.errors += 1
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Event publishing helper
    # ------------------------------------------------------------------

    async def _publish(self, event_type: EventType, data: Any, symbol: str) -> None:
        event = MarketEvent(
            event_type=event_type,
            data=data,
            exchange=self.EXCHANGE,
            symbol=symbol,
            timestamp=time.time(),
        )
        await self.event_bus.publish(event)

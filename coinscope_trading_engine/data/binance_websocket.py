"""
binance_websocket.py — Binance Futures WebSocket Connection Manager
====================================================================
Implements the Binance WebSocket API (ws-fapi/v1) for the CoinScopeAI engine.

Spec compliance
---------------
* Base endpoints  : wss://ws-fapi.binance.com/ws-fapi/v1  (mainnet)
                    wss://testnet.binancefuture.com/ws-fapi/v1  (testnet)
* Connection TTL  : 24 hours — automatically reconnects before expiry
* Ping/pong       : Server pings every ~3 min; must pong within 10 min
* Session auth    : session.logon / session.status / session.logout
* Request format  : {"id": ..., "method": ..., "params": {...}}
* Response format : {"id": ..., "status": 200, "result": {...}}
* Signatures      : HMAC-SHA256 (params sorted alphabetically, joined with &)
* Rate limits     : Tracked per response; REQUEST_WEIGHT / ORDERS windows

Usage
-----
    from data.binance_websocket import BinanceWebSocketManager

    async with BinanceWebSocketManager(testnet=True) as ws:
        await ws.session_logon()
        result = await ws.request("account.status", signed=True)
        print(result)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WS_MAINNET_URL  = "wss://ws-fapi.binance.com/ws-fapi/v1"
# NOTE: Binance retired the futures testnet (`testnet.binancefuture.com`).
# The Futures Demo at `demo-fapi.binance.com` exposes REST + market-streams
# (`wss://demo-fstream.binance.com`) but signed WS (`/ws-fapi/v1`) is NOT
# enabled on demo as of 2026-04 — an upgrade attempt gets HTTP 403.
# This client is currently unused by api.py; use REST + listen-key user-data
# stream on the market-streams host instead.
WS_TESTNET_URL  = "wss://ws-fapi.binance.com/ws-fapi/v1"  # mainnet fallback; DO NOT use for demo trading

# Reconnect 60 s before the hard 24-hour server limit
CONNECTION_MAX_AGE_S   = 23 * 3600 + 0 * 60   # 23 h
PONG_TIMEOUT_S         = 9 * 60                 # server disconnects at 10 min
RECONNECT_DELAY_S      = 5                      # base backoff on errors
MAX_RECONNECT_DELAY_S  = 60
REQUEST_TIMEOUT_S      = 10                     # default per-request timeout


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class RateLimitType(str, Enum):
    REQUEST_WEIGHT = "REQUEST_WEIGHT"
    ORDERS         = "ORDERS"


@dataclass
class RateLimitBucket:
    rate_limit_type: str
    interval: str
    interval_num: int
    limit: int
    count: int = 0

    @property
    def key(self) -> str:
        return f"{self.rate_limit_type}:{self.interval}:{self.interval_num}"


@dataclass
class PendingRequest:
    """Holds a Future that will receive the server's response."""
    future: asyncio.Future
    sent_at: float = field(default_factory=time.monotonic)


@dataclass
class ConnectionStats:
    connected_at: float   = 0.0
    requests_sent: int    = 0
    responses_received: int = 0
    pings_received: int   = 0
    reconnects: int       = 0
    last_error: str       = ""

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self.connected_at if self.connected_at else 0.0


# ---------------------------------------------------------------------------
# Signature helper
# ---------------------------------------------------------------------------

def _hmac_signature(secret: str, params: dict[str, Any]) -> str:
    """
    Build a HMAC-SHA256 signature for a set of request params.

    Spec: sort params alphabetically, join as key=value&key=value,
    then HMAC-SHA256 with the API secret.
    """
    payload = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Main manager class
# ---------------------------------------------------------------------------

class BinanceWebSocketManager:
    """
    Persistent, auto-reconnecting WebSocket connection to the Binance
    Futures WebSocket API.

    Features
    --------
    * Automatic pong replies to server pings (within PONG_TIMEOUT_S)
    * Proactive reconnection before the 24-hour server TTL
    * Exponential backoff on connection errors
    * Request/response matching via UUID id field
    * Session authentication (session.logon) with automatic re-auth on reconnect
    * Rate-limit tracking parsed from every response
    * Subscriber callbacks for real-time market stream events

    Parameters
    ----------
    testnet : bool
        When True (default) uses the Binance Futures testnet endpoint.
        Overrides the global ``settings.testnet_mode`` flag when set explicitly.
    auto_reconnect : bool
        Continuously reconnect on disconnection (default True).
    return_rate_limits : bool
        Pass ``returnRateLimits=false`` to the connection URL to suppress
        rate-limit fields in every response (default True = include them).
    """

    def __init__(
        self,
        testnet: Optional[bool] = None,
        auto_reconnect: bool = True,
        return_rate_limits: bool = True,
    ) -> None:
        self._testnet         = testnet if testnet is not None else settings.testnet_mode
        self._auto_reconnect  = auto_reconnect
        self._return_rate_limits = return_rate_limits

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected       = asyncio.Event()
        self._shutdown        = asyncio.Event()

        # Pending request map: id → PendingRequest
        self._pending: dict[str, PendingRequest] = {}

        # Rate limit state
        self._rate_limits: dict[str, RateLimitBucket] = {}

        # Session auth state
        self._session_authenticated = False
        self._api_key: str  = ""
        self._api_secret: str = ""

        # Reconnect state
        self._reconnect_delay = RECONNECT_DELAY_S

        # Stats
        self.stats = ConnectionStats()

        # Optional stream event subscribers: method_prefix → [callback]
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

        # Background tasks
        self._recv_task:    Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        base = WS_TESTNET_URL if self._testnet else WS_MAINNET_URL
        if not self._return_rate_limits:
            return f"{base}?returnRateLimits=false"
        return base

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def rate_limits(self) -> dict[str, RateLimitBucket]:
        return dict(self._rate_limits)

    # ── Context manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "BinanceWebSocketManager":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Connection lifecycle ─────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the WebSocket connection and start background tasks."""
        logger.info(
            "Connecting to Binance WS API [%s] → %s",
            "testnet" if self._testnet else "mainnet",
            self.url,
        )
        await self._do_connect()
        self._recv_task     = asyncio.create_task(self._recv_loop(),     name="ws_recv")
        self._watchdog_task = asyncio.create_task(self._watchdog_loop(), name="ws_watchdog")

    async def _do_connect(self) -> None:
        """Low-level connect with retry."""
        while not self._shutdown.is_set():
            try:
                self._ws = await websockets.connect(
                    self.url,
                    ping_interval=None,   # we handle pings manually
                    ping_timeout=None,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,  # 10 MB
                )
                self._connected.set()
                self.stats.connected_at = time.monotonic()
                self.stats.reconnects  += 1 if self.stats.reconnects else 0
                self._reconnect_delay   = RECONNECT_DELAY_S
                logger.info("WebSocket connected ✓  url=%s", self.url)

                # Re-authenticate if we had a session before
                if self._api_key and self._api_secret:
                    await self._authenticate(self._api_key, self._api_secret)
                return

            except (OSError, WebSocketException) as exc:
                self.stats.last_error = str(exc)
                logger.warning(
                    "WS connect failed: %s — retrying in %ds", exc, self._reconnect_delay
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2, MAX_RECONNECT_DELAY_S
                )

    async def close(self) -> None:
        """Gracefully close the connection and cancel background tasks."""
        logger.info("Closing WebSocket connection…")
        self._shutdown.set()
        self._connected.clear()

        for task in (self._recv_task, self._watchdog_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._ws and not self._ws.closed:
            await self._ws.close()

        # Fail all pending requests
        for req_id, pending in list(self._pending.items()):
            if not pending.future.done():
                pending.future.set_exception(
                    ConnectionError("WebSocket closed while request was pending.")
                )
        self._pending.clear()
        logger.info("WebSocket closed.")

    # ── Receive loop ────────────────────────────────────────────────────

    async def _recv_loop(self) -> None:
        """
        Continuously receive frames from the server.

        - Text frames  : JSON responses / stream events → dispatch
        - Ping frames  : reply with matching pong immediately
        """
        while not self._shutdown.is_set():
            try:
                await self._connected.wait()
                message = await self._ws.recv()

                if isinstance(message, bytes):
                    # Binary ping frame — websockets library handles at protocol
                    # level, but manual pong on application-level ping (text)
                    logger.debug("Received binary frame (%d bytes)", len(message))
                    continue

                await self._dispatch(message)

            except ConnectionClosed as exc:
                logger.warning("WS connection closed: %s", exc)
                self.stats.last_error = str(exc)
                self._connected.clear()
                self._session_authenticated = False

                if self._auto_reconnect and not self._shutdown.is_set():
                    self.stats.reconnects += 1
                    logger.info(
                        "Reconnecting… (attempt #%d)", self.stats.reconnects
                    )
                    await asyncio.sleep(self._reconnect_delay)
                    await self._do_connect()
                else:
                    break

            except asyncio.CancelledError:
                break

            except Exception as exc:
                logger.exception("Unexpected error in recv_loop: %s", exc)
                self.stats.last_error = str(exc)
                await asyncio.sleep(1)

    async def _dispatch(self, raw: str) -> None:
        """Parse an incoming JSON message and route it appropriately."""
        try:
            msg: dict = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON frame: %.200s", raw)
            return

        # --- Application-level ping (Binance sends {"ping": <timestamp>})
        if "ping" in msg:
            self.stats.pings_received += 1
            pong_payload = json.dumps({"pong": msg["ping"]})
            await self._ws.send(pong_payload)
            logger.debug("Pong sent (server ping ts=%s)", msg["ping"])
            return

        # --- Regular API response (has "id" field)
        msg_id = str(msg.get("id", ""))
        if msg_id and msg_id in self._pending:
            pending = self._pending.pop(msg_id)
            self.stats.responses_received += 1

            # Update rate-limit buckets
            for rl in msg.get("rateLimits", []):
                bucket = RateLimitBucket(
                    rate_limit_type=rl["rateLimitType"],
                    interval=rl["interval"],
                    interval_num=rl["intervalNum"],
                    limit=rl["limit"],
                    count=rl["count"],
                )
                self._rate_limits[bucket.key] = bucket

            if not pending.future.done():
                if msg.get("status", 0) == 200:
                    pending.future.set_result(msg.get("result"))
                else:
                    error = msg.get("error", {})
                    pending.future.set_exception(
                        BinanceAPIError(
                            code=error.get("code", -1),
                            msg=error.get("msg", "Unknown error"),
                            status=msg.get("status", 0),
                        )
                    )
            return

        # --- Stream event (market data push, no "id" match)
        method = msg.get("e") or msg.get("method") or "unknown"
        handlers = self._subscribers.get(method, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                result = handler(msg)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.exception("Subscriber error for event=%s: %s", method, exc)

    # ── Watchdog loop ────────────────────────────────────────────────────

    async def _watchdog_loop(self) -> None:
        """
        Proactively reconnect before the 24-hour connection TTL expires.
        Checks every minute; triggers reconnect when age > CONNECTION_MAX_AGE_S.
        """
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(60)
                if not self.is_connected:
                    continue
                age = self.stats.uptime_seconds
                if age >= CONNECTION_MAX_AGE_S:
                    logger.info(
                        "Connection age %.0f s reached TTL limit — proactive reconnect",
                        age,
                    )
                    self._connected.clear()
                    await self._ws.close()
                    await self._do_connect()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Watchdog error: %s", exc)

    # ── Public request API ───────────────────────────────────────────────

    async def request(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        signed: bool = False,
        timeout: float = REQUEST_TIMEOUT_S,
    ) -> Any:
        """
        Send a request to the Binance WebSocket API and await the response.

        Parameters
        ----------
        method : str
            WS API method name, e.g. ``"order.place"``, ``"account.status"``.
        params : dict, optional
            Request parameters.  Do NOT include ``apiKey``, ``timestamp``,
            or ``signature`` — those are added automatically when ``signed=True``.
        signed : bool
            If True, injects ``apiKey``, ``timestamp``, and ``signature``.
        timeout : float
            Seconds to wait for a response before raising ``asyncio.TimeoutError``.

        Returns
        -------
        Any
            The ``result`` field of the successful response object.

        Raises
        ------
        BinanceAPIError
            When the server returns a non-200 status.
        asyncio.TimeoutError
            When no response arrives within ``timeout`` seconds.
        ConnectionError
            When the socket is not connected.
        """
        if not self.is_connected:
            raise ConnectionError("WebSocket is not connected. Call connect() first.")

        req_params = dict(params or {})

        if signed:
            if not self._api_key or not self._api_secret:
                raise AuthenticationError(
                    "API key/secret not set. Call session_logon() first."
                )
            req_params["apiKey"]    = self._api_key
            req_params["timestamp"] = int(time.time() * 1000)
            req_params["signature"] = _hmac_signature(self._api_secret, req_params)

        req_id = str(uuid.uuid4())
        payload = {"id": req_id, "method": method}
        if req_params:
            payload["params"] = req_params

        loop   = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[req_id] = PendingRequest(future=future)

        self.stats.requests_sent += 1
        await self._ws.send(json.dumps(payload))
        logger.debug("→ %s  id=%s", method, req_id)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.debug("← %s  id=%s  OK", method, req_id)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise asyncio.TimeoutError(
                f"No response for method='{method}' within {timeout}s"
            )

    # ── Session authentication ───────────────────────────────────────────

    async def session_logon(
        self,
        api_key: Optional[str]    = None,
        api_secret: Optional[str] = None,
    ) -> dict:
        """
        Authenticate the WebSocket session using ``session.logon``.

        After this call succeeds, ``apiKey`` and ``signature`` are injected
        automatically for signed requests — you no longer need to pass them.

        Note: Only Ed25519 keys are supported by session.logon per the spec.
              HMAC keys can still sign individual requests via ``signed=True``.

        Parameters
        ----------
        api_key : str, optional
            Defaults to ``settings.active_api_key``.
        api_secret : str, optional
            Defaults to ``settings.active_api_secret``.
        """
        self._api_key    = api_key    or settings.active_api_key.get_secret_value()
        self._api_secret = api_secret or settings.active_api_secret.get_secret_value()

        await self._authenticate(self._api_key, self._api_secret)
        return {"authenticated": True, "apiKey": self._api_key}

    async def _authenticate(self, api_key: str, api_secret: str) -> None:
        """Internal — send session.logon and mark session as authenticated."""
        timestamp = int(time.time() * 1000)
        params = {
            "apiKey":    api_key,
            "timestamp": timestamp,
            "signature": _hmac_signature(api_secret, {"apiKey": api_key, "timestamp": timestamp}),
        }
        try:
            result = await self.request("session.logon", params=params)
            self._session_authenticated = True
            logger.info(
                "Session authenticated ✓  apiKey=%.8s…  since=%s",
                api_key,
                result.get("authorizedSince"),
            )
        except BinanceAPIError as exc:
            self._session_authenticated = False
            logger.error("Session authentication failed: %s", exc)
            raise

    async def session_status(self) -> dict:
        """Query the current session authentication status."""
        return await self.request("session.status")

    async def session_logout(self) -> dict:
        """Remove the API key from the current session."""
        result = await self.request("session.logout")
        self._session_authenticated = False
        self._api_key    = ""
        self._api_secret = ""
        logger.info("Session logged out.")
        return result

    # ── Convenience market-data methods ──────────────────────────────────

    async def get_ticker(self, symbol: str) -> dict:
        """Fetch the latest price ticker for a symbol."""
        return await self.request("ticker.price", params={"symbol": symbol})

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Fetch the order book depth snapshot."""
        return await self.request("depth", params={"symbol": symbol, "limit": limit})

    async def get_klines(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> list[list]:
        """Fetch candlestick (OHLCV) data."""
        params: dict[str, Any] = {
            "symbol":   symbol,
            "interval": interval,
            "limit":    limit,
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return await self.request("klines", params=params)

    async def get_mark_price(self, symbol: str) -> dict:
        """Fetch the current mark price and funding rate for a futures symbol."""
        return await self.request("premiumIndex", params={"symbol": symbol})

    async def get_funding_rate_history(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch recent funding rate history."""
        return await self.request(
            "fundingRate", params={"symbol": symbol, "limit": limit}
        )

    async def get_account_info(self) -> dict:
        """Fetch account balance and position information (SIGNED)."""
        return await self.request("account.status", signed=True)

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """Fetch open orders, optionally filtered by symbol (SIGNED)."""
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return await self.request("openOrders.status", params=params, signed=True)

    # ── Event subscription API ───────────────────────────────────────────

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[dict], Coroutine | None],
    ) -> None:
        """
        Register a callback for incoming stream events.

        Parameters
        ----------
        event_type : str
            The ``e`` field value in stream events, e.g. ``"depthUpdate"``,
            ``"kline"``, ``"aggTrade"``.  Use ``"*"`` to receive all events.
        callback : callable
            Sync or async function accepting a single ``dict`` argument.
        """
        self._subscribers[event_type].append(callback)
        logger.debug("Subscribed to event_type=%s", event_type)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """Remove a previously registered callback."""
        self._subscribers[event_type] = [
            cb for cb in self._subscribers[event_type] if cb is not callback
        ]

    # ── Rate limit helpers ───────────────────────────────────────────────

    def get_weight_usage(self) -> Optional[tuple[int, int]]:
        """
        Return (used, limit) for REQUEST_WEIGHT:MINUTE:1 bucket,
        or None if no rate limit data has been received yet.
        """
        bucket = self._rate_limits.get("REQUEST_WEIGHT:MINUTE:1")
        return (bucket.count, bucket.limit) if bucket else None

    def is_rate_limited(self, threshold_pct: float = 80.0) -> bool:
        """
        Return True if any rate-limit bucket is above threshold_pct of its limit.
        Used by the scanner to back off before hitting hard limits.
        """
        for bucket in self._rate_limits.values():
            if bucket.limit > 0 and (bucket.count / bucket.limit) * 100 >= threshold_pct:
                return True
        return False

    # ── String representation ────────────────────────────────────────────

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return (
            f"<BinanceWebSocketManager "
            f"{'testnet' if self._testnet else 'mainnet'} "
            f"{status} "
            f"uptime={self.stats.uptime_seconds:.0f}s "
            f"req={self.stats.requests_sent}>"
        )


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class BinanceAPIError(Exception):
    """Raised when the Binance API returns a non-200 status code."""

    def __init__(self, code: int, msg: str, status: int = 400) -> None:
        self.code   = code
        self.msg    = msg
        self.status = status
        super().__init__(f"[HTTP {status}] Binance error {code}: {msg}")


class AuthenticationError(Exception):
    """Raised when a signed request is attempted without credentials."""
    pass

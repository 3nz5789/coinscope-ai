"""
market_stream.py — Binance Futures Market Data WebSocket Client
===============================================================
Connects to the Binance Futures *pub/sub stream* endpoint for real-time
market data (klines, liquidations, mark price, mini-tickers, etc.).

This is a DIFFERENT endpoint from the WebSocket API (ws-fapi/v1):

  ┌─────────────────────────────────────────────────────────────────┐
  │  Market Streams  →  wss://fstream.binance.com/stream?streams=…  │
  │  WS API          →  wss://ws-fapi.binance.com/ws-fapi/v1        │
  └─────────────────────────────────────────────────────────────────┘

Market streams push data continuously with no authentication required.
The WS API (BinanceWebSocketManager) is for signed requests (orders, account).

Stream URL patterns
-------------------
  Single stream   : {base}/ws/{streamName}
  Combined streams: {base}/stream?streams={s1}/{s2}/...

Common stream names
-------------------
  {symbol}@kline_{interval}    — candlestick  (e.g. btcusdt@kline_1m)
  {symbol}@aggTrade            — aggregated trades
  {symbol}@depth20@100ms       — order book depth (20 levels, 100ms updates)
  {symbol}@forceOrder          — liquidation orders for one symbol
  !forceOrder@arr              — all liquidations across all symbols
  {symbol}@markPrice@1s        — mark price + funding rate (1s updates)
  !miniTicker@arr              — 24h rolling stats for all symbols

Usage
-----
    from data.market_stream import BinanceFuturesStreamClient

    async def on_kline(msg: dict) -> None:
        k = msg["k"]
        if k["x"]:   # candle closed
            print(f"CLOSED {k['s']} {k['i']} close={k['c']}")

    async def on_liquidation(msg: dict) -> None:
        o = msg["o"]
        print(f"LIQUIDATION {o['s']} {o['S']} qty={o['q']} price={o['p']}")

    client = BinanceFuturesStreamClient(
        streams=["btcusdt@kline_1m", "!forceOrder@arr"],
        on_message=on_kline,
    )
    await client.start()   # runs until stopped or cancelled

Testnet vs Mainnet
------------------
    # Mainnet (default)
    client = BinanceFuturesStreamClient(streams=[...], on_message=cb)

    # Testnet
    client = BinanceFuturesStreamClient(streams=[...], on_message=cb, testnet=True)

    # Config-driven (preferred — reads TESTNET_MODE from .env)
    from config import settings
    client = BinanceFuturesStreamClient(
        streams=[...],
        on_message=cb,
        testnet=settings.testnet_mode,
    )

Notes
-----
* Max 200 streams per connection; create multiple clients for larger sets.
* Combined stream messages are wrapped: {"stream": "...", "data": {...}}
  — the client unwraps this automatically before calling on_message.
* Timestamps in stream messages are in milliseconds.
* Stream names are lowercase (btcusdt); symbol fields inside messages are
  uppercase (BTCUSDT).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Coroutine, Optional

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Endpoint constants
# ---------------------------------------------------------------------------

# Pub/sub market data stream endpoints (NOT the ws-fapi/v1 API endpoint)
STREAM_MAINNET_BASE = "wss://fstream.binance.com"
STREAM_TESTNET_BASE = "wss://stream.binancefuture.com"

# Reconnect backoff config
RECONNECT_INITIAL_S = 1
RECONNECT_MAX_S     = 60


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class BinanceFuturesStreamClient:
    """
    Resilient Binance Futures market data WebSocket client.

    Connects to the combined stream endpoint, dispatches each event to
    on_message, and auto-reconnects with exponential backoff on failure.

    Parameters
    ----------
    streams : list[str]
        Stream name(s), e.g. ["btcusdt@kline_1m", "!forceOrder@arr"].
        Up to 200 streams per client instance.
    on_message : async (or sync) callable
        Called for every incoming market event with a single dict argument.
        If the callable returns a coroutine it will be awaited.
    on_error : optional callable
        Called with the exception when a connection error occurs.
    testnet : bool
        Uses testnet base URL when True (default False — mainnet).
    ping_interval : int
        Seconds between WebSocket keep-alive pings (default 20).
    ping_timeout : int
        Seconds to wait for pong before closing (default 10).
    """

    MAX_STREAMS = 200

    def __init__(
        self,
        streams: list[str],
        on_message: Callable[[dict], Coroutine | None],
        on_error:   Optional[Callable[[Exception], Coroutine | None]] = None,
        testnet:    bool = False,
        ping_interval: int = 20,
        ping_timeout:  int = 10,
    ) -> None:
        if not streams:
            raise ValueError("streams list must not be empty")
        if len(streams) > self.MAX_STREAMS:
            raise ValueError(
                f"Max {self.MAX_STREAMS} streams per client; "
                f"got {len(streams)}. Create multiple clients."
            )

        self._streams       = streams
        self._on_message    = on_message
        self._on_error      = on_error
        self._testnet       = testnet
        self._ping_interval = ping_interval
        self._ping_timeout  = ping_timeout
        self._running       = False
        self._ws            = None

    # ── URL builder ─────────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        """
        Build the WebSocket URL.

        Single stream  → {base}/ws/{streamName}
        Multi  streams → {base}/stream?streams={s1}/{s2}/...

        Combined stream is preferred even for one stream to get consistent
        message format (wrapped with "stream" and "data" keys).
        """
        base = STREAM_TESTNET_BASE if self._testnet else STREAM_MAINNET_BASE
        combined = "/".join(self._streams)
        return f"{base}/stream?streams={combined}"

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Connect and start consuming stream events.

        Runs until stop() is called or the task is cancelled.
        Reconnects automatically with exponential backoff on any error.
        """
        self._running = True
        env = "testnet" if self._testnet else "mainnet"
        logger.info(
            "BinanceFuturesStreamClient starting [%s] | %d stream(s): %s",
            env, len(self._streams), ", ".join(self._streams[:5]),
        )

        backoff = RECONNECT_INITIAL_S

        while self._running:
            try:
                async with websockets.connect(
                    self.url,
                    ping_interval=self._ping_interval,
                    ping_timeout=self._ping_timeout,
                    close_timeout=5,
                ) as ws:
                    self._ws = ws
                    backoff  = RECONNECT_INITIAL_S   # reset on successful connect
                    logger.info("Stream connected → %s", self.url)

                    async for raw in ws:
                        if not self._running:
                            break
                        await self._dispatch(raw)

            except ConnectionClosedOK:
                if not self._running:
                    break   # intentional shutdown via stop()
                logger.warning("Stream closed cleanly — reconnecting in %ds", backoff)

            except (ConnectionClosedError, OSError, asyncio.TimeoutError) as exc:
                logger.error("Stream error: %s — reconnecting in %ds", exc, backoff)
                await self._notify_error(exc)

            except asyncio.CancelledError:
                logger.info("BinanceFuturesStreamClient cancelled — shutting down.")
                break

            except Exception as exc:
                logger.exception("Unexpected stream error: %s", exc)
                await self._notify_error(exc)

            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX_S)

        self._ws = None
        logger.info("BinanceFuturesStreamClient stopped.")

    async def stop(self) -> None:
        """Gracefully stop the stream client."""
        logger.info("Stopping BinanceFuturesStreamClient…")
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()

    # ── Message dispatch ─────────────────────────────────────────────────────

    async def _dispatch(self, raw: str) -> None:
        """
        Parse and dispatch an incoming message.

        Combined-stream messages are wrapped:
            {"stream": "btcusdt@kline_1m", "data": {...}}
        We unwrap the "data" field before passing to on_message so the
        handler always receives the raw event payload regardless of whether
        we're using a single or combined stream URL.
        """
        try:
            msg: dict = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Received non-JSON frame: %.200s", raw)
            return

        # Unwrap combined-stream envelope
        payload = msg.get("data", msg)

        try:
            result = self._on_message(payload)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.exception("on_message callback error: %s", exc)

    async def _notify_error(self, exc: Exception) -> None:
        """Call on_error callback if registered."""
        if self._on_error:
            try:
                result = self._on_error(exc)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as cb_exc:
                logger.exception("on_error callback raised: %s", cb_exc)

    # ── String repr ──────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        env    = "testnet" if self._testnet else "mainnet"
        return (
            f"<BinanceFuturesStreamClient {env} {status} "
            f"streams={len(self._streams)}>"
        )


# ---------------------------------------------------------------------------
# Multi-client manager — for > 200 streams
# ---------------------------------------------------------------------------

class BinanceFuturesMultiStreamManager:
    """
    Manages multiple BinanceFuturesStreamClient instances when the number
    of streams exceeds the 200-per-connection limit.

    All clients share the same on_message callback and testnet flag.

    Parameters
    ----------
    streams    : Full list of stream names (any length).
    on_message : Callback applied to every event across all clients.
    testnet    : Testnet flag applied to all sub-clients.

    Example
    -------
        symbols = [f"{s}@kline_1m" for s in my_250_symbols]
        manager = BinanceFuturesMultiStreamManager(
            streams=symbols,
            on_message=handle_kline,
            testnet=settings.testnet_mode,
        )
        await manager.start()   # spawns ceil(250/200) = 2 client tasks
    """

    def __init__(
        self,
        streams:    list[str],
        on_message: Callable[[dict], Coroutine | None],
        on_error:   Optional[Callable[[Exception], Coroutine | None]] = None,
        testnet:    bool = False,
    ) -> None:
        chunk_size = BinanceFuturesStreamClient.MAX_STREAMS
        self._clients = [
            BinanceFuturesStreamClient(
                streams    = streams[i : i + chunk_size],
                on_message = on_message,
                on_error   = on_error,
                testnet    = testnet,
            )
            for i in range(0, len(streams), chunk_size)
        ]
        logger.info(
            "BinanceFuturesMultiStreamManager: %d streams → %d client(s)",
            len(streams), len(self._clients),
        )

    async def start(self) -> None:
        """Start all sub-clients concurrently as asyncio tasks."""
        tasks = [asyncio.create_task(c.start()) for c in self._clients]
        await asyncio.gather(*tasks)

    async def stop(self) -> None:
        """Stop all sub-clients."""
        await asyncio.gather(*[c.stop() for c in self._clients])


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def make_kline_stream(
    symbols:  list[str],
    interval: str,
    callback: Callable[[dict], Coroutine | None],
    testnet:  bool = False,
) -> BinanceFuturesStreamClient | BinanceFuturesMultiStreamManager:
    """
    Build a kline stream client for a list of symbols.

    Returns BinanceFuturesStreamClient   if len(symbols) <= 200
    Returns BinanceFuturesMultiStreamManager otherwise.

    Parameters
    ----------
    symbols  : List of Binance symbol names (uppercase OK — lowercased internally).
    interval : Kline interval string, e.g. "1m", "5m", "1h", "4h".
    callback : Async or sync callback receiving closed-candle kline events.
    testnet  : Route to testnet stream endpoint when True.

    Example
    -------
        from config import settings

        client = make_kline_stream(
            symbols  = settings.scan_pairs,
            interval = "1h",
            callback = handle_closed_candle,
            testnet  = settings.testnet_mode,
        )
        await client.start()
    """
    streams = [f"{s.lower()}@kline_{interval}" for s in symbols]

    if len(streams) <= BinanceFuturesStreamClient.MAX_STREAMS:
        return BinanceFuturesStreamClient(
            streams    = streams,
            on_message = callback,
            testnet    = testnet,
        )
    return BinanceFuturesMultiStreamManager(
        streams    = streams,
        on_message = callback,
        testnet    = testnet,
    )

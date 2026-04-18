"""
binance_stream_adapter.py — Market Data Stream Adapter
=======================================================
Provides a unified async generator interface over WebSocket backends so
the engine can swap them via the WS_BACKEND env var:

  Backend A — native (default, no extra deps) — uses BinanceFuturesStreamClient
              Connects to wss://fstream.binance.com/stream?streams=…
  Backend B — python-binance  (AsyncClient + BinanceSocketManager)
  Backend C — unicorn-binance-websocket-api (UBWA, multi-stream buffer)

NOTE: The native backend uses BinanceFuturesStreamClient (market_stream.py),
NOT BinanceWebSocketManager.  Those are two different endpoints:
  • BinanceFuturesStreamClient  → wss://fstream.binance.com   (market data pub/sub)
  • BinanceWebSocketManager     → wss://ws-fapi.binance.com   (signed WS API)

The adapter normalises every incoming event into our internal Candle
dataclass so the rest of the engine is completely backend-agnostic.

Config (.env)
-------------
  WS_BACKEND = "native" | "python-binance" | "ubwa"

Usage
-----
    adapter = BinanceStreamAdapter()
    async for candle in adapter.stream_candles(symbols, interval="1h"):
        engine.handle_closed_candle(candle)
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator, Optional

from data.data_normalizer import Candle, DataNormalizer
from utils.logger import get_logger

logger = get_logger(__name__)

WS_BACKEND = os.environ.get("WS_BACKEND", "native").lower()


# ---------------------------------------------------------------------------
# Adapter base
# ---------------------------------------------------------------------------

class _BaseStreamAdapter:
    """Abstract base — subclasses implement stream_candles()."""

    def __init__(self) -> None:
        self._norm = DataNormalizer()

    async def stream_candles(
        self,
        symbols:  list[str],
        interval: str = "1h",
    ) -> AsyncIterator[Candle]:
        raise NotImplementedError

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Backend A — native (default, no extra dependencies)
# ---------------------------------------------------------------------------

class _NativeAdapter(_BaseStreamAdapter):
    """
    Uses BinanceFuturesStreamClient (market_stream.py).

    Connects to wss://fstream.binance.com/stream?streams=… for pub/sub
    market data.  Does NOT use BinanceWebSocketManager (ws-fapi/v1), which
    is for the signed WebSocket API (orders, account) — a separate endpoint.
    """

    def __init__(self, testnet: bool) -> None:
        super().__init__()
        self._testnet = testnet
        self._client  = None   # created per stream_candles() call

    async def stream_candles(
        self,
        symbols:  list[str],
        interval: str = "1h",
    ) -> AsyncIterator[Candle]:
        """
        Yield closed Candle objects from the Binance kline stream.

        Uses an asyncio.Queue to bridge the push-based BinanceFuturesStreamClient
        callback into an async generator interface.
        """
        from data.market_stream import BinanceFuturesStreamClient

        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        def on_kline(msg: dict) -> None:
            """Enqueue closed klines; skip open (unfinished) candles."""
            if msg.get("e") != "kline":
                return
            k = msg.get("k", {})
            if not k.get("x"):   # x=True means candle is closed
                return
            candle = self._norm.ws_kline_to_candle(msg)
            if candle:
                try:
                    queue.put_nowait(candle)
                except asyncio.QueueFull:
                    logger.warning(
                        "NativeAdapter queue full — dropping candle for %s",
                        k.get("s"),
                    )

        streams = [f"{s.lower()}@kline_{interval}" for s in symbols]
        self._client = BinanceFuturesStreamClient(
            streams    = streams,
            on_message = on_kline,
            testnet    = self._testnet,
        )

        # Run the stream client in a background task
        stream_task = asyncio.create_task(self._client.start())

        try:
            while True:
                candle = await queue.get()
                yield candle
        finally:
            await self._client.stop()
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass

    async def close(self) -> None:
        if self._client:
            await self._client.stop()


# ---------------------------------------------------------------------------
# Backend B — python-binance
# ---------------------------------------------------------------------------

class _PythonBinanceAdapter(_BaseStreamAdapter):
    """
    Uses python-binance AsyncClient + BinanceSocketManager.

    Install:  pip install python-binance
    Docs:     https://python-binance.readthedocs.io
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool) -> None:
        super().__init__()
        self._api_key    = api_key
        self._api_secret = api_secret
        self._testnet    = testnet
        self._client     = None
        self._bsm        = None

    async def _ensure_client(self):
        if self._client is None:
            try:
                from binance import AsyncClient, BinanceSocketManager
            except ImportError:
                raise ImportError(
                    "python-binance not installed. "
                    "Run: pip install python-binance"
                )
            self._client = await AsyncClient.create(
                api_key    = self._api_key,
                api_secret = self._api_secret,
                testnet    = self._testnet,
            )
            self._bsm = BinanceSocketManager(self._client, user_timeout=60)
        return self._client, self._bsm

    async def stream_candles(
        self,
        symbols:  list[str],
        interval: str = "1h",
    ) -> AsyncIterator[Candle]:
        _, bsm = await self._ensure_client()
        reconnect_delay = 2.0

        while True:
            try:
                # python-binance multiplex stream
                streams = [f"{s.lower()}@kline_{interval}" for s in symbols]
                async with bsm.multiplex_socket(streams) as stream:
                    logger.info(
                        "python-binance: streaming %d symbols @ %s",
                        len(symbols), interval,
                    )
                    while True:
                        msg = await asyncio.wait_for(stream.recv(), timeout=30)
                        if msg.get("e") == "error":
                            logger.error("python-binance stream error: %s", msg)
                            break
                        data = msg.get("data", msg)
                        if data.get("e") != "kline":
                            continue
                        kline = data["k"]
                        if not kline.get("x"):   # not yet closed
                            continue
                        candle = self._norm.ws_kline_to_candle(data)
                        if candle:
                            yield candle

                reconnect_delay = 2.0

            except asyncio.TimeoutError:
                logger.warning("python-binance stream timeout — reconnecting.")
            except Exception as exc:
                logger.warning(
                    "python-binance adapter error: %s — retry in %.0fs",
                    exc, reconnect_delay,
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

    async def close(self) -> None:
        if self._client:
            await self._client.close_connection()
            self._client = None


# ---------------------------------------------------------------------------
# Backend C — unicorn-binance-websocket-api (UBWA)
# ---------------------------------------------------------------------------

class _UBWAAdapter(_BaseStreamAdapter):
    """
    Uses unicorn-binance-websocket-api for high-throughput multi-stream.

    Install:  pip install unicorn-binance-websocket-api
    Docs:     https://unicorn-binance-websocket-api.docs.lucit.tech
    """

    def __init__(self, testnet: bool) -> None:
        super().__init__()
        self._testnet = testnet
        self._manager = None

    def _ensure_manager(self):
        if self._manager is None:
            try:
                from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager
            except ImportError:
                raise ImportError(
                    "unicorn-binance-websocket-api not installed. "
                    "Run: pip install unicorn-binance-websocket-api"
                )
            exchange = "binance.com-futures-testnet" if self._testnet else "binance.com-futures"
            self._manager = BinanceWebSocketApiManager(exchange=exchange)
        return self._manager

    async def stream_candles(
        self,
        symbols:  list[str],
        interval: str = "1h",
    ) -> AsyncIterator[Candle]:
        mgr = self._ensure_manager()

        channels = [f"kline_{interval}"]
        markets  = [s.lower() for s in symbols]

        mgr.create_stream(
            channels     = channels,
            markets      = markets,
            stream_label = "main",
            output       = "UnicornFy",
        )

        logger.info("UBWA: stream created for %d symbols @ %s.", len(symbols), interval)

        while True:
            if mgr.is_manager_stopping():
                break
            data = mgr.pop_stream_data_from_stream_buffer()
            if not data:
                await asyncio.sleep(0.01)
                continue

            # UnicornFy already normalises the event dict
            try:
                if data.get("event_type") != "kline":
                    continue
                kline = data.get("kline", {})
                if not kline.get("is_closed"):
                    continue
                candle = Candle(
                    symbol       = kline.get("symbol", "").upper(),
                    interval     = interval,
                    open_time    = int(kline.get("kline_start_time", 0)),
                    close_time   = int(kline.get("kline_close_time", 0)),
                    open         = float(kline.get("open_price", 0)),
                    high         = float(kline.get("high_price", 0)),
                    low          = float(kline.get("low_price", 0)),
                    close        = float(kline.get("close_price", 0)),
                    volume       = float(kline.get("base_volume", 0)),
                    quote_volume = float(kline.get("quote_volume", 0)),
                    trades       = int(kline.get("number_of_trades", 0)),
                    taker_buy_volume      = float(kline.get("taker_buy_base_volume", 0)),
                    taker_buy_quote       = float(kline.get("taker_buy_quote_volume", 0)),
                )
                yield candle
            except Exception as exc:
                logger.debug("UBWA event parse error: %s", exc)

    async def close(self) -> None:
        if self._manager:
            self._manager.stop_manager_with_all_streams()
            self._manager = None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def BinanceStreamAdapter(
    api_key:    str = "",
    api_secret: str = "",
    testnet:    bool = True,
    backend:    Optional[str] = None,
) -> _BaseStreamAdapter:
    """
    Return the appropriate stream adapter based on WS_BACKEND env var
    or the explicit `backend` parameter.

    Parameters
    ----------
    api_key / api_secret : Binance credentials.
    testnet              : Route to testnet endpoints.
    backend              : "native" | "python-binance" | "ubwa"
                           Falls back to WS_BACKEND env var, then "native".
    """
    chosen = (backend or WS_BACKEND).lower()

    if chosen == "python-binance":
        logger.info("Stream backend: python-binance")
        return _PythonBinanceAdapter(api_key, api_secret, testnet)

    if chosen == "ubwa":
        logger.info("Stream backend: unicorn-binance-websocket-api")
        return _UBWAAdapter(testnet)

    # Default — native uses BinanceFuturesStreamClient (fstream.binance.com),
    # not the WS API client (ws-fapi.binance.com). No credentials needed.
    logger.info("Stream backend: native (BinanceFuturesStreamClient)")
    return _NativeAdapter(testnet)

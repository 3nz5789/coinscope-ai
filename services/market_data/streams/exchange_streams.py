"""
CoinScopeAI Market Data — Multi-Exchange WebSocket Streams
=============================================================
Free, public WebSocket streams from 4 exchanges:
  - Binance Futures (testnet for orders, mainnet for public data)
  - Bybit Perpetuals
  - OKX Perpetuals
  - Deribit (BTC/ETH only)

All streams normalize data into the standard types and publish to EventBus.

Design:
  - Each exchange has its own connection manager
  - Automatic reconnection with exponential backoff
  - Heartbeat/ping management per exchange protocol
  - All public data — no API keys required
"""

import asyncio
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import websockets

from ..event_bus import Event, EventBus
from ..types import (
    FundingRate,
    Kline,
    Liquidation,
    OrderBookLevel,
    OrderBookSnapshot,
    Trade,
)

logger = logging.getLogger("coinscopeai.market_data.streams")


@dataclass
class StreamConfig:
    """Configuration for a stream connection."""
    symbols: List[str] = field(default_factory=lambda: [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    ])
    orderbook_depth: int = 20
    reconnect_max_attempts: int = 100
    reconnect_initial_delay: float = 1.0
    reconnect_max_delay: float = 60.0
    ping_interval: int = 20
    ping_timeout: int = 10


class BaseExchangeStream(ABC):
    """Base class for exchange WebSocket stream clients."""

    EXCHANGE_NAME = "unknown"

    def __init__(self, event_bus: EventBus, config: Optional[StreamConfig] = None):
        self._bus = event_bus
        self._config = config or StreamConfig()
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._reconnect_count = 0
        self._connected = False
        self._last_message_time = 0.0
        self._messages_received = 0

    def start(self):
        """Start the stream in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"stream-{self.EXCHANGE_NAME}",
        )
        self._thread.start()
        logger.info("%s stream started", self.EXCHANGE_NAME)

    def stop(self):
        """Stop the stream."""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("%s stream stopped", self.EXCHANGE_NAME)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_stats(self) -> Dict:
        return {
            "exchange": self.EXCHANGE_NAME,
            "connected": self._connected,
            "running": self._running,
            "messages_received": self._messages_received,
            "last_message_age_s": (
                time.time() - self._last_message_time
                if self._last_message_time else -1
            ),
            "reconnect_count": self._reconnect_count,
        }

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as e:
            logger.error("%s stream loop error: %s", self.EXCHANGE_NAME, e)
        finally:
            self._loop.close()

    @abstractmethod
    async def _connect(self):
        """Connect to the exchange WebSocket and process messages."""
        pass

    async def _reconnect_delay(self):
        self._reconnect_count += 1
        if self._reconnect_count > self._config.reconnect_max_attempts:
            logger.error("%s: max reconnect attempts reached", self.EXCHANGE_NAME)
            self._running = False
            return
        delay = min(
            self._config.reconnect_initial_delay * (2 ** (self._reconnect_count - 1)),
            self._config.reconnect_max_delay,
        )
        logger.info(
            "%s: reconnecting in %.1fs (attempt %d)",
            self.EXCHANGE_NAME, delay, self._reconnect_count,
        )
        await asyncio.sleep(delay)

    def _publish(self, topic: str, data: Any, source: str = ""):
        """Publish an event to the EventBus."""
        self._bus.publish(Event(
            topic=topic,
            data=data,
            source=source or self.EXCHANGE_NAME,
        ))
        self._messages_received += 1
        self._last_message_time = time.time()


# ── Binance Futures ──────────────────────────────────────────

class BinanceStream(BaseExchangeStream):
    """
    Binance Futures public WebSocket streams.
    Endpoints:
      - Combined stream: wss://fstream.binance.com/stream?streams=...
      - Trades: <symbol>@aggTrade
      - Orderbook: <symbol>@depth20@100ms
      - Klines: <symbol>@kline_<interval>
      - Liquidations: <symbol>@forceOrder
      - Mark price (funding): <symbol>@markPrice@1s
    """

    EXCHANGE_NAME = "binance"
    WS_BASE = "wss://fstream.binance.com"

    async def _connect(self):
        streams = []
        for sym in self._config.symbols:
            s = sym.lower()
            streams.extend([
                f"{s}@aggTrade",
                f"{s}@depth{self._config.orderbook_depth}@100ms",
                f"{s}@markPrice@1s",
                f"{s}@forceOrder",
                f"{s}@kline_4h",
            ])

        url = f"{self.WS_BASE}/stream?streams={'/'.join(streams)}"

        while self._running:
            try:
                logger.info("Binance: connecting to %d streams", len(streams))
                async with websockets.connect(
                    url,
                    ping_interval=self._config.ping_interval,
                    ping_timeout=self._config.ping_timeout,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._connected = True
                    self._reconnect_count = 0
                    logger.info("Binance: connected (%d streams)", len(streams))

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self._parse_binance(data)
                        except Exception as e:
                            logger.error("Binance parse error: %s", e)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("Binance disconnected: %s", e)
            except Exception as e:
                logger.error("Binance stream error: %s", e)

            self._connected = False
            if self._running:
                await self._reconnect_delay()

    def _parse_binance(self, data: Dict):
        stream_name = data.get("stream", "")
        payload = data.get("data", data)
        event_type = payload.get("e", "")

        if event_type == "aggTrade":
            trade = Trade(
                symbol=payload["s"],
                exchange="binance",
                price=float(payload["p"]),
                quantity=float(payload["q"]),
                side="sell" if payload.get("m", False) else "buy",
                timestamp=payload["T"] / 1000.0,
                trade_id=str(payload.get("a", "")),
                is_maker=payload.get("m", False),
            )
            self._publish(trade.topic, trade)

        elif event_type == "depthUpdate" or "@depth" in stream_name:
            bids = [OrderBookLevel(float(p), float(q)) for p, q in payload.get("b", payload.get("bids", []))]
            asks = [OrderBookLevel(float(p), float(q)) for p, q in payload.get("a", payload.get("asks", []))]
            # For partial depth streams, symbol is in the stream name
            symbol = payload.get("s", "")
            if not symbol and "@depth" in stream_name:
                symbol = stream_name.split("@")[0].upper()
            ob = OrderBookSnapshot(
                symbol=symbol,
                exchange="binance",
                bids=bids,
                asks=asks,
                timestamp=payload.get("E", time.time() * 1000) / 1000.0,
                sequence=payload.get("u", 0),
            )
            self._publish(ob.topic, ob)

        elif event_type == "markPriceUpdate":
            fr = FundingRate(
                symbol=payload["s"],
                exchange="binance",
                rate=float(payload.get("r", 0)),
                next_funding_time=float(payload.get("T", 0)) / 1000.0,
                timestamp=payload["E"] / 1000.0,
                mark_price=float(payload.get("p", 0)),
                index_price=float(payload.get("i", 0)),
            )
            self._publish(fr.topic, fr)

        elif event_type == "forceOrder":
            order = payload.get("o", {})
            liq = Liquidation(
                symbol=order.get("s", ""),
                exchange="binance",
                side=order.get("S", "").lower(),
                price=float(order.get("p", 0)),
                quantity=float(order.get("q", 0)),
                timestamp=order.get("T", time.time() * 1000) / 1000.0,
            )
            self._publish(liq.topic, liq)

        elif event_type == "kline":
            k = payload.get("k", {})
            kline = Kline(
                symbol=payload["s"],
                exchange="binance",
                interval=k.get("i", ""),
                open_time=k["t"] / 1000.0,
                close_time=k["T"] / 1000.0,
                open=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                is_closed=k.get("x", False),
                trades=k.get("n", 0),
            )
            self._publish(kline.topic, kline)


# ── Bybit Perpetuals ────────────────────────────────────────

class BybitStream(BaseExchangeStream):
    """
    Bybit V5 public WebSocket streams.
    Endpoint: wss://stream.bybit.com/v5/public/linear
    Topics: publicTrade, orderbook.{depth}, tickers, liquidation
    """

    EXCHANGE_NAME = "bybit"
    WS_URL = "wss://stream.bybit.com/v5/public/linear"

    async def _connect(self):
        while self._running:
            try:
                logger.info("Bybit: connecting")
                async with websockets.connect(
                    self.WS_URL,
                    ping_interval=self._config.ping_interval,
                    ping_timeout=self._config.ping_timeout,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._connected = True
                    self._reconnect_count = 0

                    # Subscribe
                    args = []
                    for sym in self._config.symbols:
                        args.extend([
                            f"publicTrade.{sym}",
                            f"orderbook.{self._config.orderbook_depth}.{sym}",
                            f"tickers.{sym}",
                            f"liquidation.{sym}",
                        ])

                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": args,
                    }))
                    logger.info("Bybit: subscribed to %d topics", len(args))

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self._parse_bybit(data)
                        except Exception as e:
                            logger.error("Bybit parse error: %s", e)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("Bybit disconnected: %s", e)
            except Exception as e:
                logger.error("Bybit stream error: %s", e)

            self._connected = False
            if self._running:
                await self._reconnect_delay()

    def _parse_bybit(self, data: Dict):
        topic = data.get("topic", "")
        payload = data.get("data", {})

        if not topic:
            return

        if topic.startswith("publicTrade."):
            trades = payload if isinstance(payload, list) else [payload]
            for t in trades:
                trade = Trade(
                    symbol=t.get("s", ""),
                    exchange="bybit",
                    price=float(t.get("p", 0)),
                    quantity=float(t.get("v", 0)),
                    side=t.get("S", "Buy").lower(),
                    timestamp=float(t.get("T", 0)) / 1000.0,
                    trade_id=str(t.get("i", "")),
                )
                self._publish(trade.topic, trade)

        elif topic.startswith("orderbook."):
            symbol = topic.split(".")[-1]
            ob_type = data.get("type", "")
            bids = [OrderBookLevel(float(p), float(q)) for p, q in payload.get("b", [])]
            asks = [OrderBookLevel(float(p), float(q)) for p, q in payload.get("a", [])]
            ob = OrderBookSnapshot(
                symbol=symbol,
                exchange="bybit",
                bids=bids,
                asks=asks,
                timestamp=float(data.get("ts", 0)) / 1000.0,
                sequence=payload.get("u", 0),
            )
            self._publish(ob.topic, ob)

        elif topic.startswith("tickers."):
            # Extract funding rate from ticker
            symbol = topic.split(".")[-1]
            rate = payload.get("fundingRate")
            if rate is not None:
                fr = FundingRate(
                    symbol=symbol,
                    exchange="bybit",
                    rate=float(rate),
                    next_funding_time=float(payload.get("nextFundingTime", 0)) / 1000.0,
                    timestamp=float(data.get("ts", 0)) / 1000.0,
                    mark_price=float(payload.get("markPrice", 0)),
                    index_price=float(payload.get("indexPrice", 0)),
                )
                self._publish(fr.topic, fr)

        elif topic.startswith("liquidation."):
            liq = Liquidation(
                symbol=payload.get("symbol", ""),
                exchange="bybit",
                side=payload.get("side", "Buy").lower(),
                price=float(payload.get("price", 0)),
                quantity=float(payload.get("size", 0)),
                timestamp=float(payload.get("updatedTime", 0)) / 1000.0,
            )
            self._publish(liq.topic, liq)


# ── OKX Perpetuals ──────────────────────────────────────────

class OKXStream(BaseExchangeStream):
    """
    OKX public WebSocket streams.
    Endpoint: wss://ws.okx.com:8443/ws/v5/public
    Channels: trades, books5/books, funding-rate, liquidation-orders
    """

    EXCHANGE_NAME = "okx"
    WS_URL = "wss://ws.okx.com:8443/ws/v5/public"

    # OKX uses different symbol format: BTC-USDT-SWAP
    SYMBOL_MAP = {
        "BTCUSDT": "BTC-USDT-SWAP",
        "ETHUSDT": "ETH-USDT-SWAP",
        "SOLUSDT": "SOL-USDT-SWAP",
        "BNBUSDT": "BNB-USDT-SWAP",  # May not be available
        "XRPUSDT": "XRP-USDT-SWAP",
    }
    REVERSE_MAP = {v: k for k, v in SYMBOL_MAP.items()}

    async def _connect(self):
        while self._running:
            try:
                logger.info("OKX: connecting")
                async with websockets.connect(
                    self.WS_URL,
                    ping_interval=self._config.ping_interval,
                    ping_timeout=self._config.ping_timeout,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._connected = True
                    self._reconnect_count = 0

                    # Subscribe
                    args = []
                    for sym in self._config.symbols:
                        okx_sym = self.SYMBOL_MAP.get(sym)
                        if not okx_sym:
                            continue
                        args.extend([
                            {"channel": "trades", "instId": okx_sym},
                            {"channel": "books5", "instId": okx_sym},
                            {"channel": "funding-rate", "instId": okx_sym},
                            {"channel": "liquidation-orders", "instType": "SWAP"},
                        ])

                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": args,
                    }))
                    logger.info("OKX: subscribed to %d channels", len(args))

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self._parse_okx(data)
                        except Exception as e:
                            logger.error("OKX parse error: %s", e)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("OKX disconnected: %s", e)
            except Exception as e:
                logger.error("OKX stream error: %s", e)

            self._connected = False
            if self._running:
                await self._reconnect_delay()

    def _parse_okx(self, data: Dict):
        arg = data.get("arg", {})
        channel = arg.get("channel", "")
        records = data.get("data", [])

        if not records:
            return

        inst_id = arg.get("instId", "")
        symbol = self.REVERSE_MAP.get(inst_id, inst_id.replace("-SWAP", "").replace("-", ""))

        if channel == "trades":
            for t in records:
                trade = Trade(
                    symbol=symbol,
                    exchange="okx",
                    price=float(t.get("px", 0)),
                    quantity=float(t.get("sz", 0)),
                    side=t.get("side", "buy").lower(),
                    timestamp=float(t.get("ts", 0)) / 1000.0,
                    trade_id=str(t.get("tradeId", "")),
                )
                self._publish(trade.topic, trade)

        elif channel == "books5":
            for snap in records:
                bids = [OrderBookLevel(float(p), float(q)) for p, q, _, _ in snap.get("bids", [])]
                asks = [OrderBookLevel(float(p), float(q)) for p, q, _, _ in snap.get("asks", [])]
                ob = OrderBookSnapshot(
                    symbol=symbol,
                    exchange="okx",
                    bids=bids,
                    asks=asks,
                    timestamp=float(snap.get("ts", 0)) / 1000.0,
                )
                self._publish(ob.topic, ob)

        elif channel == "funding-rate":
            for fr_data in records:
                fr = FundingRate(
                    symbol=symbol,
                    exchange="okx",
                    rate=float(fr_data.get("fundingRate", 0)),
                    next_funding_time=float(fr_data.get("nextFundingTime", 0)) / 1000.0,
                    timestamp=float(fr_data.get("ts", 0)) / 1000.0,
                )
                self._publish(fr.topic, fr)

        elif channel == "liquidation-orders":
            for liq_data in records:
                details = liq_data.get("details", [{}])
                for d in details:
                    inst = liq_data.get("instId", "")
                    liq_symbol = self.REVERSE_MAP.get(inst, inst.replace("-SWAP", "").replace("-", ""))
                    liq = Liquidation(
                        symbol=liq_symbol,
                        exchange="okx",
                        side=d.get("side", "buy").lower(),
                        price=float(d.get("bkPx", 0)),
                        quantity=float(d.get("sz", 0)),
                        timestamp=float(d.get("ts", 0)) / 1000.0,
                    )
                    self._publish(liq.topic, liq)


# ── Deribit ─────────────────────────────────────────────────

class DeribitStream(BaseExchangeStream):
    """
    Deribit public WebSocket streams (BTC and ETH only).
    Endpoint: wss://www.deribit.com/ws/api/v2
    Channels: trades, book, ticker (for funding)
    """

    EXCHANGE_NAME = "deribit"
    WS_URL = "wss://www.deribit.com/ws/api/v2"

    # Deribit perpetuals use different naming
    SYMBOL_MAP = {
        "BTCUSDT": "BTC-PERPETUAL",
        "ETHUSDT": "ETH-PERPETUAL",
    }
    REVERSE_MAP = {v: k for k, v in SYMBOL_MAP.items()}

    async def _connect(self):
        # Deribit only supports BTC and ETH perpetuals
        supported = [s for s in self._config.symbols if s in self.SYMBOL_MAP]
        if not supported:
            logger.info("Deribit: no supported symbols, skipping")
            return

        while self._running:
            try:
                logger.info("Deribit: connecting")
                async with websockets.connect(
                    self.WS_URL,
                    ping_interval=self._config.ping_interval,
                    ping_timeout=self._config.ping_timeout,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._connected = True
                    self._reconnect_count = 0

                    # Subscribe via JSON-RPC
                    channels = []
                    for sym in supported:
                        deribit_sym = self.SYMBOL_MAP[sym]
                        channels.extend([
                            f"trades.{deribit_sym}.raw",
                            f"book.{deribit_sym}.none.20.100ms",
                            f"ticker.{deribit_sym}.raw",
                        ])

                    await ws.send(json.dumps({
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "public/subscribe",
                        "params": {"channels": channels},
                    }))
                    logger.info("Deribit: subscribed to %d channels", len(channels))

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            self._parse_deribit(data)
                        except Exception as e:
                            logger.error("Deribit parse error: %s", e)

            except websockets.exceptions.ConnectionClosed as e:
                logger.warning("Deribit disconnected: %s", e)
            except Exception as e:
                logger.error("Deribit stream error: %s", e)

            self._connected = False
            if self._running:
                await self._reconnect_delay()

    def _parse_deribit(self, data: Dict):
        params = data.get("params", {})
        channel = params.get("channel", "")
        payload = params.get("data", {})

        if not channel or not payload:
            return

        if channel.startswith("trades."):
            trades = payload if isinstance(payload, list) else [payload]
            for t in trades:
                inst = t.get("instrument_name", "")
                symbol = self.REVERSE_MAP.get(inst, "BTCUSDT")
                trade = Trade(
                    symbol=symbol,
                    exchange="deribit",
                    price=float(t.get("price", 0)),
                    quantity=float(t.get("amount", 0)),
                    side=t.get("direction", "buy").lower(),
                    timestamp=float(t.get("timestamp", 0)) / 1000.0,
                    trade_id=str(t.get("trade_id", "")),
                )
                self._publish(trade.topic, trade)

        elif channel.startswith("book."):
            inst = channel.split(".")[1]
            symbol = self.REVERSE_MAP.get(inst, "BTCUSDT")
            bids = [OrderBookLevel(float(p), float(q)) for _, p, q in payload.get("bids", [])]
            asks = [OrderBookLevel(float(p), float(q)) for _, p, q in payload.get("asks", [])]
            ob = OrderBookSnapshot(
                symbol=symbol,
                exchange="deribit",
                bids=bids,
                asks=asks,
                timestamp=float(payload.get("timestamp", 0)) / 1000.0,
            )
            self._publish(ob.topic, ob)

        elif channel.startswith("ticker."):
            inst = channel.split(".")[1]
            symbol = self.REVERSE_MAP.get(inst, "BTCUSDT")
            fr = FundingRate(
                symbol=symbol,
                exchange="deribit",
                rate=float(payload.get("current_funding", 0)),
                next_funding_time=0.0,
                timestamp=float(payload.get("timestamp", 0)) / 1000.0,
                mark_price=float(payload.get("mark_price", 0)),
                index_price=float(payload.get("index_price", 0)),
            )
            self._publish(fr.topic, fr)


# ── Stream Manager ──────────────────────────────────────────

class StreamManager:
    """
    Manages all exchange stream connections.
    Provides a single interface to start/stop all streams.
    """

    def __init__(self, event_bus: EventBus, config: Optional[StreamConfig] = None):
        self._bus = event_bus
        self._config = config or StreamConfig()
        self._streams: Dict[str, BaseExchangeStream] = {}

        # Initialize all exchange streams
        self._streams["binance"] = BinanceStream(event_bus, self._config)
        self._streams["bybit"] = BybitStream(event_bus, self._config)
        self._streams["okx"] = OKXStream(event_bus, self._config)
        self._streams["deribit"] = DeribitStream(event_bus, self._config)

    def start(self, exchanges: Optional[List[str]] = None):
        """Start streams for specified exchanges (or all)."""
        targets = exchanges or list(self._streams.keys())
        for name in targets:
            stream = self._streams.get(name)
            if stream:
                stream.start()
                logger.info("Started %s stream", name)

    def stop(self):
        """Stop all streams."""
        for name, stream in self._streams.items():
            stream.stop()
            logger.info("Stopped %s stream", name)

    def get_stats(self) -> Dict:
        """Get stats for all streams."""
        return {
            name: stream.get_stats()
            for name, stream in self._streams.items()
        }

    def get_stream(self, exchange: str) -> Optional[BaseExchangeStream]:
        return self._streams.get(exchange)

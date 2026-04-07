"""
Unified Tick Trade Stream — aggregates real-time trades from
Binance, Bybit, OKX, and Hyperliquid via free public WebSocket feeds.

All trades are normalised into the `Trade` model and published to the EventBus.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

from .base import (
    BaseStream,
    EventBus,
    EventType,
    Exchange,
    Trade,
    normalize_symbol,
    now_ms,
    to_binance_symbol,
    to_bybit_symbol,
    to_hyperliquid_coin,
    to_okx_symbol,
)

logger = logging.getLogger("coinscopeai.streams.trades")


class TradeStream(BaseStream):
    """
    Unified trade stream across 4 exchanges.

    Usage::

        stream = TradeStream(["BTCUSDT", "ETHUSDT"])
        await stream.start()
        # ... trades are published to EventBus as EventType.TRADE
        await stream.stop()
    """

    def _create_tasks(self) -> List[asyncio.Task]:
        tasks: List[asyncio.Task] = []
        for symbol in self.symbols:
            for exchange in self.exchanges:
                if exchange == Exchange.BINANCE:
                    tasks.append(asyncio.create_task(self._binance_trades(symbol)))
                elif exchange == Exchange.BYBIT:
                    tasks.append(asyncio.create_task(self._bybit_trades(symbol)))
                elif exchange == Exchange.OKX:
                    tasks.append(asyncio.create_task(self._okx_trades(symbol)))
                elif exchange == Exchange.HYPERLIQUID:
                    tasks.append(asyncio.create_task(self._hyperliquid_trades(symbol)))
        return tasks

    # ------------------------------------------------------------------
    # Binance: wss://fstream.binance.com/ws/<symbol>@aggTrade
    # ------------------------------------------------------------------
    async def _binance_trades(self, symbol: str) -> None:
        ws_symbol = to_binance_symbol(symbol)
        url = f"wss://fstream.binance.com/ws/{ws_symbol}@aggTrade"

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict) or data.get("e") != "aggTrade":
                return
            trade = Trade(
                exchange=Exchange.BINANCE.value,
                symbol=normalize_symbol(data["s"]),
                trade_id=str(data["a"]),
                price=float(data["p"]),
                quantity=float(data["q"]),
                side="sell" if data.get("m") else "buy",  # m=True → maker was buyer → trade is sell
                timestamp_ms=int(data["T"]),
                received_ms=now_ms(),
                raw=data,
            )
            await self.bus.publish(EventType.TRADE, trade)

        await self._ws_connect_loop(
            url, on_msg, Exchange.BINANCE, symbol, stream_type="aggTrade",
        )

    # ------------------------------------------------------------------
    # Bybit: WebSocket publicTrade.<symbol>
    # ------------------------------------------------------------------
    async def _bybit_trades(self, symbol: str) -> None:
        url = "wss://stream.bybit.com/v5/public/linear"
        bybit_sym = to_bybit_symbol(symbol)
        sub = {
            "op": "subscribe",
            "args": [f"publicTrade.{bybit_sym}"],
        }

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            topic = data.get("topic", "")
            if not topic.startswith("publicTrade."):
                return
            for item in data.get("data", []):
                trade = Trade(
                    exchange=Exchange.BYBIT.value,
                    symbol=normalize_symbol(item.get("s", symbol)),
                    trade_id=str(item.get("i", "")),
                    price=float(item["p"]),
                    quantity=float(item["v"]),
                    side=item.get("S", "Buy").lower(),
                    timestamp_ms=int(item.get("T", now_ms())),
                    received_ms=now_ms(),
                    raw=item,
                )
                # Bybit side: "Buy" or "Sell"
                if trade.side not in ("buy", "sell"):
                    trade.side = "buy" if trade.side.startswith("b") else "sell"
                await self.bus.publish(EventType.TRADE, trade)

        await self._ws_connect_loop(
            url, on_msg, Exchange.BYBIT, symbol,
            subscribe_msg=sub, stream_type="publicTrade",
        )

    # ------------------------------------------------------------------
    # OKX: WebSocket trades channel
    # ------------------------------------------------------------------
    async def _okx_trades(self, symbol: str) -> None:
        url = "wss://ws.okx.com:8443/ws/v5/public"
        okx_inst = to_okx_symbol(symbol)
        sub = {
            "op": "subscribe",
            "args": [{"channel": "trades", "instId": okx_inst}],
        }

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            # OKX sends {"arg":...,"data":[...]}
            if "data" not in data:
                return
            for item in data["data"]:
                side_raw = item.get("side", "buy").lower()
                trade = Trade(
                    exchange=Exchange.OKX.value,
                    symbol=normalize_symbol(symbol),
                    trade_id=str(item.get("tradeId", "")),
                    price=float(item["px"]),
                    quantity=float(item["sz"]),
                    side=side_raw,
                    timestamp_ms=int(item.get("ts", now_ms())),
                    received_ms=now_ms(),
                    raw=item,
                )
                await self.bus.publish(EventType.TRADE, trade)

        await self._ws_connect_loop(
            url, on_msg, Exchange.OKX, symbol,
            subscribe_msg=sub, stream_type="trades",
        )

    # ------------------------------------------------------------------
    # Hyperliquid: WebSocket trades subscription
    # ------------------------------------------------------------------
    async def _hyperliquid_trades(self, symbol: str) -> None:
        url = "wss://api.hyperliquid.xyz/ws"
        coin = to_hyperliquid_coin(symbol)
        sub = {
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": coin},
        }

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            channel = data.get("channel")
            if channel != "trades":
                return
            items = data.get("data", [])
            if not isinstance(items, list):
                items = [items]
            for item in items:
                side_raw = item.get("side", "B")
                side = "buy" if side_raw.upper().startswith("B") else "sell"
                ts = item.get("time", now_ms())
                if isinstance(ts, str):
                    ts = int(ts)
                trade = Trade(
                    exchange=Exchange.HYPERLIQUID.value,
                    symbol=normalize_symbol(symbol),
                    trade_id=str(item.get("tid", "")),
                    price=float(item.get("px", 0)),
                    quantity=float(item.get("sz", 0)),
                    side=side,
                    timestamp_ms=ts,
                    received_ms=now_ms(),
                    raw=item,
                )
                await self.bus.publish(EventType.TRADE, trade)

        await self._ws_connect_loop(
            url, on_msg, Exchange.HYPERLIQUID, symbol,
            subscribe_msg=sub, stream_type="trades",
        )

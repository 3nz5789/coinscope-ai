"""
Unified Liquidation Stream — real-time liquidation events from
Binance, Bybit, OKX, and Hyperliquid via free public endpoints.

Approach per exchange:
- Binance: WebSocket forceOrder stream (real-time)
- Bybit: WebSocket liquidation stream (real-time)
- OKX: REST polling /api/v5/public/liquidation-orders every 5-10s (no WS feed)
- Hyperliquid: Derived from trade stream — large market orders above threshold
  flagged as potential liquidations (is_derived=True)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .base import (
    BaseStream,
    EventBus,
    EventType,
    Exchange,
    Liquidation,
    Trade,
    normalize_symbol,
    now_ms,
    to_binance_symbol,
    to_bybit_symbol,
    to_hyperliquid_coin,
    to_okx_symbol,
)

logger = logging.getLogger("coinscopeai.streams.liquidation")


class LiquidationStream(BaseStream):
    """
    Unified liquidation stream across 4 exchanges.

    For OKX: polls REST endpoint every poll_interval seconds.
    For Hyperliquid: subscribes to trades and flags large orders as potential liquidations.
    """

    def __init__(
        self,
        symbols: List[str],
        exchanges: Optional[List[Exchange]] = None,
        event_bus: Optional[EventBus] = None,
        okx_poll_interval: float = 5.0,
        hl_liq_threshold_usd: float = 50_000.0,
    ):
        super().__init__(symbols, exchanges, event_bus)
        self.okx_poll_interval = okx_poll_interval
        self.hl_liq_threshold_usd = hl_liq_threshold_usd
        self._seen_okx_ids: Dict[str, set] = {}  # dedup for OKX polling

    def _create_tasks(self) -> List[asyncio.Task]:
        tasks: List[asyncio.Task] = []
        for symbol in self.symbols:
            for exchange in self.exchanges:
                if exchange == Exchange.BINANCE:
                    tasks.append(asyncio.create_task(self._binance_liquidations(symbol)))
                elif exchange == Exchange.BYBIT:
                    tasks.append(asyncio.create_task(self._bybit_liquidations(symbol)))
                elif exchange == Exchange.OKX:
                    tasks.append(asyncio.create_task(self._okx_liquidations(symbol)))
                elif exchange == Exchange.HYPERLIQUID:
                    tasks.append(asyncio.create_task(self._hyperliquid_liquidations(symbol)))
        return tasks

    # ------------------------------------------------------------------
    # Binance: wss://fstream.binance.com/ws/<symbol>@forceOrder
    # ------------------------------------------------------------------
    async def _binance_liquidations(self, symbol: str) -> None:
        ws_sym = to_binance_symbol(symbol)
        url = f"wss://fstream.binance.com/ws/{ws_sym}@forceOrder"

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            if data.get("e") != "forceOrder":
                return
            order = data.get("o", {})
            price = float(order.get("p", 0))
            qty = float(order.get("q", 0))
            side_raw = order.get("S", "BUY").upper()
            # forceOrder side: BUY means short was liquidated, SELL means long was liquidated
            side = "sell" if side_raw == "BUY" else "buy"
            liq = Liquidation(
                exchange=Exchange.BINANCE.value,
                symbol=normalize_symbol(order.get("s", symbol)),
                side=side,
                price=price,
                quantity=qty,
                usd_value=price * qty,
                timestamp_ms=int(order.get("T", now_ms())),
                received_ms=now_ms(),
            )
            await self.bus.publish(EventType.LIQUIDATION, liq)

        await self._ws_connect_loop(
            url, on_msg, Exchange.BINANCE, symbol, stream_type="forceOrder",
        )

    # ------------------------------------------------------------------
    # Bybit: WebSocket liquidation.<symbol>
    # ------------------------------------------------------------------
    async def _bybit_liquidations(self, symbol: str) -> None:
        url = "wss://stream.bybit.com/v5/public/linear"
        bybit_sym = to_bybit_symbol(symbol)
        sub = {
            "op": "subscribe",
            "args": [f"liquidation.{bybit_sym}"],
        }

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            topic = data.get("topic", "")
            if not topic.startswith("liquidation."):
                return
            item = data.get("data", {})
            price = float(item.get("price", 0))
            qty = float(item.get("size", 0))
            side_raw = item.get("side", "Buy")
            # Bybit: side is the liquidation order side
            side = side_raw.lower()
            if side not in ("buy", "sell"):
                side = "buy" if side.startswith("b") else "sell"
            liq = Liquidation(
                exchange=Exchange.BYBIT.value,
                symbol=normalize_symbol(item.get("symbol", symbol)),
                side=side,
                price=price,
                quantity=qty,
                usd_value=price * qty,
                timestamp_ms=int(item.get("updatedTime", now_ms())),
                received_ms=now_ms(),
            )
            await self.bus.publish(EventType.LIQUIDATION, liq)

        await self._ws_connect_loop(
            url, on_msg, Exchange.BYBIT, symbol,
            subscribe_msg=sub, stream_type="liquidation",
        )

    # ------------------------------------------------------------------
    # OKX: REST polling /api/v5/public/liquidation-orders
    # ------------------------------------------------------------------
    async def _okx_liquidations(self, symbol: str) -> None:
        okx_inst = to_okx_symbol(symbol)
        seen_key = f"okx:{symbol}"
        self._seen_okx_ids[seen_key] = set()

        while self._running:
            try:
                data = await self._rest_get(
                    "https://www.okx.com/api/v5/public/liquidation-orders",
                    Exchange.OKX,
                    params={
                        "instType": "SWAP",
                        "instId": okx_inst,
                        "state": "filled",
                        "limit": "100",
                    },
                )
                items = data.get("data", [])
                for entry in items:
                    details = entry.get("details", [])
                    for detail in details:
                        detail_id = detail.get("ts", "") + detail.get("bkPx", "")
                        if detail_id in self._seen_okx_ids[seen_key]:
                            continue
                        self._seen_okx_ids[seen_key].add(detail_id)
                        # Trim seen set to prevent memory growth
                        if len(self._seen_okx_ids[seen_key]) > 5000:
                            self._seen_okx_ids[seen_key] = set(
                                list(self._seen_okx_ids[seen_key])[-2500:]
                            )
                        price = float(detail.get("bkPx", 0))
                        qty = float(detail.get("sz", 0))
                        side_raw = detail.get("side", "buy").lower()
                        ts = int(detail.get("ts", now_ms()))
                        liq = Liquidation(
                            exchange=Exchange.OKX.value,
                            symbol=normalize_symbol(symbol),
                            side=side_raw,
                            price=price,
                            quantity=qty,
                            usd_value=price * qty,
                            timestamp_ms=ts,
                            received_ms=now_ms(),
                        )
                        await self.bus.publish(EventType.LIQUIDATION, liq)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("OKX liquidation poll error for %s: %s", symbol, exc)
            await asyncio.sleep(self.okx_poll_interval)

    # ------------------------------------------------------------------
    # Hyperliquid: Derived from trade stream (large market orders)
    # ------------------------------------------------------------------
    async def _hyperliquid_liquidations(self, symbol: str) -> None:
        """
        Subscribe to Hyperliquid trades via WebSocket and flag
        large market orders (> threshold USD) as potential liquidations.
        """
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
                price = float(item.get("px", 0))
                qty = float(item.get("sz", 0))
                usd_value = price * qty
                if usd_value < self.hl_liq_threshold_usd:
                    continue
                side_raw = item.get("side", "B")
                side = "buy" if side_raw.upper().startswith("B") else "sell"
                ts = item.get("time", now_ms())
                if isinstance(ts, str):
                    ts = int(ts)
                liq = Liquidation(
                    exchange=Exchange.HYPERLIQUID.value,
                    symbol=normalize_symbol(symbol),
                    side=side,
                    price=price,
                    quantity=qty,
                    usd_value=usd_value,
                    timestamp_ms=ts,
                    received_ms=now_ms(),
                    is_derived=True,
                )
                await self.bus.publish(EventType.LIQUIDATION, liq)

        await self._ws_connect_loop(
            url, on_msg, Exchange.HYPERLIQUID, symbol,
            subscribe_msg=sub, stream_type="liquidation-derived",
        )

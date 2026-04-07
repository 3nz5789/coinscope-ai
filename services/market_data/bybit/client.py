"""
CoinScopeAI — Bybit Client

WebSocket streams (V5 public):
  - orderbook.1 (best bid/ask) or orderbook.50 (top 50 levels)
  - publicTrade

REST polling:
  - Open Interest  (GET /v5/market/open-interest)
  - Funding History (GET /v5/market/funding/history)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from ..base import BaseExchangeClient, EventBus
from ..models import (
    EventType,
    Exchange,
    FundingRate,
    MarkPrice,
    OpenInterest,
    OrderBook,
    OrderBookLevel,
    Side,
    Trade,
)

logger = logging.getLogger("coinscopeai.market_data.bybit")


class BybitClient(BaseExchangeClient):
    """Bybit V5 linear perpetual public data client."""

    EXCHANGE = Exchange.BYBIT
    WS_BASE_URL = "wss://stream.bybit.com/v5/public/linear"
    REST_BASE_URL = "https://api.bybit.com"

    OI_POLL_INTERVAL = 15.0
    FUNDING_POLL_INTERVAL = 60.0

    def __init__(
        self,
        symbols: List[str],
        event_bus: Optional[EventBus] = None,
        rest_rate_limit: int = 10,
        rest_rate_period: float = 1.0,
        orderbook_depth: int = 1,
        oi_poll_interval: float = 15.0,
        funding_poll_interval: float = 60.0,
        use_testnet: bool = False,
    ) -> None:
        super().__init__(symbols, event_bus, rest_rate_limit, rest_rate_period)
        self.orderbook_depth = orderbook_depth  # 1 or 50
        self.oi_poll_interval = oi_poll_interval
        self.funding_poll_interval = funding_poll_interval
        if use_testnet:
            self.WS_BASE_URL = "wss://stream-testnet.bybit.com/v5/public/linear"
            self.REST_BASE_URL = "https://api-testnet.bybit.com"

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def _create_ws_tasks(self) -> List[asyncio.Task]:
        subscribe_msg = {
            "op": "subscribe",
            "args": [],
        }
        for sym in self.symbols:
            subscribe_msg["args"].append(f"orderbook.{self.orderbook_depth}.{sym}")
            subscribe_msg["args"].append(f"publicTrade.{sym}")

        task = asyncio.create_task(
            self._ws_connect_loop(
                self.WS_BASE_URL,
                self._handle_message,
                subscribe_msg=subscribe_msg,
                label="combined",
            ),
            name="bybit-ws-combined",
        )
        return [task]

    def _create_rest_tasks(self) -> List[asyncio.Task]:
        return [
            asyncio.create_task(
                self._rest_poll_loop("open_interest", self.oi_poll_interval, self._poll_open_interest),
                name="bybit-rest-oi",
            ),
            asyncio.create_task(
                self._rest_poll_loop("funding_rate", self.funding_poll_interval, self._poll_funding_rate),
                name="bybit-rest-funding",
            ),
        ]

    # ------------------------------------------------------------------
    # WebSocket message handlers
    # ------------------------------------------------------------------

    async def _handle_message(self, raw: str) -> None:
        data = json.loads(raw)

        # Bybit sends pong / subscription confirmations
        if data.get("op") or data.get("success") is not None:
            logger.debug("[bybit] Control message: %s", raw[:200])
            return

        topic = data.get("topic", "")
        payload = data.get("data", {})
        ts = float(data.get("ts", time.time() * 1000)) / 1000.0

        if topic.startswith("orderbook"):
            await self._process_orderbook(data, ts)
        elif topic.startswith("publicTrade"):
            await self._process_trades(payload, ts)

    async def _process_orderbook(self, data: Dict[str, Any], ts: float) -> None:
        topic = data.get("topic", "")
        parts = topic.split(".")
        symbol = parts[-1] if len(parts) >= 3 else ""
        book_data = data.get("data", {})

        bids = [OrderBookLevel(price=float(b[0]), quantity=float(b[1])) for b in book_data.get("b", [])]
        asks = [OrderBookLevel(price=float(a[0]), quantity=float(a[1])) for a in book_data.get("a", [])]

        ob = OrderBook(
            exchange=Exchange.BYBIT,
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=ts,
            sequence=book_data.get("u"),
            raw=data,
        )
        await self._publish(EventType.ORDER_BOOK, ob, symbol)

    async def _process_trades(self, trades: Any, ts: float) -> None:
        if not isinstance(trades, list):
            trades = [trades]
        for t in trades:
            symbol = t.get("s", "")
            trade = Trade(
                exchange=Exchange.BYBIT,
                symbol=symbol,
                trade_id=str(t.get("i", "")),
                price=float(t.get("p", 0)),
                quantity=float(t.get("v", 0)),
                side=Side.BUY if t.get("S") == "Buy" else Side.SELL,
                timestamp=float(t.get("T", ts * 1000)) / 1000.0,
                raw=t,
            )
            await self._publish(EventType.TRADE, trade, symbol)

    # ------------------------------------------------------------------
    # REST polling
    # ------------------------------------------------------------------

    async def _poll_open_interest(self) -> None:
        for symbol in self.symbols:
            url = f"{self.REST_BASE_URL}/v5/market/open-interest"
            params = {"category": "linear", "symbol": symbol, "intervalTime": "5min", "limit": "1"}
            resp = await self._rest_get(url, params=params)
            items = resp.get("result", {}).get("list", [])
            if items:
                item = items[0]
                oi = OpenInterest(
                    exchange=Exchange.BYBIT,
                    symbol=symbol,
                    open_interest=float(item.get("openInterest", 0)),
                    timestamp=float(item.get("timestamp", time.time() * 1000)) / 1000.0,
                    raw=item,
                )
                await self._publish(EventType.OPEN_INTEREST, oi, symbol)

    async def _poll_funding_rate(self) -> None:
        for symbol in self.symbols:
            url = f"{self.REST_BASE_URL}/v5/market/funding/history"
            params = {"category": "linear", "symbol": symbol, "limit": "1"}
            resp = await self._rest_get(url, params=params)
            items = resp.get("result", {}).get("list", [])
            if items:
                item = items[0]
                fr = FundingRate(
                    exchange=Exchange.BYBIT,
                    symbol=symbol,
                    funding_rate=float(item.get("fundingRate", 0)),
                    timestamp=float(item.get("fundingRateTimestamp", time.time() * 1000)) / 1000.0,
                    raw=item,
                )
                await self._publish(EventType.FUNDING_RATE, fr, symbol)

"""
CoinScopeAI — OKX Client

WebSocket streams (public):
  - books5 (order book top 5)
  - tickers
  - mark-price
  - funding-rate
  - open-interest

All streams are WebSocket-based on OKX; no REST polling needed for the
channels above, but we keep the REST fallback for resilience.
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
    Ticker,
    Trade,
)

logger = logging.getLogger("coinscopeai.market_data.okx")


def _inst_id(symbol: str) -> str:
    """Convert unified symbol like BTCUSDT to OKX instId like BTC-USDT-SWAP."""
    # Simple heuristic: strip USDT suffix and build swap id
    base = symbol.replace("USDT", "")
    return f"{base}-USDT-SWAP"


def _symbol_from_inst(inst_id: str) -> str:
    """Convert OKX instId like BTC-USDT-SWAP back to unified BTCUSDT."""
    parts = inst_id.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}{parts[1]}"
    return inst_id


class OKXClient(BaseExchangeClient):
    """OKX perpetual swap public data client."""

    EXCHANGE = Exchange.OKX
    WS_BASE_URL = "wss://ws.okx.com:8443/ws/v5/public"
    REST_BASE_URL = "https://www.okx.com"

    def __init__(
        self,
        symbols: List[str],
        event_bus: Optional[EventBus] = None,
        rest_rate_limit: int = 10,
        rest_rate_period: float = 1.0,
        use_demo: bool = False,
    ) -> None:
        super().__init__(symbols, event_bus, rest_rate_limit, rest_rate_period)
        if use_demo:
            self.WS_BASE_URL = "wss://wspap.okx.com:8443/ws/v5/public?brokerId=9999"

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def _create_ws_tasks(self) -> List[asyncio.Task]:
        # OKX allows subscribing to multiple channels in one connection
        subscribe_msg = {"op": "subscribe", "args": []}
        for sym in self.symbols:
            inst = _inst_id(sym)
            subscribe_msg["args"].extend([
                {"channel": "books5", "instId": inst},
                {"channel": "tickers", "instId": inst},
                {"channel": "mark-price", "instId": inst},
                {"channel": "funding-rate", "instId": inst},
                {"channel": "open-interest", "instId": inst},
            ])

        task = asyncio.create_task(
            self._ws_connect_loop(
                self.WS_BASE_URL,
                self._handle_message,
                subscribe_msg=subscribe_msg,
                label="combined",
            ),
            name="okx-ws-combined",
        )
        return [task]

    def _create_rest_tasks(self) -> List[asyncio.Task]:
        # OKX streams cover all needed data; REST tasks kept empty but
        # could be added for resilience fallback.
        return []

    # ------------------------------------------------------------------
    # WebSocket message handlers
    # ------------------------------------------------------------------

    async def _handle_message(self, raw: str) -> None:
        data = json.loads(raw)

        # Subscription confirmations / pong
        if "event" in data:
            logger.debug("[okx] Control: %s", raw[:200])
            return

        arg = data.get("arg", {})
        channel = arg.get("channel", "")
        items = data.get("data", [])

        for item in items:
            inst_id = arg.get("instId", item.get("instId", ""))
            symbol = _symbol_from_inst(inst_id)

            if channel == "books5":
                await self._process_orderbook(item, symbol)
            elif channel == "tickers":
                await self._process_ticker(item, symbol)
            elif channel == "mark-price":
                await self._process_mark_price(item, symbol)
            elif channel == "funding-rate":
                await self._process_funding_rate(item, symbol)
            elif channel == "open-interest":
                await self._process_open_interest(item, symbol)

    async def _process_orderbook(self, d: Dict[str, Any], symbol: str) -> None:
        bids = [OrderBookLevel(price=float(b[0]), quantity=float(b[1])) for b in d.get("bids", [])]
        asks = [OrderBookLevel(price=float(a[0]), quantity=float(a[1])) for a in d.get("asks", [])]
        ts = float(d.get("ts", time.time() * 1000)) / 1000.0

        ob = OrderBook(
            exchange=Exchange.OKX,
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=ts,
            raw=d,
        )
        await self._publish(EventType.ORDER_BOOK, ob, symbol)

    async def _process_ticker(self, d: Dict[str, Any], symbol: str) -> None:
        ts = float(d.get("ts", time.time() * 1000)) / 1000.0
        ticker = Ticker(
            exchange=Exchange.OKX,
            symbol=symbol,
            last_price=float(d.get("last", 0)),
            bid_price=float(d.get("bidPx", 0)) if d.get("bidPx") else None,
            ask_price=float(d.get("askPx", 0)) if d.get("askPx") else None,
            high_24h=float(d.get("high24h", 0)) if d.get("high24h") else None,
            low_24h=float(d.get("low24h", 0)) if d.get("low24h") else None,
            volume_24h=float(d.get("vol24h", 0)) if d.get("vol24h") else None,
            volume_24h_quote=float(d.get("volCcy24h", 0)) if d.get("volCcy24h") else None,
            timestamp=ts,
            raw=d,
        )
        await self._publish(EventType.TICKER, ticker, symbol)

    async def _process_mark_price(self, d: Dict[str, Any], symbol: str) -> None:
        ts = float(d.get("ts", time.time() * 1000)) / 1000.0
        mp = MarkPrice(
            exchange=Exchange.OKX,
            symbol=symbol,
            mark_price=float(d.get("markPx", 0)),
            timestamp=ts,
            raw=d,
        )
        await self._publish(EventType.MARK_PRICE, mp, symbol)

    async def _process_funding_rate(self, d: Dict[str, Any], symbol: str) -> None:
        ts = float(d.get("ts", time.time() * 1000)) / 1000.0
        fr = FundingRate(
            exchange=Exchange.OKX,
            symbol=symbol,
            funding_rate=float(d.get("fundingRate", 0)),
            predicted_rate=float(d.get("nextFundingRate", 0)) if d.get("nextFundingRate") else None,
            next_funding_time=float(d.get("nextFundingTime", 0)) / 1000.0 if d.get("nextFundingTime") else None,
            timestamp=ts,
            raw=d,
        )
        await self._publish(EventType.FUNDING_RATE, fr, symbol)

    async def _process_open_interest(self, d: Dict[str, Any], symbol: str) -> None:
        ts = float(d.get("ts", time.time() * 1000)) / 1000.0
        oi = OpenInterest(
            exchange=Exchange.OKX,
            symbol=symbol,
            open_interest=float(d.get("oi", 0)),
            open_interest_value=float(d.get("oiCcy", 0)) if d.get("oiCcy") else None,
            timestamp=ts,
            raw=d,
        )
        await self._publish(EventType.OPEN_INTEREST, oi, symbol)

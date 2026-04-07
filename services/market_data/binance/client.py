"""
CoinScopeAI — Binance Futures Client

WebSocket streams:
  - markPrice@1s
  - bookTicker
  - aggTrade

REST polling:
  - Open Interest  (GET /fapi/v1/openInterest)
  - Funding History (GET /fapi/v1/fundingRate)
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

logger = logging.getLogger("coinscopeai.market_data.binance")


class BinanceFuturesClient(BaseExchangeClient):
    """Binance USD-M Futures public data client."""

    EXCHANGE = Exchange.BINANCE
    WS_BASE_URL = "wss://fstream.binance.com"
    REST_BASE_URL = "https://fapi.binance.com"

    # REST polling intervals (seconds)
    OI_POLL_INTERVAL = 15.0
    FUNDING_POLL_INTERVAL = 60.0

    def __init__(
        self,
        symbols: List[str],
        event_bus: Optional[EventBus] = None,
        rest_rate_limit: int = 10,
        rest_rate_period: float = 1.0,
        oi_poll_interval: float = 15.0,
        funding_poll_interval: float = 60.0,
        use_testnet: bool = False,
    ) -> None:
        super().__init__(symbols, event_bus, rest_rate_limit, rest_rate_period)
        self.oi_poll_interval = oi_poll_interval
        self.funding_poll_interval = funding_poll_interval
        if use_testnet:
            self.WS_BASE_URL = "wss://stream.binancefuture.com"
            self.REST_BASE_URL = "https://testnet.binancefuture.com"

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def _create_ws_tasks(self) -> List[asyncio.Task]:
        tasks = []
        # Combined stream URL for all symbols
        streams = []
        for sym in self.symbols:
            s = sym.lower()
            streams.append(f"{s}@markPrice@1s")
            streams.append(f"{s}@bookTicker")
            streams.append(f"{s}@aggTrade")

        url = f"{self.WS_BASE_URL}/stream?streams={'/'.join(streams)}"
        tasks.append(asyncio.create_task(
            self._ws_connect_loop(url, self._handle_combined_message, label="combined"),
            name=f"binance-ws-combined",
        ))
        return tasks

    def _create_rest_tasks(self) -> List[asyncio.Task]:
        tasks = []
        tasks.append(asyncio.create_task(
            self._rest_poll_loop("open_interest", self.oi_poll_interval, self._poll_open_interest),
            name="binance-rest-oi",
        ))
        tasks.append(asyncio.create_task(
            self._rest_poll_loop("funding_rate", self.funding_poll_interval, self._poll_funding_rate),
            name="binance-rest-funding",
        ))
        return tasks

    # ------------------------------------------------------------------
    # WebSocket message handlers
    # ------------------------------------------------------------------

    async def _handle_combined_message(self, raw: str) -> None:
        data = json.loads(raw)
        stream = data.get("stream", "")
        payload = data.get("data", {})

        if "@markPrice" in stream:
            await self._process_mark_price(payload)
        elif "@bookTicker" in stream:
            await self._process_book_ticker(payload)
        elif "@aggTrade" in stream:
            await self._process_agg_trade(payload)

    async def _process_mark_price(self, d: Dict[str, Any]) -> None:
        symbol = d.get("s", "")
        mp = MarkPrice(
            exchange=Exchange.BINANCE,
            symbol=symbol,
            mark_price=float(d.get("p", 0)),
            index_price=float(d.get("i", 0)) if d.get("i") else None,
            estimated_settle_price=float(d.get("P", 0)) if d.get("P") else None,
            timestamp=float(d.get("E", time.time() * 1000)) / 1000.0,
            raw=d,
        )
        await self._publish(EventType.MARK_PRICE, mp, symbol)

    async def _process_book_ticker(self, d: Dict[str, Any]) -> None:
        symbol = d.get("s", "")
        ob = OrderBook(
            exchange=Exchange.BINANCE,
            symbol=symbol,
            bids=[OrderBookLevel(price=float(d.get("b", 0)), quantity=float(d.get("B", 0)))],
            asks=[OrderBookLevel(price=float(d.get("a", 0)), quantity=float(d.get("A", 0)))],
            timestamp=float(d.get("E", time.time() * 1000)) / 1000.0 if d.get("E") else time.time(),
            raw=d,
        )
        await self._publish(EventType.ORDER_BOOK, ob, symbol)

    async def _process_agg_trade(self, d: Dict[str, Any]) -> None:
        symbol = d.get("s", "")
        trade = Trade(
            exchange=Exchange.BINANCE,
            symbol=symbol,
            trade_id=str(d.get("a", "")),
            price=float(d.get("p", 0)),
            quantity=float(d.get("q", 0)),
            side=Side.SELL if d.get("m") else Side.BUY,  # m=True → seller is maker → taker bought
            timestamp=float(d.get("T", time.time() * 1000)) / 1000.0,
            raw=d,
        )
        await self._publish(EventType.TRADE, trade, symbol)

    # ------------------------------------------------------------------
    # REST polling
    # ------------------------------------------------------------------

    async def _poll_open_interest(self) -> None:
        for symbol in self.symbols:
            url = f"{self.REST_BASE_URL}/fapi/v1/openInterest"
            data = await self._rest_get(url, params={"symbol": symbol})
            oi = OpenInterest(
                exchange=Exchange.BINANCE,
                symbol=data.get("symbol", symbol),
                open_interest=float(data.get("openInterest", 0)),
                timestamp=float(data.get("time", time.time() * 1000)) / 1000.0,
                raw=data,
            )
            await self._publish(EventType.OPEN_INTEREST, oi, symbol)

    async def _poll_funding_rate(self) -> None:
        for symbol in self.symbols:
            url = f"{self.REST_BASE_URL}/fapi/v1/premiumIndex"
            data = await self._rest_get(url, params={"symbol": symbol})
            fr = FundingRate(
                exchange=Exchange.BINANCE,
                symbol=data.get("symbol", symbol),
                funding_rate=float(data.get("lastFundingRate", 0)),
                predicted_rate=None,  # Binance doesn't expose predicted in this endpoint
                next_funding_time=float(data.get("nextFundingTime", 0)) / 1000.0 if data.get("nextFundingTime") else None,
                timestamp=float(data.get("time", time.time() * 1000)) / 1000.0,
                raw=data,
            )
            await self._publish(EventType.FUNDING_RATE, fr, symbol)

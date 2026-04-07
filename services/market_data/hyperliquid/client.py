"""
CoinScopeAI — Hyperliquid Client

Hyperliquid uses a single WebSocket endpoint with subscription channels:
  - allMids        (mid prices for all assets)
  - l2Book         (order book per coin)
  - trades         (public trades per coin)
  - activeAssetCtx (funding, open interest, mark price per coin)

REST info endpoint for supplementary data:
  - POST https://api.hyperliquid.xyz/info
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

logger = logging.getLogger("coinscopeai.market_data.hyperliquid")


def _hl_coin(symbol: str) -> str:
    """Convert unified symbol like BTCUSDT to Hyperliquid coin like BTC."""
    return symbol.replace("USDT", "").replace("USD", "")


class HyperliquidClient(BaseExchangeClient):
    """Hyperliquid perpetual public data client."""

    EXCHANGE = Exchange.HYPERLIQUID
    WS_BASE_URL = "wss://api.hyperliquid.xyz/ws"
    REST_BASE_URL = "https://api.hyperliquid.xyz"

    # Hyperliquid REST info polling
    FUNDING_POLL_INTERVAL = 30.0

    def __init__(
        self,
        symbols: List[str],
        event_bus: Optional[EventBus] = None,
        rest_rate_limit: int = 5,
        rest_rate_period: float = 1.0,
        funding_poll_interval: float = 30.0,
    ) -> None:
        super().__init__(symbols, event_bus, rest_rate_limit, rest_rate_period)
        self.funding_poll_interval = funding_poll_interval
        # Map coin -> unified symbol for reverse lookup
        self._coin_to_symbol = {_hl_coin(s): s for s in self.symbols}

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def _create_ws_tasks(self) -> List[asyncio.Task]:
        tasks = []

        # allMids stream (single subscription, covers all coins)
        tasks.append(asyncio.create_task(
            self._ws_connect_loop(
                self.WS_BASE_URL,
                self._handle_all_mids,
                subscribe_msg={"method": "subscribe", "subscription": {"type": "allMids"}},
                label="allMids",
            ),
            name="hl-ws-allMids",
        ))

        # Per-symbol streams: l2Book + trades
        for sym in self.symbols:
            coin = _hl_coin(sym)
            tasks.append(asyncio.create_task(
                self._ws_connect_loop(
                    self.WS_BASE_URL,
                    self._handle_l2book,
                    subscribe_msg={"method": "subscribe", "subscription": {"type": "l2Book", "coin": coin}},
                    label=f"l2Book-{coin}",
                ),
                name=f"hl-ws-l2book-{coin}",
            ))
            tasks.append(asyncio.create_task(
                self._ws_connect_loop(
                    self.WS_BASE_URL,
                    self._handle_trades,
                    subscribe_msg={"method": "subscribe", "subscription": {"type": "trades", "coin": coin}},
                    label=f"trades-{coin}",
                ),
                name=f"hl-ws-trades-{coin}",
            ))

        return tasks

    def _create_rest_tasks(self) -> List[asyncio.Task]:
        return [
            asyncio.create_task(
                self._rest_poll_loop("funding_oi", self.funding_poll_interval, self._poll_meta_and_ctx),
                name="hl-rest-meta",
            ),
        ]

    # ------------------------------------------------------------------
    # WebSocket message handlers
    # ------------------------------------------------------------------

    async def _handle_all_mids(self, raw: str) -> None:
        data = json.loads(raw)
        channel = data.get("channel")
        if channel != "allMids":
            return
        mids = data.get("data", {}).get("mids", {})
        for coin, price_str in mids.items():
            symbol = self._coin_to_symbol.get(coin)
            if symbol is None:
                continue
            mp = MarkPrice(
                exchange=Exchange.HYPERLIQUID,
                symbol=symbol,
                mark_price=float(price_str),
                timestamp=time.time(),
                raw={"coin": coin, "mid": price_str},
            )
            await self._publish(EventType.MARK_PRICE, mp, symbol)

    async def _handle_l2book(self, raw: str) -> None:
        data = json.loads(raw)
        channel = data.get("channel")
        if channel != "l2Book":
            return
        book = data.get("data", {})
        coin = book.get("coin", "")
        symbol = self._coin_to_symbol.get(coin)
        if symbol is None:
            return

        levels = book.get("levels", [[], []])
        bids = [OrderBookLevel(price=float(b.get("px", 0)), quantity=float(b.get("sz", 0))) for b in levels[0]] if len(levels) > 0 else []
        asks = [OrderBookLevel(price=float(a.get("px", 0)), quantity=float(a.get("sz", 0))) for a in levels[1]] if len(levels) > 1 else []

        ob = OrderBook(
            exchange=Exchange.HYPERLIQUID,
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=float(book.get("time", time.time() * 1000)) / 1000.0 if book.get("time") else time.time(),
            raw=book,
        )
        await self._publish(EventType.ORDER_BOOK, ob, symbol)

    async def _handle_trades(self, raw: str) -> None:
        data = json.loads(raw)
        channel = data.get("channel")
        if channel != "trades":
            return
        trades = data.get("data", [])
        for t in trades:
            coin = t.get("coin", "")
            symbol = self._coin_to_symbol.get(coin)
            if symbol is None:
                continue
            trade = Trade(
                exchange=Exchange.HYPERLIQUID,
                symbol=symbol,
                trade_id=str(t.get("tid", "")),
                price=float(t.get("px", 0)),
                quantity=float(t.get("sz", 0)),
                side=Side.BUY if t.get("side") == "B" else Side.SELL,
                timestamp=float(t.get("time", time.time() * 1000)) / 1000.0 if t.get("time") else time.time(),
                raw=t,
            )
            await self._publish(EventType.TRADE, trade, symbol)

    # ------------------------------------------------------------------
    # REST polling — meta + asset contexts (funding, OI)
    # ------------------------------------------------------------------

    async def _poll_meta_and_ctx(self) -> None:
        """
        POST /info with {"type": "metaAndAssetCtxs"} returns metadata
        and per-asset context including funding rate and open interest.
        """
        import aiohttp

        await self.rate_limiter.acquire()
        session = await self._get_session()
        url = f"{self.REST_BASE_URL}/info"
        payload = {"type": "metaAndAssetCtxs"}

        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                result = await resp.json()
        except Exception:
            self.metrics.errors += 1
            logger.exception("[hyperliquid] REST meta poll error")
            return

        if not isinstance(result, list) or len(result) < 2:
            return

        meta = result[0]
        ctxs = result[1]
        universe = meta.get("universe", [])

        for i, asset_info in enumerate(universe):
            coin = asset_info.get("name", "")
            symbol = self._coin_to_symbol.get(coin)
            if symbol is None:
                continue
            if i >= len(ctxs):
                continue
            ctx = ctxs[i]

            # Funding rate
            funding_str = ctx.get("funding")
            if funding_str is not None:
                fr = FundingRate(
                    exchange=Exchange.HYPERLIQUID,
                    symbol=symbol,
                    funding_rate=float(funding_str),
                    timestamp=time.time(),
                    raw=ctx,
                )
                await self._publish(EventType.FUNDING_RATE, fr, symbol)

            # Open interest
            oi_str = ctx.get("openInterest")
            if oi_str is not None:
                oi = OpenInterest(
                    exchange=Exchange.HYPERLIQUID,
                    symbol=symbol,
                    open_interest=float(oi_str),
                    timestamp=time.time(),
                    raw=ctx,
                )
                await self._publish(EventType.OPEN_INTEREST, oi, symbol)

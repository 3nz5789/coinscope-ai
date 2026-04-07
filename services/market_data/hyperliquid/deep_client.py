"""
CoinScopeAI Phase 2 — Hyperliquid Deep Integration Client

Extends Phase 1 Hyperliquid connectivity with:
  - Asset contexts (meta + per-asset context: funding, mark prices, OI)
  - Predicted funding rates across venues
  - Historical funding rates
  - L2 order book snapshots
  - Real-time WebSocket subscriptions for L2 book and asset context updates

All requests target the Hyperliquid Info API at https://api.hyperliquid.xyz/info
(POST with JSON body, no authentication required for public data).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

import aiohttp

from services.market_data.models import (
    AssetContext,
    Exchange,
    FundingRate,
    L2OrderBook,
    OrderBookLevel,
    PredictedFunding,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
HL_WS_URL = "wss://api.hyperliquid.xyz/ws"
HL_TESTNET_INFO_URL = "https://api.hyperliquid-testnet.xyz/info"
HL_TESTNET_WS_URL = "wss://api.hyperliquid-testnet.xyz/ws"

DEFAULT_HEADERS = {"Content-Type": "application/json"}
WS_PING_INTERVAL = 50  # seconds


# ---------------------------------------------------------------------------
# REST Client
# ---------------------------------------------------------------------------

class HyperliquidDeepClient:
    """
    Extended Hyperliquid REST client for deep market data.

    Provides methods for fetching asset contexts, funding data, and L2 order
    book snapshots via the Info API.  All methods are async and return
    normalised model objects from ``services.market_data.models``.
    """

    def __init__(
        self,
        base_url: str = HL_INFO_URL,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url
        self._external_session = session is not None
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_retries = max_retries

    # -- lifecycle -----------------------------------------------------------

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout, headers=DEFAULT_HEADERS
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._external_session:
            await self._session.close()

    # -- low-level request ---------------------------------------------------

    async def _post(self, payload: Dict[str, Any]) -> Any:
        session = await self._ensure_session()
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with session.post(
                    self._base_url, json=payload
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "Hyperliquid request attempt %d/%d failed: %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * attempt)
        raise ConnectionError(
            f"Hyperliquid request failed after {self._max_retries} attempts"
        ) from last_exc

    # -- meta & asset contexts -----------------------------------------------

    async def get_meta_and_asset_contexts(
        self, dex: str = ""
    ) -> tuple[dict, List[AssetContext]]:
        """
        Fetch ``metaAndAssetCtxs`` — returns (meta_dict, list_of_AssetContext).

        The meta dict contains ``universe`` (list of asset descriptors) and
        ``marginTables``.  The asset contexts list is positionally aligned
        with ``universe``.
        """
        payload: Dict[str, Any] = {"type": "metaAndAssetCtxs"}
        if dex:
            payload["dex"] = dex

        raw = await self._post(payload)
        meta = raw[0]
        raw_ctxs = raw[1]
        universe = meta.get("universe", [])

        contexts: List[AssetContext] = []
        now = time.time()
        for idx, ctx in enumerate(raw_ctxs):
            name = universe[idx]["name"] if idx < len(universe) else f"UNKNOWN_{idx}"
            impact = None
            if ctx.get("impactPxs"):
                impact = [float(p) for p in ctx["impactPxs"]]
            contexts.append(
                AssetContext(
                    symbol=name,
                    funding_rate=float(ctx.get("funding", 0)),
                    mark_price=float(ctx.get("markPx", 0)),
                    mid_price=float(ctx["midPx"]) if ctx.get("midPx") else None,
                    oracle_price=float(ctx.get("oraclePx", 0)),
                    open_interest=float(ctx.get("openInterest", 0)),
                    day_notional_volume=float(ctx.get("dayNtlVlm", 0)),
                    premium=float(ctx.get("premium", 0)) if ctx.get("premium") is not None else 0.0,
                    prev_day_price=float(ctx.get("prevDayPx", 0)),
                    impact_prices=impact,
                    timestamp=now,
                )
            )
        return meta, contexts

    # -- predicted funding ---------------------------------------------------

    async def get_predicted_fundings(self) -> Dict[str, List[PredictedFunding]]:
        """
        Fetch ``predictedFundings`` — predicted next funding rates across venues.

        Returns a dict mapping symbol -> list of PredictedFunding.
        """
        raw = await self._post({"type": "predictedFundings"})
        result: Dict[str, List[PredictedFunding]] = {}
        for entry in raw:
            symbol = entry[0]
            venues = entry[1]
            preds: List[PredictedFunding] = []
            for venue_name, info in venues:
                preds.append(
                    PredictedFunding(
                        symbol=symbol,
                        venue=venue_name,
                        predicted_rate=float(info.get("fundingRate", 0)),
                        next_funding_time=float(info.get("nextFundingTime", 0)),
                    )
                )
            result[symbol] = preds
        return result

    # -- funding history -----------------------------------------------------

    async def get_funding_history(
        self,
        coin: str,
        start_time_ms: int,
        end_time_ms: Optional[int] = None,
    ) -> List[FundingRate]:
        """
        Fetch ``fundingHistory`` — historical funding rates for a coin.

        ``start_time_ms`` and ``end_time_ms`` are in epoch milliseconds.
        Returns at most 500 records per call (use pagination for more).
        """
        payload: Dict[str, Any] = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": start_time_ms,
        }
        if end_time_ms is not None:
            payload["endTime"] = end_time_ms

        raw = await self._post(payload)
        rates: List[FundingRate] = []
        for entry in raw:
            rates.append(
                FundingRate(
                    symbol=entry.get("coin", coin),
                    exchange=Exchange.HYPERLIQUID,
                    rate=float(entry.get("fundingRate", 0)),
                    timestamp=float(entry.get("time", 0)) / 1000.0,
                    premium=float(entry.get("premium", 0)),
                )
            )
        return rates

    # -- L2 order book -------------------------------------------------------

    async def get_l2_book(
        self,
        coin: str,
        n_sig_figs: Optional[int] = None,
    ) -> L2OrderBook:
        """
        Fetch ``l2Book`` — Level 2 order book snapshot (max 20 levels/side).
        """
        payload: Dict[str, Any] = {"type": "l2Book", "coin": coin}
        if n_sig_figs is not None:
            payload["nSigFigs"] = n_sig_figs

        raw = await self._post(payload)
        bids_raw = raw.get("levels", [[], []])[0]
        asks_raw = raw.get("levels", [[], []])[1]

        bids = [
            OrderBookLevel(
                price=float(lvl["px"]),
                size=float(lvl["sz"]),
                num_orders=int(lvl.get("n", 1)),
            )
            for lvl in bids_raw
        ]
        asks = [
            OrderBookLevel(
                price=float(lvl["px"]),
                size=float(lvl["sz"]),
                num_orders=int(lvl.get("n", 1)),
            )
            for lvl in asks_raw
        ]

        return L2OrderBook(
            symbol=raw.get("coin", coin),
            exchange=Exchange.HYPERLIQUID,
            timestamp=float(raw.get("time", time.time() * 1000)) / 1000.0,
            bids=bids,
            asks=asks,
        )

    # -- convenience: all mids -----------------------------------------------

    async def get_all_mids(self) -> Dict[str, float]:
        raw = await self._post({"type": "allMids"})
        return {k: float(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

# Callback type for incoming messages
WsCallback = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


class HyperliquidDeepWs:
    """
    Async WebSocket client for real-time Hyperliquid data streams.

    Supports subscriptions for:
      - ``l2Book``         — real-time L2 order book updates
      - ``activeAssetCtx`` — real-time per-asset context updates
      - ``trades``         — real-time trade feed
      - ``allMids``        — all mid-price updates
    """

    def __init__(
        self,
        ws_url: str = HL_WS_URL,
        on_message: Optional[WsCallback] = None,
        reconnect_delay: float = 2.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        self._ws_url = ws_url
        self._on_message = on_message
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = max_reconnect_delay
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._subscriptions: List[Dict[str, Any]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # -- subscription management ---------------------------------------------

    def subscribe_l2_book(self, coin: str) -> None:
        sub = {"type": "l2Book", "coin": coin}
        self._subscriptions.append(sub)

    def subscribe_active_asset_ctx(self, coin: str) -> None:
        sub = {"type": "activeAssetCtx", "coin": coin}
        self._subscriptions.append(sub)

    def subscribe_trades(self, coin: str) -> None:
        sub = {"type": "trades", "coin": coin}
        self._subscriptions.append(sub)

    def subscribe_all_mids(self) -> None:
        sub = {"type": "allMids"}
        self._subscriptions.append(sub)

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start the WebSocket connection loop in the background."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Gracefully stop the WebSocket connection."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session:
            await self._session.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    # -- internal loop -------------------------------------------------------

    async def _run_loop(self) -> None:
        delay = self._reconnect_delay
        while self._running:
            try:
                await self._connect_and_listen()
            except (aiohttp.WSServerHandshakeError, aiohttp.ClientError, OSError) as exc:
                logger.warning("WS connection error: %s — reconnecting in %.1fs", exc, delay)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Unexpected WS error — reconnecting in %.1fs", delay)

            if self._running:
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, self._max_reconnect_delay)

    async def _connect_and_listen(self) -> None:
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(
                self._ws_url, heartbeat=WS_PING_INTERVAL
            )
            logger.info("Connected to Hyperliquid WS: %s", self._ws_url)

            # Send all subscriptions
            for sub in self._subscriptions:
                msg = {"method": "subscribe", "subscription": sub}
                await self._ws.send_json(msg)
                logger.debug("Sent subscription: %s", sub)

            # Listen loop
            async for ws_msg in self._ws:
                if ws_msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(ws_msg.data)
                elif ws_msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
        finally:
            if self._session:
                await self._session.close()

    async def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse WS message: %s", raw[:200])
            return

        channel = data.get("channel", "")
        payload = data.get("data", {})

        if channel == "subscriptionResponse":
            logger.debug("Subscription confirmed: %s", payload)
            return

        if self._on_message:
            try:
                await self._on_message(channel, payload)
            except Exception:
                logger.exception("Error in WS message callback for channel=%s", channel)

    # -- helpers for parsing incoming data -----------------------------------

    @staticmethod
    def parse_l2_book(data: Dict[str, Any]) -> L2OrderBook:
        """Parse a WsBook message into an L2OrderBook model."""
        levels = data.get("levels", [[], []])
        bids = [
            OrderBookLevel(
                price=float(lvl["px"]),
                size=float(lvl["sz"]),
                num_orders=int(lvl.get("n", 1)),
            )
            for lvl in levels[0]
        ]
        asks = [
            OrderBookLevel(
                price=float(lvl["px"]),
                size=float(lvl["sz"]),
                num_orders=int(lvl.get("n", 1)),
            )
            for lvl in levels[1]
        ]
        return L2OrderBook(
            symbol=data.get("coin", ""),
            exchange=Exchange.HYPERLIQUID,
            timestamp=float(data.get("time", time.time() * 1000)) / 1000.0,
            bids=bids,
            asks=asks,
        )

    @staticmethod
    def parse_asset_context(data: Dict[str, Any]) -> AssetContext:
        """Parse a WsActiveAssetCtx message into an AssetContext model."""
        ctx = data.get("ctx", data)
        coin = data.get("coin", ctx.get("coin", ""))
        impact = None
        if ctx.get("impactPxs"):
            impact = [float(p) for p in ctx["impactPxs"]]
        return AssetContext(
            symbol=coin,
            funding_rate=float(ctx.get("funding", 0)),
            mark_price=float(ctx.get("markPx", 0)),
            mid_price=float(ctx["midPx"]) if ctx.get("midPx") else None,
            oracle_price=float(ctx.get("oraclePx", 0)),
            open_interest=float(ctx.get("openInterest", 0)),
            day_notional_volume=float(ctx.get("dayNtlVlm", 0)),
            premium=float(ctx.get("premium", 0)) if ctx.get("premium") is not None else 0.0,
            prev_day_price=float(ctx.get("prevDayPx", 0)),
            impact_prices=impact,
            timestamp=time.time(),
        )

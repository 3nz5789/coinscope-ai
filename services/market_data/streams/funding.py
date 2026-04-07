"""
Unified Funding Rate Stream — real-time and historical funding rates
from Binance, Bybit, OKX, and Hyperliquid via free public endpoints.

Approach per exchange:
- Binance: REST polling premiumIndex (current + predicted) + fundingRate (historical)
- Bybit: REST polling funding/history
- OKX: WebSocket funding-rate channel (real-time) + REST historical
- Hyperliquid: REST polling metaAndAssetCtxs (current) + fundingHistory (historical)
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
    FundingRate,
    normalize_symbol,
    now_ms,
    to_binance_symbol,
    to_bybit_symbol,
    to_hyperliquid_coin,
    to_okx_symbol,
)

logger = logging.getLogger("coinscopeai.streams.funding")


class FundingStream(BaseStream):
    """
    Unified funding rate stream.

    Polls REST endpoints at configurable intervals for exchanges without
    WebSocket funding feeds, and uses WebSocket where available (OKX).
    """

    def __init__(
        self,
        symbols: List[str],
        exchanges: Optional[List[Exchange]] = None,
        event_bus: Optional[EventBus] = None,
        poll_interval: float = 30.0,
    ):
        super().__init__(symbols, exchanges, event_bus)
        self.poll_interval = poll_interval

    def _create_tasks(self) -> List[asyncio.Task]:
        tasks: List[asyncio.Task] = []
        for symbol in self.symbols:
            for exchange in self.exchanges:
                if exchange == Exchange.BINANCE:
                    tasks.append(asyncio.create_task(self._binance_funding(symbol)))
                elif exchange == Exchange.BYBIT:
                    tasks.append(asyncio.create_task(self._bybit_funding(symbol)))
                elif exchange == Exchange.OKX:
                    tasks.append(asyncio.create_task(self._okx_funding(symbol)))
                elif exchange == Exchange.HYPERLIQUID:
                    tasks.append(asyncio.create_task(self._hyperliquid_funding(symbol)))
        return tasks

    # ------------------------------------------------------------------
    # Binance: REST premiumIndex (current + predicted)
    # ------------------------------------------------------------------
    async def _binance_funding(self, symbol: str) -> None:
        sym = normalize_symbol(symbol)
        while self._running:
            try:
                data = await self._rest_get(
                    "https://fapi.binance.com/fapi/v1/premiumIndex",
                    Exchange.BINANCE,
                    params={"symbol": sym},
                )
                if isinstance(data, dict):
                    fr = FundingRate(
                        exchange=Exchange.BINANCE.value,
                        symbol=sym,
                        funding_rate=float(data.get("lastFundingRate", 0)),
                        predicted_rate=float(data.get("interestRate", 0)),
                        funding_time_ms=int(data.get("nextFundingTime", 0)),
                        timestamp_ms=int(data.get("time", now_ms())),
                        received_ms=now_ms(),
                        mark_price=float(data.get("markPrice", 0)),
                        index_price=float(data.get("indexPrice", 0)),
                    )
                    await self.bus.publish(EventType.FUNDING_RATE, fr)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("Binance funding poll error for %s: %s", symbol, exc)
            await asyncio.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Bybit: REST /v5/market/funding/history
    # ------------------------------------------------------------------
    async def _bybit_funding(self, symbol: str) -> None:
        bybit_sym = to_bybit_symbol(symbol)
        while self._running:
            try:
                data = await self._rest_get(
                    "https://api.bybit.com/v5/market/funding/history",
                    Exchange.BYBIT,
                    params={"category": "linear", "symbol": bybit_sym, "limit": "1"},
                )
                result = data.get("result", {})
                items = result.get("list", [])
                if items:
                    item = items[0]
                    fr = FundingRate(
                        exchange=Exchange.BYBIT.value,
                        symbol=normalize_symbol(symbol),
                        funding_rate=float(item.get("fundingRate", 0)),
                        predicted_rate=None,
                        funding_time_ms=int(item.get("fundingRateTimestamp", 0)),
                        timestamp_ms=int(item.get("fundingRateTimestamp", now_ms())),
                        received_ms=now_ms(),
                    )
                    await self.bus.publish(EventType.FUNDING_RATE, fr)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("Bybit funding poll error for %s: %s", symbol, exc)
            await asyncio.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # OKX: WebSocket funding-rate channel (real-time)
    # ------------------------------------------------------------------
    async def _okx_funding(self, symbol: str) -> None:
        url = "wss://ws.okx.com:8443/ws/v5/public"
        okx_inst = to_okx_symbol(symbol)
        sub = {
            "op": "subscribe",
            "args": [{"channel": "funding-rate", "instId": okx_inst}],
        }

        async def on_msg(data: Any) -> None:
            if not isinstance(data, dict):
                return
            if "data" not in data:
                return
            for item in data["data"]:
                fr = FundingRate(
                    exchange=Exchange.OKX.value,
                    symbol=normalize_symbol(symbol),
                    funding_rate=float(item.get("fundingRate", 0)),
                    predicted_rate=float(item.get("nextFundingRate", 0)) if item.get("nextFundingRate") else None,
                    funding_time_ms=int(item.get("fundingTime", 0)),
                    timestamp_ms=int(item.get("ts", now_ms())),
                    received_ms=now_ms(),
                )
                await self.bus.publish(EventType.FUNDING_RATE, fr)

        await self._ws_connect_loop(
            url, on_msg, Exchange.OKX, symbol,
            subscribe_msg=sub, stream_type="funding-rate",
        )

    # ------------------------------------------------------------------
    # Hyperliquid: REST metaAndAssetCtxs (current funding)
    # ------------------------------------------------------------------
    async def _hyperliquid_funding(self, symbol: str) -> None:
        coin = to_hyperliquid_coin(symbol)
        while self._running:
            try:
                data = await self._rest_post(
                    "https://api.hyperliquid.xyz/info",
                    Exchange.HYPERLIQUID,
                    json_data={"type": "metaAndAssetCtxs"},
                )
                # Response: [meta, [assetCtx, ...]]
                if isinstance(data, list) and len(data) >= 2:
                    meta = data[0]
                    ctxs = data[1]
                    universe = meta.get("universe", [])
                    for i, asset in enumerate(universe):
                        if asset.get("name", "").upper() == coin.upper() and i < len(ctxs):
                            ctx = ctxs[i]
                            funding_val = ctx.get("funding", 0)
                            if isinstance(funding_val, str):
                                funding_val = float(funding_val)
                            mark_px = ctx.get("markPx", 0)
                            if isinstance(mark_px, str):
                                mark_px = float(mark_px)
                            fr = FundingRate(
                                exchange=Exchange.HYPERLIQUID.value,
                                symbol=normalize_symbol(symbol),
                                funding_rate=float(funding_val),
                                predicted_rate=None,
                                funding_time_ms=0,  # HL doesn't give next funding time directly
                                timestamp_ms=now_ms(),
                                received_ms=now_ms(),
                                mark_price=mark_px,
                            )
                            await self.bus.publish(EventType.FUNDING_RATE, fr)
                            break
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("Hyperliquid funding poll error for %s: %s", symbol, exc)
            await asyncio.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Historical funding rate fetchers (for backtest/download)
    # ------------------------------------------------------------------

    @staticmethod
    async def fetch_binance_funding_history(
        session: Any, symbol: str, start_time: Optional[int] = None,
        end_time: Optional[int] = None, limit: int = 1000,
    ) -> List[FundingRate]:
        """Fetch historical funding rates from Binance REST."""
        params: Dict[str, Any] = {"symbol": normalize_symbol(symbol), "limit": str(limit)}
        if start_time:
            params["startTime"] = str(start_time)
        if end_time:
            params["endTime"] = str(end_time)
        async with session.get("https://fapi.binance.com/fapi/v1/fundingRate", params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
        results = []
        for item in data:
            results.append(FundingRate(
                exchange=Exchange.BINANCE.value,
                symbol=normalize_symbol(item.get("symbol", symbol)),
                funding_rate=float(item.get("fundingRate", 0)),
                predicted_rate=None,
                funding_time_ms=int(item.get("fundingTime", 0)),
                timestamp_ms=int(item.get("fundingTime", 0)),
                received_ms=now_ms(),
                mark_price=float(item.get("markPrice", 0)) if item.get("markPrice") else None,
            ))
        return results

    @staticmethod
    async def fetch_bybit_funding_history(
        session: Any, symbol: str, start_time: Optional[int] = None,
        end_time: Optional[int] = None, limit: int = 200,
    ) -> List[FundingRate]:
        """Fetch historical funding rates from Bybit REST."""
        params: Dict[str, Any] = {
            "category": "linear",
            "symbol": to_bybit_symbol(symbol),
            "limit": str(limit),
        }
        if start_time:
            params["startTime"] = str(start_time)
        if end_time:
            params["endTime"] = str(end_time)
        async with session.get("https://api.bybit.com/v5/market/funding/history", params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
        results = []
        for item in data.get("result", {}).get("list", []):
            results.append(FundingRate(
                exchange=Exchange.BYBIT.value,
                symbol=normalize_symbol(symbol),
                funding_rate=float(item.get("fundingRate", 0)),
                predicted_rate=None,
                funding_time_ms=int(item.get("fundingRateTimestamp", 0)),
                timestamp_ms=int(item.get("fundingRateTimestamp", 0)),
                received_ms=now_ms(),
            ))
        return results

    @staticmethod
    async def fetch_okx_funding_history(
        session: Any, symbol: str, limit: int = 100,
    ) -> List[FundingRate]:
        """Fetch historical funding rates from OKX REST."""
        okx_inst = to_okx_symbol(symbol)
        params = {"instId": okx_inst, "limit": str(limit)}
        async with session.get("https://www.okx.com/api/v5/public/funding-rate-history", params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
        results = []
        for item in data.get("data", []):
            results.append(FundingRate(
                exchange=Exchange.OKX.value,
                symbol=normalize_symbol(symbol),
                funding_rate=float(item.get("fundingRate", 0)),
                predicted_rate=float(item.get("nextFundingRate", 0)) if item.get("nextFundingRate") else None,
                funding_time_ms=int(item.get("fundingTime", 0)),
                timestamp_ms=int(item.get("fundingTime", 0)),
                received_ms=now_ms(),
            ))
        return results

    @staticmethod
    async def fetch_hyperliquid_funding_history(
        session: Any, symbol: str, start_time: Optional[int] = None,
    ) -> List[FundingRate]:
        """Fetch historical funding rates from Hyperliquid REST."""
        coin = to_hyperliquid_coin(symbol)
        payload: Dict[str, Any] = {"type": "fundingHistory", "coin": coin}
        if start_time:
            payload["startTime"] = start_time
        async with session.post("https://api.hyperliquid.xyz/info", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
        results = []
        if isinstance(data, list):
            for item in data:
                ts = item.get("time", 0)
                if isinstance(ts, str):
                    ts = int(ts)
                results.append(FundingRate(
                    exchange=Exchange.HYPERLIQUID.value,
                    symbol=normalize_symbol(symbol),
                    funding_rate=float(item.get("fundingRate", 0)),
                    predicted_rate=None,
                    funding_time_ms=ts,
                    timestamp_ms=ts,
                    received_ms=now_ms(),
                ))
        return results

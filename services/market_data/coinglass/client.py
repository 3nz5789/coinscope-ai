"""
CoinScopeAI Phase 2 — CoinGlass Integration Client

Provides access to CoinGlass API v4 for:
  - Cross-exchange liquidation data
  - Cross-exchange open interest
  - Cross-exchange funding rates
  - Futures basis / premium data

The API key is **optional** — when ``COINGLASS_API_KEY`` is not set the
client falls back to a free aggregation layer that pulls data directly
from public exchange APIs (Binance, Bybit, OKX).

Base URL: https://open-api-v4.coinglass.com
Auth header: ``CG-API-KEY: <key>``
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional

import aiohttp

from services.market_data.models import (
    AggregatedBasis,
    AggregatedOI,
    BasisData,
    Exchange,
    FundingRate,
    FundingSnapshot,
    Liquidation,
    LiquidationSnapshot,
    OpenInterest,
    Side,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CG_BASE_URL = "https://open-api-v4.coinglass.com"

# Free fallback exchange REST endpoints (public, no auth)
BINANCE_FUTURES_URL = "https://fapi.binance.com"
BYBIT_V5_URL = "https://api.bybit.com"
OKX_URL = "https://www.okx.com"


# ---------------------------------------------------------------------------
# CoinGlass REST Client
# ---------------------------------------------------------------------------

class CoinGlassClient:
    """
    Async REST client for CoinGlass API v4.

    If ``api_key`` is ``None`` (or the env var ``COINGLASS_API_KEY`` is
    empty), all methods transparently delegate to
    :class:`ExchangeFallbackClient` which aggregates data from free
    public exchange APIs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = CG_BASE_URL,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key or os.environ.get("COINGLASS_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        self._fallback: Optional[ExchangeFallbackClient] = None

        if not self._api_key:
            logger.info(
                "No CoinGlass API key found — using free exchange fallback"
            )

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    # -- lifecycle -----------------------------------------------------------

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers: Dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["CG-API-KEY"] = self._api_key
            self._session = aiohttp.ClientSession(
                timeout=self._timeout, headers=headers
            )
        return self._session

    async def _ensure_fallback(self) -> ExchangeFallbackClient:
        if self._fallback is None:
            self._fallback = ExchangeFallbackClient()
        return self._fallback

    async def close(self) -> None:
        if self._session:
            await self._session.close()
        if self._fallback:
            await self._fallback.close()

    # -- low-level GET -------------------------------------------------------

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with session.get(url, params=params) as resp:
                    resp.raise_for_status()
                    body = await resp.json()
                    # CoinGlass wraps data in {"code": "0", "msg": "", "data": ...}
                    if isinstance(body, dict) and "data" in body:
                        return body["data"]
                    return body
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "CoinGlass GET %s attempt %d/%d failed: %s",
                    path, attempt, self._max_retries, exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * attempt)
        raise ConnectionError(
            f"CoinGlass GET {path} failed after {self._max_retries} attempts"
        ) from last_exc

    # -----------------------------------------------------------------------
    # Liquidation
    # -----------------------------------------------------------------------

    async def get_liquidation_history(
        self,
        symbol: str = "BTC",
        time_type: str = "1h",
    ) -> LiquidationSnapshot:
        """
        Aggregated liquidation history for a coin across exchanges.

        ``time_type``: "1h", "4h", "12h", "24h"
        """
        if not self.has_api_key:
            fb = await self._ensure_fallback()
            return await fb.get_liquidation_snapshot(symbol)

        raw = await self._get(
            "/api/futures/liquidation/aggregated-history",
            params={"symbol": symbol, "timeType": time_type},
        )
        return self._parse_liquidation_history(symbol, raw, time_type)

    async def get_liquidation_exchange_list(
        self,
        symbol: str = "BTC",
        time_type: str = "1h",
    ) -> List[Dict[str, Any]]:
        """Liquidation breakdown by exchange."""
        if not self.has_api_key:
            return []
        return await self._get(
            "/api/futures/liquidation/exchange-list",
            params={"symbol": symbol, "timeType": time_type},
        )

    # -----------------------------------------------------------------------
    # Open Interest
    # -----------------------------------------------------------------------

    async def get_oi_exchange_list(
        self,
        symbol: str = "BTC",
    ) -> AggregatedOI:
        """Cross-exchange open interest for a coin."""
        if not self.has_api_key:
            fb = await self._ensure_fallback()
            return await fb.get_aggregated_oi(symbol)

        raw = await self._get(
            "/api/futures/open-interest/exchange-list",
            params={"symbol": symbol},
        )
        return self._parse_oi_exchange_list(symbol, raw)

    async def get_oi_history(
        self,
        symbol: str = "BTC",
        interval: str = "1h",
    ) -> List[Dict[str, Any]]:
        """OI OHLC history."""
        if not self.has_api_key:
            return []
        return await self._get(
            "/api/futures/open-interest/aggregated-history",
            params={"symbol": symbol, "interval": interval},
        )

    # -----------------------------------------------------------------------
    # Funding Rates
    # -----------------------------------------------------------------------

    async def get_funding_exchange_list(
        self,
        symbol: str = "BTC",
    ) -> FundingSnapshot:
        """Cross-exchange current funding rates."""
        if not self.has_api_key:
            fb = await self._ensure_fallback()
            return await fb.get_funding_snapshot(symbol)

        raw = await self._get(
            "/api/futures/funding-rate/exchange-list",
            params={"symbol": symbol},
        )
        return self._parse_funding_exchange_list(symbol, raw)

    async def get_funding_history(
        self,
        symbol: str = "BTC",
        interval: str = "8h",
    ) -> List[Dict[str, Any]]:
        """Funding rate OHLC history."""
        if not self.has_api_key:
            return []
        return await self._get(
            "/api/futures/funding-rate/history",
            params={"symbol": symbol, "interval": interval},
        )

    async def get_funding_arbitrage(self) -> List[Dict[str, Any]]:
        """Funding rate arbitrage opportunities."""
        if not self.has_api_key:
            return []
        return await self._get("/api/futures/funding-rate/arbitrage")

    # -----------------------------------------------------------------------
    # Basis / Futures Premium
    # -----------------------------------------------------------------------

    async def get_basis_history(
        self,
        symbol: str = "BTC",
        interval: str = "1h",
    ) -> List[Dict[str, Any]]:
        """Futures basis history."""
        if not self.has_api_key:
            fb = await self._ensure_fallback()
            return await fb.get_basis_raw(symbol)
        return await self._get(
            "/api/futures/basis/history",
            params={"symbol": symbol, "interval": interval},
        )

    # -----------------------------------------------------------------------
    # Parsers
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_liquidation_history(
        symbol: str, raw: Any, time_type: str
    ) -> LiquidationSnapshot:
        window_map = {"1h": 3600, "4h": 14400, "12h": 43200, "24h": 86400}
        window = window_map.get(time_type, 3600)

        if isinstance(raw, list) and raw:
            latest = raw[-1] if isinstance(raw[-1], dict) else {}
        elif isinstance(raw, dict):
            latest = raw
        else:
            latest = {}

        return LiquidationSnapshot(
            symbol=symbol,
            timestamp=time.time(),
            window_seconds=window,
            long_liquidations_usd=float(latest.get("longLiquidationUsd", 0)),
            short_liquidations_usd=float(latest.get("shortLiquidationUsd", 0)),
            total_count=int(latest.get("count", 0)),
        )

    @staticmethod
    def _parse_oi_exchange_list(symbol: str, raw: Any) -> AggregatedOI:
        by_exchange: Dict[str, float] = {}
        if isinstance(raw, list):
            for entry in raw:
                ex_name = entry.get("exchangeName", "unknown")
                oi_val = float(entry.get("openInterest", 0))
                by_exchange[ex_name] = oi_val
        return AggregatedOI(
            symbol=symbol,
            timestamp=time.time(),
            by_exchange=by_exchange,
        )

    @staticmethod
    def _parse_funding_exchange_list(symbol: str, raw: Any) -> FundingSnapshot:
        rates: Dict[str, float] = {}
        if isinstance(raw, list):
            for entry in raw:
                ex_name = entry.get("exchangeName", "unknown")
                rate = float(entry.get("rate", 0))
                rates[ex_name] = rate
        return FundingSnapshot(
            symbol=symbol,
            timestamp=time.time(),
            rates=rates,
        )


# ---------------------------------------------------------------------------
# Free Exchange Fallback Client
# ---------------------------------------------------------------------------

class ExchangeFallbackClient:
    """
    Aggregates public exchange data as a free alternative to CoinGlass.

    Pulls from Binance Futures, Bybit v5, and OKX public endpoints.
    No API keys required.
    """

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def _safe_get(self, url: str, params: Optional[Dict] = None) -> Any:
        session = await self._ensure_session()
        try:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("Fallback GET %s returned %d", url, resp.status)
                return None
        except Exception as exc:
            logger.warning("Fallback GET %s failed: %s", url, exc)
            return None

    # -- Funding Rates -------------------------------------------------------

    async def get_funding_snapshot(self, symbol: str) -> FundingSnapshot:
        """Aggregate current funding rates from Binance, Bybit, OKX."""
        tasks = [
            self._binance_funding(symbol),
            self._bybit_funding(symbol),
            self._okx_funding(symbol),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        rates: Dict[str, float] = {}
        for r in results:
            if isinstance(r, dict):
                rates.update(r)
        return FundingSnapshot(
            symbol=symbol,
            timestamp=time.time(),
            rates=rates,
        )

    async def _binance_funding(self, symbol: str) -> Dict[str, float]:
        pair = f"{symbol.upper()}USDT"
        data = await self._safe_get(
            f"{BINANCE_FUTURES_URL}/fapi/v1/premiumIndex",
            params={"symbol": pair},
        )
        if data and isinstance(data, dict):
            rate = float(data.get("lastFundingRate", 0))
            return {"Binance": rate}
        return {}

    async def _bybit_funding(self, symbol: str) -> Dict[str, float]:
        pair = f"{symbol.upper()}USDT"
        data = await self._safe_get(
            f"{BYBIT_V5_URL}/v5/market/tickers",
            params={"category": "linear", "symbol": pair},
        )
        if data and isinstance(data, dict):
            result = data.get("result", {})
            tickers = result.get("list", [])
            if tickers:
                rate = float(tickers[0].get("fundingRate", 0))
                return {"Bybit": rate}
        return {}

    async def _okx_funding(self, symbol: str) -> Dict[str, float]:
        inst_id = f"{symbol.upper()}-USDT-SWAP"
        data = await self._safe_get(
            f"{OKX_URL}/api/v5/public/funding-rate",
            params={"instId": inst_id},
        )
        if data and isinstance(data, dict):
            entries = data.get("data", [])
            if entries:
                rate = float(entries[0].get("fundingRate", 0))
                return {"OKX": rate}
        return {}

    # -- Open Interest -------------------------------------------------------

    async def get_aggregated_oi(self, symbol: str) -> AggregatedOI:
        """Aggregate OI from Binance, Bybit, OKX."""
        tasks = [
            self._binance_oi(symbol),
            self._bybit_oi(symbol),
            self._okx_oi(symbol),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        by_exchange: Dict[str, float] = {}
        for r in results:
            if isinstance(r, dict):
                by_exchange.update(r)
        return AggregatedOI(
            symbol=symbol,
            timestamp=time.time(),
            by_exchange=by_exchange,
        )

    async def _binance_oi(self, symbol: str) -> Dict[str, float]:
        pair = f"{symbol.upper()}USDT"
        data = await self._safe_get(
            f"{BINANCE_FUTURES_URL}/fapi/v1/openInterest",
            params={"symbol": pair},
        )
        if data and isinstance(data, dict):
            oi = float(data.get("openInterest", 0))
            return {"Binance": oi}
        return {}

    async def _bybit_oi(self, symbol: str) -> Dict[str, float]:
        pair = f"{symbol.upper()}USDT"
        data = await self._safe_get(
            f"{BYBIT_V5_URL}/v5/market/tickers",
            params={"category": "linear", "symbol": pair},
        )
        if data and isinstance(data, dict):
            tickers = data.get("result", {}).get("list", [])
            if tickers:
                oi = float(tickers[0].get("openInterest", 0))
                return {"Bybit": oi}
        return {}

    async def _okx_oi(self, symbol: str) -> Dict[str, float]:
        inst_id = f"{symbol.upper()}-USDT-SWAP"
        data = await self._safe_get(
            f"{OKX_URL}/api/v5/public/open-interest",
            params={"instId": inst_id},
        )
        if data and isinstance(data, dict):
            entries = data.get("data", [])
            if entries:
                oi = float(entries[0].get("oi", 0))
                return {"OKX": oi}
        return {}

    # -- Liquidation (limited from free APIs) --------------------------------

    async def get_liquidation_snapshot(self, symbol: str) -> LiquidationSnapshot:
        """
        Free fallback for liquidation data.

        Public exchange APIs do not expose aggregated liquidation history,
        so this returns a minimal snapshot.  For full liquidation data,
        a CoinGlass API key is required.
        """
        # Binance has a forceOrders endpoint for recent liquidations
        pair = f"{symbol.upper()}USDT"
        data = await self._safe_get(
            f"{BINANCE_FUTURES_URL}/fapi/v1/allForceOrders",
            params={"symbol": pair, "limit": 100},
        )
        long_usd = 0.0
        short_usd = 0.0
        count = 0
        if data and isinstance(data, list):
            for order in data:
                qty = float(order.get("origQty", 0))
                px = float(order.get("averagePrice", 0) or order.get("price", 0))
                usd = qty * px
                side = order.get("side", "").upper()
                if side == "SELL":  # long liquidated
                    long_usd += usd
                else:
                    short_usd += usd
                count += 1

        return LiquidationSnapshot(
            symbol=symbol,
            timestamp=time.time(),
            window_seconds=3600,
            long_liquidations_usd=long_usd,
            short_liquidations_usd=short_usd,
            total_count=count,
            by_exchange={"Binance": long_usd + short_usd},
        )

    # -- Basis (free fallback) -----------------------------------------------

    async def get_basis_raw(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Compute basis from spot vs futures prices on Binance.

        Returns a list with a single dict for the current snapshot.
        """
        pair = f"{symbol.upper()}USDT"
        spot_data = await self._safe_get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": pair},
        )
        futures_data = await self._safe_get(
            f"{BINANCE_FUTURES_URL}/fapi/v1/premiumIndex",
            params={"symbol": pair},
        )
        if spot_data and futures_data:
            spot_px = float(spot_data.get("price", 0))
            mark_px = float(futures_data.get("markPrice", 0))
            if spot_px > 0:
                basis_pct = ((mark_px - spot_px) / spot_px) * 100.0
                return [
                    {
                        "symbol": symbol,
                        "exchange": "Binance",
                        "spotPrice": spot_px,
                        "futuresPrice": mark_px,
                        "basisPct": basis_pct,
                        "timestamp": time.time(),
                    }
                ]
        return []

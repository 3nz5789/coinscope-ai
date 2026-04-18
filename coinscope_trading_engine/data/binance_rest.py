"""
binance_rest.py — Binance Futures REST API Wrapper
====================================================
Async HTTP client for the Binance USD-M Futures REST API (fapi/v1 & v2).

Spec compliance
---------------
* Base URL (mainnet) : https://fapi.binance.com
* Base URL (testnet) : https://testnet.binancefuture.com
* Connectivity test  : GET /fapi/v1/ping  → {}
* Authentication     : HMAC-SHA256 signature on SIGNED endpoints
* Signature payload  : query-string params sorted alphabetically
* INT params         : sent as integers (not strings)
* DECIMAL params     : sent as strings (not floats)
* Timestamps         : milliseconds UTC
* Rate limits        : X-MBX-USED-WEIGHT-1M / X-MBX-ORDER-COUNT headers tracked

Security levels
---------------
* NONE   — public market data, no API key required
* USER_STREAM — only apiKey header, no signature
* SIGNED — apiKey header + timestamp + HMAC signature

Usage
-----
    from data.binance_rest import BinanceRESTClient

    async with BinanceRESTClient(testnet=True) as client:
        await client.ping()
        ticker = await client.get_ticker_price("BTCUSDT")
        klines = await client.get_klines("BTCUSDT", "5m", limit=100)
        acct   = await client.get_account()   # SIGNED
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REST_MAINNET_BASE = "https://fapi.binance.com"
REST_TESTNET_BASE = "https://testnet.binancefuture.com"

# Default recv window for signed requests (milliseconds)
DEFAULT_RECV_WINDOW = 5_000

# Retry config
MAX_RETRIES        = 3
RETRY_BACKOFF_S    = 0.5   # doubled each retry

# Rate-limit safety threshold — pause when weight usage >= this %
WEIGHT_THROTTLE_PCT = 85.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RateLimit:
    """Tracks the current request-weight consumption from response headers."""
    used_weight_1m: int  = 0
    order_count_1m: int  = 0
    order_count_10s: int = 0
    limit_weight_1m: int = 2400   # Binance default; updated from headers


@dataclass
class APIResponse:
    """Wraps a raw API result with metadata."""
    data:       Any
    status:     int
    headers:    dict
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Signature helper
# ---------------------------------------------------------------------------

def _sign(secret: str, params: dict[str, Any]) -> str:
    """HMAC-SHA256 of alphabetically-sorted key=value& payload."""
    payload = urlencode(sorted(params.items()))
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class BinanceRESTError(Exception):
    """Base error for all REST API failures."""
    def __init__(self, status: int, code: int, msg: str) -> None:
        self.status = status
        self.code   = code
        self.msg    = msg
        super().__init__(f"[HTTP {status}] Binance {code}: {msg}")


class RateLimitError(BinanceRESTError):
    """Raised on HTTP 429 / 418 — rate limit hit or IP ban."""
    pass


class AuthError(BinanceRESTError):
    """Raised on HTTP 401 / 403."""
    pass


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

class BinanceRESTClient:
    """
    Async REST client for Binance USD-M Futures.

    Parameters
    ----------
    testnet : bool, optional
        Uses testnet base URL when True. Defaults to ``settings.testnet_mode``.
    api_key : str, optional
        Overrides ``settings.active_api_key``.
    api_secret : str, optional
        Overrides ``settings.active_api_secret``.
    recv_window : int
        Milliseconds tolerance for signed request timestamps (default 5000).
    """

    def __init__(
        self,
        testnet: Optional[bool] = None,
        api_key: Optional[str]    = None,
        api_secret: Optional[str] = None,
        recv_window: int = DEFAULT_RECV_WINDOW,
    ) -> None:
        self._testnet     = testnet if testnet is not None else settings.testnet_mode
        self._api_key     = api_key     or settings.active_api_key.get_secret_value()
        self._api_secret  = api_secret  or settings.active_api_secret.get_secret_value()
        self._recv_window = recv_window
        self._base_url    = REST_TESTNET_BASE if self._testnet else REST_MAINNET_BASE

        self._session:    Optional[aiohttp.ClientSession] = None
        self.rate_limit   = RateLimit()

    # ── Context manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "BinanceRESTClient":
        await self._open_session()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def _open_session(self) -> None:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self._session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"X-MBX-APIKEY": self._api_key},
        )
        logger.info(
            "BinanceRESTClient ready [%s] → %s",
            "testnet" if self._testnet else "mainnet",
            self._base_url,
        )

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("BinanceRESTClient session closed.")

    # ── Core request engine ──────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        signed: bool = False,
        retries: int = MAX_RETRIES,
    ) -> Any:
        """
        Execute an HTTP request with retry logic and rate-limit tracking.

        Parameters
        ----------
        method : str     HTTP verb — "GET", "POST", "DELETE"
        path   : str     Endpoint path, e.g. "/fapi/v1/ping"
        params : dict    Query / body parameters
        signed : bool    If True, injects timestamp + signature
        retries: int     Number of retries on transient failures
        """
        if self._session is None:
            await self._open_session()

        req_params = dict(params or {})

        if signed:
            req_params["timestamp"]   = int(time.time() * 1000)
            req_params["recvWindow"]  = self._recv_window
            req_params["signature"]   = _sign(self._api_secret, req_params)

        url = f"{self._base_url}{path}"
        attempt = 0

        while attempt <= retries:
            t0 = time.monotonic()
            try:
                async with self._session.request(
                    method,
                    url,
                    params=req_params if method == "GET" else None,
                    data=req_params  if method != "GET" else None,
                ) as resp:
                    elapsed = (time.monotonic() - t0) * 1000
                    self._update_rate_limits(resp.headers)
                    body = await resp.json(content_type=None)

                    logger.debug(
                        "%s %s → %d  (%.0fms)  weight=%d",
                        method, path, resp.status, elapsed,
                        self.rate_limit.used_weight_1m,
                    )

                    if resp.status == 200:
                        return body

                    # --- Error handling by status code ---
                    code = body.get("code", -1) if isinstance(body, dict) else -1
                    msg  = body.get("msg",  "Unknown error") if isinstance(body, dict) else str(body)

                    if resp.status in (429, 418):
                        retry_after = int(resp.headers.get("Retry-After", 60))
                        logger.warning(
                            "Rate limit hit (HTTP %d) — backing off %ds",
                            resp.status, retry_after,
                        )
                        raise RateLimitError(resp.status, code, msg)

                    if resp.status in (401, 403):
                        raise AuthError(resp.status, code, msg)

                    # Transient 5xx — retry
                    if resp.status >= 500 and attempt < retries:
                        wait = RETRY_BACKOFF_S * (2 ** attempt)
                        logger.warning(
                            "Server error %d on %s — retry %d/%d in %.1fs",
                            resp.status, path, attempt + 1, retries, wait,
                        )
                        await asyncio.sleep(wait)
                        attempt += 1
                        continue

                    raise BinanceRESTError(resp.status, code, msg)

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt < retries:
                    wait = RETRY_BACKOFF_S * (2 ** attempt)
                    logger.warning(
                        "Network error on %s: %s — retry %d/%d in %.1fs",
                        path, exc, attempt + 1, retries, wait,
                    )
                    await asyncio.sleep(wait)
                    attempt += 1
                    continue
                raise

        raise BinanceRESTError(503, -1, f"Max retries ({retries}) exceeded for {path}")

    def _update_rate_limits(self, headers: Any) -> None:
        """Parse Binance rate-limit headers and update internal state."""
        try:
            if w := headers.get("X-MBX-USED-WEIGHT-1M"):
                self.rate_limit.used_weight_1m = int(w)
            if o := headers.get("X-MBX-ORDER-COUNT-1M"):
                self.rate_limit.order_count_1m = int(o)
            if o10 := headers.get("X-MBX-ORDER-COUNT-10S"):
                self.rate_limit.order_count_10s = int(o10)
        except (ValueError, TypeError):
            pass

    @property
    def is_throttled(self) -> bool:
        """True when weight usage is above the safety threshold."""
        if self.rate_limit.limit_weight_1m == 0:
            return False
        pct = (self.rate_limit.used_weight_1m / self.rate_limit.limit_weight_1m) * 100
        return pct >= WEIGHT_THROTTLE_PCT

    # ================================================================
    # ── PUBLIC ENDPOINTS (no auth required) ─────────────────────────
    # ================================================================

    # ── Connectivity ─────────────────────────────────────────────────

    async def ping(self) -> bool:
        """
        Test connectivity to the REST API.
        GET /fapi/v1/ping  → {}
        Weight: 1
        """
        await self._request("GET", "/fapi/v1/ping")
        logger.info("Binance REST ping OK [%s]", "testnet" if self._testnet else "mainnet")
        return True

    async def get_server_time(self) -> int:
        """
        Get Binance server time in milliseconds.
        GET /fapi/v1/time  → {"serverTime": 1499827319559}
        Weight: 1
        """
        result = await self._request("GET", "/fapi/v1/time")
        return result["serverTime"]

    async def get_exchange_info(self) -> dict:
        """
        Get exchange rules, symbol info, and rate limits.
        GET /fapi/v1/exchangeInfo
        Weight: 1
        """
        return await self._request("GET", "/fapi/v1/exchangeInfo")

    # ── Market data ───────────────────────────────────────────────────

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """
        Get order book depth snapshot.
        GET /fapi/v1/depth
        Weight: scales with limit (5→2, 10→5, 20→10, 50→20, 100→50, 500→10, 1000→20)

        Parameters
        ----------
        symbol : str  Trading pair, e.g. "BTCUSDT"
        limit  : int  Valid values: 5, 10, 20, 50, 100, 500, 1000 (default 20)
        """
        return await self._request(
            "GET", "/fapi/v1/depth",
            params={"symbol": symbol, "limit": limit},
        )

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> list[dict]:
        """
        Get recent trades.
        GET /fapi/v1/trades
        Weight: 5
        """
        return await self._request(
            "GET", "/fapi/v1/trades",
            params={"symbol": symbol, "limit": limit},
        )

    async def get_agg_trades(
        self,
        symbol: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
        from_id: Optional[int]    = None,
    ) -> list[dict]:
        """
        Get compressed/aggregated trades.
        GET /fapi/v1/aggTrades
        Weight: 20
        """
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        if from_id:    params["fromId"]    = from_id
        return await self._request("GET", "/fapi/v1/aggTrades", params=params)

    async def get_klines(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int    = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
    ) -> list[list]:
        """
        Get candlestick / OHLCV data.
        GET /fapi/v1/klines
        Weight: scales with limit

        Returns list of:
        [open_time, open, high, low, close, volume, close_time,
         quote_vol, trades, taker_buy_base_vol, taker_buy_quote_vol, ignore]
        """
        params: dict[str, Any] = {
            "symbol":   symbol,
            "interval": interval,
            "limit":    limit,
        }
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        return await self._request("GET", "/fapi/v1/klines", params=params)

    async def get_continuous_klines(
        self,
        pair: str,
        contract_type: str = "PERPETUAL",
        interval: str = "5m",
        limit: int    = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
    ) -> list[list]:
        """
        Get continuous contract klines.
        GET /fapi/v1/continuousKlines
        Weight: scales with limit
        """
        params: dict[str, Any] = {
            "pair":         pair,
            "contractType": contract_type,
            "interval":     interval,
            "limit":        limit,
        }
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        return await self._request("GET", "/fapi/v1/continuousKlines", params=params)

    async def get_mark_price(self, symbol: Optional[str] = None) -> dict | list[dict]:
        """
        Get mark price and funding rate.
        GET /fapi/v1/premiumIndex
        Weight: 1

        Returns a single dict if symbol is provided, list for all symbols.
        """
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v1/premiumIndex", params=params)

    async def get_funding_rate_history(
        self,
        symbol: str,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
    ) -> list[dict]:
        """
        Get historical funding rate data.
        GET /fapi/v1/fundingRate
        Weight: 1
        """
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        return await self._request("GET", "/fapi/v1/fundingRate", params=params)

    async def get_24h_ticker(self, symbol: Optional[str] = None) -> dict | list[dict]:
        """
        24-hour rolling window price change statistics.
        GET /fapi/v1/ticker/24hr
        Weight: 1 (single symbol) or 40 (all symbols)
        """
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v1/ticker/24hr", params=params)

    async def get_ticker_price(self, symbol: Optional[str] = None) -> dict | list[dict]:
        """
        Latest price for a symbol or all symbols.
        GET /fapi/v1/ticker/price
        Weight: 1 (single) or 2 (all)
        """
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v1/ticker/price", params=params)

    async def get_best_price(self, symbol: Optional[str] = None) -> dict | list[dict]:
        """
        Best price/qty on the order book (bid/ask).
        GET /fapi/v1/ticker/bookTicker
        Weight: 1 (single) or 2 (all)
        """
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v1/ticker/bookTicker", params=params)

    async def get_open_interest(self, symbol: str) -> dict:
        """
        Get current open interest for a symbol.
        GET /fapi/v1/openInterest
        Weight: 1
        """
        return await self._request(
            "GET", "/fapi/v1/openInterest", params={"symbol": symbol}
        )

    async def get_open_interest_history(
        self,
        symbol: str,
        period: str   = "5m",
        limit: int    = 30,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
    ) -> list[dict]:
        """
        Get open interest statistics history.
        GET /futures/data/openInterestHist
        Weight: 1
        """
        params: dict[str, Any] = {"symbol": symbol, "period": period, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        return await self._request("GET", "/futures/data/openInterestHist", params=params)

    async def get_long_short_ratio(
        self,
        symbol: str,
        period: str = "5m",
        limit: int  = 30,
    ) -> list[dict]:
        """
        Top trader long/short ratio (accounts).
        GET /futures/data/topLongShortAccountRatio
        Weight: 1
        """
        params: dict[str, Any] = {"symbol": symbol, "period": period, "limit": limit}
        return await self._request(
            "GET", "/futures/data/topLongShortAccountRatio", params=params
        )

    async def get_taker_long_short_ratio(
        self,
        symbol: str,
        period: str = "5m",
        limit: int  = 30,
    ) -> list[dict]:
        """
        Taker buy/sell volume ratio.
        GET /futures/data/takerlongshortRatio
        Weight: 1
        """
        return await self._request(
            "GET", "/futures/data/takerlongshortRatio",
            params={"symbol": symbol, "period": period, "limit": limit},
        )

    async def get_liquidation_orders(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
    ) -> list[dict]:
        """
        Get liquidation orders.
        GET /fapi/v1/allForceOrders
        Weight: 20 (with symbol) or 50 (all symbols)
        """
        params: dict[str, Any] = {"limit": limit}
        if symbol:     params["symbol"]    = symbol
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        return await self._request("GET", "/fapi/v1/allForceOrders", params=params)

    # ================================================================
    # ── SIGNED ENDPOINTS (require apiKey + signature) ────────────────
    # ================================================================

    async def get_account(self) -> dict:
        """
        Get current account information, balances, and positions.
        GET /fapi/v2/account  (SIGNED)
        Weight: 5
        """
        return await self._request("GET", "/fapi/v2/account", signed=True)

    async def get_balance(self) -> list[dict]:
        """
        Get account balance for all assets.
        GET /fapi/v2/balance  (SIGNED)
        Weight: 5
        """
        return await self._request("GET", "/fapi/v2/balance", signed=True)

    async def get_positions(self, symbol: Optional[str] = None) -> list[dict]:
        """
        Get current open positions.
        GET /fapi/v2/positionRisk  (SIGNED)
        Weight: 5
        """
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v2/positionRisk", params=params, signed=True)

    async def get_income_history(
        self,
        income_type: Optional[str] = None,
        symbol: Optional[str]      = None,
        limit: int                 = 100,
        start_time: Optional[int]  = None,
        end_time: Optional[int]    = None,
    ) -> list[dict]:
        """
        Get income/PnL history.
        GET /fapi/v1/income  (SIGNED)
        Weight: 30
        """
        params: dict[str, Any] = {"limit": limit}
        if income_type: params["incomeType"] = income_type
        if symbol:      params["symbol"]     = symbol
        if start_time:  params["startTime"]  = start_time
        if end_time:    params["endTime"]    = end_time
        return await self._request("GET", "/fapi/v1/income", params=params, signed=True)

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str]         = None,
        stop_price: Optional[str]    = None,
        time_in_force: str           = "GTC",
        reduce_only: bool            = False,
        position_side: str           = "BOTH",
        working_type: str            = "CONTRACT_PRICE",
        client_order_id: Optional[str] = None,
    ) -> dict:
        """
        Place a new order.
        POST /fapi/v1/order  (SIGNED)
        Weight: 1

        Parameters
        ----------
        symbol        : e.g. "BTCUSDT"
        side          : "BUY" | "SELL"
        order_type    : "LIMIT" | "MARKET" | "STOP" | "STOP_MARKET" |
                        "TAKE_PROFIT" | "TAKE_PROFIT_MARKET" | "TRAILING_STOP_MARKET"
        quantity      : Order quantity as string (DECIMAL rule)
        price         : Limit price as string  (required for LIMIT orders)
        stop_price    : Trigger price as string (required for STOP/TP orders)
        time_in_force : "GTC" | "IOC" | "FOK" | "GTX" (default GTC)
        reduce_only   : True to only reduce an existing position
        position_side : "BOTH" | "LONG" | "SHORT" (hedge mode)
        working_type  : "CONTRACT_PRICE" | "MARK_PRICE"
        client_order_id: Custom order ID (max 36 chars)
        """
        params: dict[str, Any] = {
            "symbol":       symbol,
            "side":         side,
            "type":         order_type,
            "quantity":     quantity,
            "timeInForce":  time_in_force,
            "reduceOnly":   str(reduce_only).lower(),
            "positionSide": position_side,
            "workingType":  working_type,
        }
        if price:            params["price"]           = price
        if stop_price:       params["stopPrice"]       = stop_price
        if client_order_id:  params["newClientOrderId"] = client_order_id

        return await self._request("POST", "/fapi/v1/order", params=params, signed=True)

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int]         = None,
        client_order_id: Optional[str]  = None,
    ) -> dict:
        """
        Cancel an open order.
        DELETE /fapi/v1/order  (SIGNED)
        Weight: 1
        """
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:         params["orderId"]            = order_id
        if client_order_id:  params["origClientOrderId"] = client_order_id
        return await self._request("DELETE", "/fapi/v1/order", params=params, signed=True)

    async def cancel_all_orders(self, symbol: str) -> dict:
        """
        Cancel all open orders for a symbol.
        DELETE /fapi/v1/allOpenOrders  (SIGNED)
        Weight: 1
        """
        return await self._request(
            "DELETE", "/fapi/v1/allOpenOrders",
            params={"symbol": symbol}, signed=True,
        )

    async def get_order(
        self,
        symbol: str,
        order_id: Optional[int]        = None,
        client_order_id: Optional[str] = None,
    ) -> dict:
        """
        Query a single order status.
        GET /fapi/v1/order  (SIGNED)
        Weight: 1
        """
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:         params["orderId"]           = order_id
        if client_order_id:  params["origClientOrderId"] = client_order_id
        return await self._request("GET", "/fapi/v1/order", params=params, signed=True)

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict]:
        """
        Get all currently open orders.
        GET /fapi/v1/openOrders  (SIGNED)
        Weight: 1 (single symbol) or 40 (all symbols)
        """
        params = {"symbol": symbol} if symbol else {}
        return await self._request("GET", "/fapi/v1/openOrders", params=params, signed=True)

    async def get_all_orders(
        self,
        symbol: str,
        limit: int = 500,
        order_id: Optional[int]    = None,
        start_time: Optional[int]  = None,
        end_time: Optional[int]    = None,
    ) -> list[dict]:
        """
        Get all account orders (active, cancelled, filled).
        GET /fapi/v1/allOrders  (SIGNED)
        Weight: 5
        """
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if order_id:    params["orderId"]   = order_id
        if start_time:  params["startTime"] = start_time
        if end_time:    params["endTime"]   = end_time
        return await self._request("GET", "/fapi/v1/allOrders", params=params, signed=True)

    async def change_leverage(self, symbol: str, leverage: int) -> dict:
        """
        Change initial leverage for a symbol.
        POST /fapi/v1/leverage  (SIGNED)
        Weight: 1
        """
        return await self._request(
            "POST", "/fapi/v1/leverage",
            params={"symbol": symbol, "leverage": leverage},
            signed=True,
        )

    async def change_margin_type(self, symbol: str, margin_type: str) -> dict:
        """
        Change margin type: "ISOLATED" or "CROSSED".
        POST /fapi/v1/marginType  (SIGNED)
        Weight: 1
        """
        return await self._request(
            "POST", "/fapi/v1/marginType",
            params={"symbol": symbol, "marginType": margin_type},
            signed=True,
        )

    async def get_user_trades(
        self,
        symbol: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int]   = None,
        from_id: Optional[int]    = None,
    ) -> list[dict]:
        """
        Get trade history for a symbol.
        GET /fapi/v1/userTrades  (SIGNED)
        Weight: 5
        """
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time:   params["endTime"]   = end_time
        if from_id:    params["fromId"]    = from_id
        return await self._request("GET", "/fapi/v1/userTrades", params=params, signed=True)

    # ── User Data Stream ──────────────────────────────────────────────

    async def create_listen_key(self) -> str:
        """
        Create a new User Data Stream listen key.
        POST /fapi/v1/listenKey  (USER_STREAM — no signature)
        Weight: 1
        Returns the listenKey string.
        """
        result = await self._request("POST", "/fapi/v1/listenKey")
        return result["listenKey"]

    async def keepalive_listen_key(self, listen_key: str) -> None:
        """
        Extend the validity of a listen key by 60 minutes.
        PUT /fapi/v1/listenKey  (USER_STREAM)
        Weight: 1
        """
        await self._request("PUT", "/fapi/v1/listenKey", params={"listenKey": listen_key})

    async def delete_listen_key(self, listen_key: str) -> None:
        """
        Close a User Data Stream.
        DELETE /fapi/v1/listenKey  (USER_STREAM)
        Weight: 1
        """
        await self._request("DELETE", "/fapi/v1/listenKey", params={"listenKey": listen_key})

    # ── Convenience helpers ───────────────────────────────────────────

    async def clock_skew_ms(self) -> int:
        """
        Return the difference between local time and Binance server time in ms.
        Positive = local clock is ahead of Binance.
        """
        server_time = await self.get_server_time()
        return int(time.time() * 1000) - server_time

    async def get_symbol_info(self, symbol: str) -> Optional[dict]:
        """
        Return exchange-info metadata for a single symbol, or None if not found.
        """
        info = await self.get_exchange_info()
        for sym in info.get("symbols", []):
            if sym["symbol"] == symbol:
                return sym
        return None

    async def get_min_notional(self, symbol: str) -> float:
        """
        Return the minimum notional value (price × qty) for a symbol.
        """
        sym_info = await self.get_symbol_info(symbol)
        if not sym_info:
            raise ValueError(f"Symbol {symbol!r} not found in exchange info.")
        for filt in sym_info.get("filters", []):
            if filt["filterType"] == "MIN_NOTIONAL":
                return float(filt["notional"])
        return 5.0  # Binance Futures default

    def __repr__(self) -> str:
        env = "testnet" if self._testnet else "mainnet"
        return (
            f"<BinanceRESTClient {env} "
            f"weight={self.rate_limit.used_weight_1m}/{self.rate_limit.limit_weight_1m}>"
        )

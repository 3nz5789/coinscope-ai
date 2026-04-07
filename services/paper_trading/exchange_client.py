"""
CoinScopeAI Paper Trading — Binance Futures Testnet REST Client
=================================================================
Handles all REST API interactions with Binance Futures Testnet.
TESTNET ONLY — mainnet endpoints are blocked at the config level.

Features:
- HMAC-SHA256 authentication
- Adaptive rate limiting with exponential backoff
- Automatic retry on transient errors
- Request/response logging for audit trail
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

from .config import (
    BINANCE_FUTURES_TESTNET_REST,
    ExchangeConfig,
    _BLOCKED_MAINNET_URLS,
)

logger = logging.getLogger("coinscopeai.paper_trading.exchange")


class ExchangeError(Exception):
    """Base exchange error."""
    def __init__(self, message: str, code: int = 0, response: str = ""):
        super().__init__(message)
        self.code = code
        self.response = response


class RateLimitError(ExchangeError):
    """Rate limit hit."""
    pass


class InsufficientBalanceError(ExchangeError):
    """Not enough margin/balance."""
    pass


@dataclass
class OrderResult:
    """Standardized order result."""
    order_id: int
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    price: float
    avg_price: float
    quantity: float
    executed_qty: float
    timestamp: int
    raw: Dict[str, Any]


class BinanceFuturesTestnetClient:
    """
    Binance Futures Testnet REST API client.

    All methods enforce testnet-only operation.
    Rate limiting is handled automatically.
    """

    # Rate limit: 2400 request weight per minute for futures
    MAX_REQUESTS_PER_MINUTE = 1200  # Conservative: 50% of limit
    MIN_REQUEST_INTERVAL = 0.05     # 50ms minimum between requests

    def __init__(self, config: Optional[ExchangeConfig] = None):
        self._config = config or ExchangeConfig()
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "CoinScopeAI-PaperTrading/1.0",
            "X-MBX-APIKEY": self._config.api_key,
        })
        self._last_request_time = 0.0
        self._request_count = 0
        self._minute_start = time.time()

        # Final safety check
        self._validate_testnet()

    def _validate_testnet(self):
        """Ensure we are connecting to testnet only."""
        for blocked in _BLOCKED_MAINNET_URLS:
            if blocked in self._config.rest_url:
                raise RuntimeError(f"BLOCKED: Mainnet URL detected: {blocked}")
        if "testnet" not in self._config.rest_url:
            raise RuntimeError(
                f"BLOCKED: URL does not contain 'testnet': {self._config.rest_url}"
            )

    def _sign(self, params: Dict) -> str:
        """Create HMAC-SHA256 signature."""
        query = urlencode(params)
        return hmac.new(
            self._config.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _rate_limit(self):
        """Enforce rate limiting."""
        now = time.time()

        # Reset counter every minute
        if now - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = now

        # Check rate limit
        if self._request_count >= self.MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (now - self._minute_start) + 1
            logger.warning("Rate limit approaching, sleeping %.1fs", sleep_time)
            time.sleep(sleep_time)
            self._request_count = 0
            self._minute_start = time.time()

        # Minimum interval
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = False,
        max_retries: int = 3,
    ) -> Any:
        """Execute HTTP request with retry and rate limiting."""
        params = params or {}
        url = f"{self._config.rest_url}{endpoint}"

        for attempt in range(max_retries):
            self._rate_limit()

            if signed:
                params["timestamp"] = int(time.time() * 1000)
                params["recvWindow"] = 5000
                # Remove old signature if retrying
                params.pop("signature", None)
                params["signature"] = self._sign(params)

            try:
                if method == "GET":
                    resp = self._session.get(url, params=params, timeout=10)
                elif method == "POST":
                    resp = self._session.post(url, params=params, timeout=10)
                elif method == "DELETE":
                    resp = self._session.delete(url, params=params, timeout=10)
                elif method == "PUT":
                    resp = self._session.put(url, params=params, timeout=10)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Rate limit response
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    logger.warning("Rate limited (429), retrying in %ds", retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code == 418:
                    logger.error("IP banned (418), waiting 120s")
                    time.sleep(120)
                    continue

                if resp.status_code >= 400:
                    body = resp.text
                    try:
                        err = resp.json()
                        code = err.get("code", resp.status_code)
                        msg = err.get("msg", body)
                    except Exception:
                        code = resp.status_code
                        msg = body

                    if code == -2019:
                        raise InsufficientBalanceError(msg, code, body)

                    # Retry on server errors
                    if resp.status_code >= 500 and attempt < max_retries - 1:
                        wait = 2 ** attempt
                        logger.warning("Server error %d, retrying in %ds", resp.status_code, wait)
                        time.sleep(wait)
                        continue

                    raise ExchangeError(msg, code, body)

                return resp.json()

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning("Request timeout, retrying in %ds", wait)
                    time.sleep(wait)
                    continue
                raise ExchangeError("Request timed out after all retries")

            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("Connection error, retrying in %ds: %s", wait, e)
                    time.sleep(wait)
                    continue
                raise ExchangeError(f"Connection failed: {e}")

        raise ExchangeError("Max retries exceeded")

    # ── Public Endpoints ──────────────────────────────────────

    def ping(self) -> bool:
        """Test connectivity."""
        self._request("GET", "/fapi/v1/ping")
        return True

    def get_server_time(self) -> int:
        """Get server timestamp in ms."""
        resp = self._request("GET", "/fapi/v1/time")
        return resp.get("serverTime", 0)

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict:
        """Get exchange trading rules."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/exchangeInfo", params)

    def get_ticker_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        resp = self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(resp.get("price", 0))

    def get_klines(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[List]:
        """Get kline/candlestick data."""
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        return self._request("GET", "/fapi/v1/klines", params)

    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get order book."""
        return self._request("GET", "/fapi/v1/depth", {"symbol": symbol, "limit": limit})

    # ── Account Endpoints (Signed) ────────────────────────────

    def get_account(self) -> Dict:
        """Get account information."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def get_balance(self) -> List[Dict]:
        """Get account balances."""
        return self._request("GET", "/fapi/v2/balance", signed=True)

    def get_usdt_balance(self) -> float:
        """Get available USDT balance."""
        balances = self.get_balance()
        for b in balances:
            if b.get("asset") == "USDT":
                return float(b.get("availableBalance", 0))
        return 0.0

    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        account = self.get_account()
        positions = []
        for pos in account.get("positions", []):
            amt = float(pos.get("positionAmt", 0))
            if amt != 0:
                positions.append(pos)
        return positions

    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for a specific symbol."""
        positions = self.get_positions()
        for pos in positions:
            if pos.get("symbol") == symbol:
                return pos
        return None

    # ── Order Endpoints (Signed) ──────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "MARKET",
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: Optional[str] = None,
        reduce_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Place an order on Binance Futures Testnet.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            side: BUY or SELL
            order_type: MARKET, LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET
            quantity: Order quantity
            price: Limit price (required for LIMIT orders)
            stop_price: Stop/trigger price
            time_in_force: GTC, IOC, FOK
            reduce_only: Close-only order
            client_order_id: Custom order ID
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
        }

        if quantity is not None:
            params["quantity"] = f"{quantity:.8f}".rstrip("0").rstrip(".")
        if price is not None:
            params["price"] = f"{price:.8f}".rstrip("0").rstrip(".")
        if stop_price is not None:
            params["stopPrice"] = f"{stop_price:.8f}".rstrip("0").rstrip(".")
        if time_in_force:
            params["timeInForce"] = time_in_force
        elif order_type.upper() == "LIMIT":
            params["timeInForce"] = "GTC"
        if reduce_only:
            params["reduceOnly"] = "true"
        if client_order_id:
            params["newClientOrderId"] = client_order_id

        logger.info("Placing order: %s", json.dumps(params, default=str))

        resp = self._request("POST", "/fapi/v1/order", params, signed=True)

        result = OrderResult(
            order_id=resp.get("orderId", 0),
            client_order_id=resp.get("clientOrderId", ""),
            symbol=resp.get("symbol", symbol),
            side=resp.get("side", side),
            order_type=resp.get("type", order_type),
            status=resp.get("status", "UNKNOWN"),
            price=float(resp.get("price", 0)),
            avg_price=float(resp.get("avgPrice", 0)),
            quantity=float(resp.get("origQty", 0)),
            executed_qty=float(resp.get("executedQty", 0)),
            timestamp=resp.get("updateTime", int(time.time() * 1000)),
            raw=resp,
        )

        logger.info(
            "Order placed: id=%d status=%s %s %s %s qty=%.6f price=%.2f",
            result.order_id, result.status, result.symbol,
            result.side, result.order_type, result.quantity, result.price,
        )

        return result

    def cancel_order(self, symbol: str, order_id: Optional[int] = None,
                     client_order_id: Optional[str] = None) -> Dict:
        """Cancel an open order."""
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        return self._request("DELETE", "/fapi/v1/order", params, signed=True)

    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all open orders for a symbol."""
        return self._request("DELETE", "/fapi/v1/allOpenOrders",
                             {"symbol": symbol}, signed=True)

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params, signed=True)

    def get_order(self, symbol: str, order_id: Optional[int] = None) -> Dict:
        """Get order status."""
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        return self._request("GET", "/fapi/v1/order", params, signed=True)

    # ── Leverage & Margin ─────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for a symbol."""
        return self._request("POST", "/fapi/v1/leverage",
                             {"symbol": symbol, "leverage": leverage}, signed=True)

    def set_margin_type(self, symbol: str, margin_type: str = "CROSSED") -> Dict:
        """Set margin type (ISOLATED or CROSSED)."""
        try:
            return self._request("POST", "/fapi/v1/marginType",
                                 {"symbol": symbol, "marginType": margin_type}, signed=True)
        except ExchangeError as e:
            # -4046 means margin type is already set
            if e.code == -4046:
                return {"msg": "No need to change margin type."}
            raise

    # ── Emergency ─────────────────────────────────────────────

    def close_all_positions(self) -> List[OrderResult]:
        """
        EMERGENCY: Close all open positions with market orders.
        This is the kill switch implementation at the exchange level.
        """
        results = []
        positions = self.get_positions()

        for pos in positions:
            symbol = pos["symbol"]
            amt = float(pos["positionAmt"])
            if amt == 0:
                continue

            side = "SELL" if amt > 0 else "BUY"
            qty = abs(amt)

            logger.warning(
                "KILL SWITCH: Closing %s position %s qty=%.6f",
                symbol, side, qty,
            )

            try:
                result = self.place_order(
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=qty,
                    reduce_only=True,
                )
                results.append(result)
            except Exception as e:
                logger.error("Failed to close %s: %s", symbol, e)

        # Cancel all open orders for all symbols
        for symbol in set(pos["symbol"] for pos in positions):
            try:
                self.cancel_all_orders(symbol)
            except Exception as e:
                logger.error("Failed to cancel orders for %s: %s", symbol, e)

        return results

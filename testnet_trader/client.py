"""
client.py — CoinScopeAI Binance Futures REST client.

Features:
  - Session-based HTTP with connection pooling
  - HMAC SHA256 signing for private (TRADE / USER_DATA) endpoints
  - Clock-drift correction: syncs against /fapi/v1/time at startup
  - Rate limit tracking from response headers (X-MBX-USED-WEIGHT-1M)
  - Explicit handling of 429, 418, and Binance API error codes
  - Testnet / mainnet URL driven by config — no hardcoding
"""

import hashlib
import hmac
import math
import time
from collections import deque

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import BinanceConfig


# ── Custom exceptions ─────────────────────────────────────────────────────────

class RateLimitError(Exception):
    def __init__(self, msg: str, retry_after: int = 60):
        super().__init__(msg)
        self.retry_after = retry_after

class BinanceAPIError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(f"Binance error {code}: {msg}")
        self.code = code
        self.msg  = msg

# Binance error codes that are safe to retry (transient)
RETRYABLE_CODES     = {-1001, -1007}
# Binance error codes that should never be retried (logic errors)
NON_RETRYABLE_CODES = {-1021, -1022, -2018, -2019}


# ── Rate limit tracker ────────────────────────────────────────────────────────

class RateLimitTracker:
    """
    Client-side rolling window tracker for all three Binance rate limit buckets.
    Proactively warns before hitting the server cap so we never get a 429.
    """

    WEIGHT_LIMIT_1M  = 2400   # request weight per minute per IP
    ORDER_LIMIT_10S  = 300    # orders per 10 seconds per account
    ORDER_LIMIT_1M   = 1200   # orders per minute per account
    SAFETY_BUFFER    = 0.90   # stay under 90% of limit to leave headroom

    def __init__(self):
        self._weights: deque = deque()   # (monotonic_ts, weight)
        self._orders:  deque = deque()   # (monotonic_ts, 1)

    def _prune(self, q: deque, window: float):
        cutoff = time.monotonic() - window
        while q and q[0][0] < cutoff:
            q.popleft()

    def record_weight(self, weight: int):
        self._weights.append((time.monotonic(), weight))

    def record_order(self):
        self._orders.append((time.monotonic(), 1))

    def used_weight_1m(self) -> int:
        self._prune(self._weights, 60)
        return sum(w for _, w in self._weights)

    def order_count_10s(self) -> int:
        self._prune(self._orders, 10)
        return len(self._orders)

    def order_count_1m(self) -> int:
        self._prune(self._orders, 60)
        return len(self._orders)

    def can_place_order(self) -> bool:
        return (
            self.order_count_10s() < self.ORDER_LIMIT_10S * self.SAFETY_BUFFER and
            self.order_count_1m()  < self.ORDER_LIMIT_1M  * self.SAFETY_BUFFER
        )

    def weight_ok(self, needed: int = 1) -> bool:
        return (self.used_weight_1m() + needed) < self.WEIGHT_LIMIT_1M * self.SAFETY_BUFFER

    def summary(self) -> str:
        return (
            f"weight={self.used_weight_1m()}/{self.WEIGHT_LIMIT_1M}  "
            f"orders_10s={self.order_count_10s()}  orders_1m={self.order_count_1m()}"
        )


# ── REST client ───────────────────────────────────────────────────────────────

class BinanceFuturesRestClient:
    """
    Full-featured Binance USDT-M Futures REST client.
    Accepts a BinanceConfig so it works identically on testnet and mainnet.
    """

    def __init__(self, cfg: BinanceConfig):
        self._base       = cfg.rest_url.rstrip("/")
        self._api_key    = cfg.api_key
        self._api_secret = cfg.api_secret
        self._ts_offset  = 0   # millisecond offset corrected at startup
        self.rate        = RateLimitTracker()

        # Session with connection pooling; retry only on server-side 5xx errors.
        # We handle 429 / 418 / API errors ourselves.
        self._session = requests.Session()
        self._session.headers.update({"X-MBX-APIKEY": self._api_key})
        adapter = HTTPAdapter(max_retries=Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE", "PUT"],
        ))
        self._session.mount("https://", adapter)

    # ── Clock sync ────────────────────────────────────────────────────────────

    def sync_clock(self) -> int:
        """
        Sync local clock against Binance server time.
        Call once at startup — fixes -1021 errors caused by VPS clock drift.
        Returns the offset in milliseconds.
        """
        data = self._session.get(f"{self._base}/fapi/v1/time", timeout=5).json()
        server_ms   = data["serverTime"]
        local_ms    = int(time.time() * 1000)
        self._ts_offset = server_ms - local_ms
        print(f"[Client] Clock synced. Offset: {self._ts_offset:+d} ms")
        return self._ts_offset

    # ── Signing ───────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        """
        Append timestamp + recvWindow + HMAC SHA256 signature to params.
        Must be called LAST — after all other params are set — because
        parameter order is part of what gets signed.
        """
        params["timestamp"]  = int(time.time() * 1000) + self._ts_offset
        params["recvWindow"] = 10000   # 10s window; generous enough for most VPS setups
        query = "&".join(f"{k}={v}" for k, v in params.items())
        params["signature"] = hmac.new(
            self._api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        return params

    # ── Core request dispatcher ───────────────────────────────────────────────

    def _req(self, method: str, path: str, signed: bool = False, **kwargs) -> dict:
        params = kwargs.pop("params", {})
        if signed:
            params = self._sign(params)

        resp = self._session.request(
            method, f"{self._base}{path}",
            params=params, timeout=10, **kwargs
        )

        # Update our rate limit tracker from the response header
        w = resp.headers.get("X-MBX-USED-WEIGHT-1M")
        if w:
            self.rate.record_weight(int(w))

        # Hard rate limit hits
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            raise RateLimitError(f"429 rate limit — retry after {wait}s", wait)
        if resp.status_code == 418:
            wait = int(resp.headers.get("Retry-After", 120))
            raise RateLimitError(f"418 IP ban — retry after {wait}s", wait)

        resp.raise_for_status()
        data = resp.json()

        # Binance API-level errors come back as 200 with a negative code field
        if isinstance(data, dict) and data.get("code", 0) < 0:
            raise BinanceAPIError(data["code"], data.get("msg", "unknown"))

        return data

    # ── Public endpoints (no auth needed) ─────────────────────────────────────

    def get_exchange_info(self, symbol: str = None) -> dict:
        """Symbol filters (stepSize, tickSize, minNotional). Weight: 1."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._req("GET", "/fapi/v1/exchangeInfo", params=params)

    def get_mark_price(self, symbol: str) -> dict:
        """Current mark price + funding rate. Weight: 1."""
        return self._req("GET", "/fapi/v1/premiumIndex", params={"symbol": symbol.upper()})

    def get_klines(self, symbol: str, interval: str, limit: int = 3) -> list:
        """OHLCV klines. Weight: 1."""
        return self._req("GET", "/fapi/v1/klines", params={
            "symbol": symbol.upper(), "interval": interval, "limit": limit,
        })

    # ── Private endpoints (signed) ─────────────────────────────────────────────

    def get_account(self) -> dict:
        """Account summary including availableBalance. Weight: 5."""
        return self._req("GET", "/fapi/v2/account", signed=True)

    def get_positions(self, symbol: str = None) -> list:
        """Open positions. Weight: 5."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._req("GET", "/fapi/v2/positionRisk", signed=True, params=params)

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage (1–125x). Weight: 1."""
        return self._req("POST", "/fapi/v1/leverage", signed=True, params={
            "symbol": symbol.upper(), "leverage": leverage,
        })

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> dict:
        """Set ISOLATED or CROSSED margin. Weight: 1."""
        try:
            return self._req("POST", "/fapi/v1/marginType", signed=True, params={
                "symbol": symbol.upper(), "marginType": margin_type.upper(),
            })
        except BinanceAPIError as e:
            # -4046 means margin type is already set — not a real error
            if e.code == -4046:
                print(f"[Client] Margin type already {margin_type} for {symbol} — skipping.")
                return {}
            raise

    def place_order(
        self,
        symbol:        str,
        side:          str,          # "BUY" | "SELL"
        order_type:    str,          # "MARKET" | "LIMIT" | "STOP_MARKET" | "TAKE_PROFIT_MARKET"
        quantity:      float,
        price:         float = None,
        stop_price:    float = None,
        reduce_only:   bool  = False,
        time_in_force: str   = "GTC",
    ) -> dict:
        """
        Place a Futures order. Weight: 1 (also counts against order-rate limits).
        Caller is responsible for rounding quantity/price to stepSize/tickSize first.
        """
        if not self.rate.can_place_order():
            raise RateLimitError("Order rate limit approaching — slow down", retry_after=5)

        params = {
            "symbol":       symbol.upper(),
            "side":         side.upper(),
            "type":         order_type.upper(),
            "quantity":     quantity,
            "positionSide": "BOTH",   # one-way mode; change to LONG/SHORT for hedge mode
        }
        if order_type.upper() == "LIMIT":
            params["price"]       = price
            params["timeInForce"] = time_in_force
        if stop_price is not None:
            params["stopPrice"] = stop_price
        if reduce_only:
            params["reduceOnly"] = "true"

        result = self._req("POST", "/fapi/v1/order", signed=True, params=params)
        self.rate.record_order()
        return result

    def cancel_all_orders(self, symbol: str) -> dict:
        """Cancel all open orders for a symbol. Weight: 1."""
        return self._req("DELETE", "/fapi/v1/allOpenOrders", signed=True, params={
            "symbol": symbol.upper(),
        })

    # ── Symbol filter helpers ─────────────────────────────────────────────────

    def get_symbol_filters(self, symbol: str) -> dict:
        """
        Returns a dict with the most useful filter values for a symbol:
            step_size     — quantity rounding unit (LOT_SIZE)
            tick_size     — price rounding unit (PRICE_FILTER)
            min_notional  — minimum order value in USDT (MIN_NOTIONAL)
            qty_precision — decimal places for quantity
            price_precision — decimal places for price
        """
        info = self.get_exchange_info(symbol)
        sym_info = next(
            (s for s in info["symbols"] if s["symbol"] == symbol.upper()), None
        )
        if not sym_info:
            raise ValueError(f"Symbol {symbol} not found in exchange info")

        result = {}
        for f in sym_info["filters"]:
            if f["filterType"] == "LOT_SIZE":
                result["step_size"]      = float(f["stepSize"])
                result["qty_precision"]  = _decimal_places(f["stepSize"])
            elif f["filterType"] == "PRICE_FILTER":
                result["tick_size"]        = float(f["tickSize"])
                result["price_precision"]  = _decimal_places(f["tickSize"])
            elif f["filterType"] == "MIN_NOTIONAL":
                result["min_notional"] = float(f.get("notional", f.get("minNotional", 5.0)))
        return result

    def round_quantity(self, quantity: float, filters: dict) -> float:
        """Floor quantity to the nearest stepSize to avoid -1013 errors."""
        step = filters["step_size"]
        prec = filters["qty_precision"]
        return round(math.floor(quantity / step) * step, prec)

    def round_price(self, price: float, filters: dict) -> float:
        """Floor price to the nearest tickSize to avoid -4014 errors."""
        tick = filters["tick_size"]
        prec = filters["price_precision"]
        return round(math.floor(price / tick) * tick, prec)


def _decimal_places(s: str) -> int:
    """Count decimal places in a string like '0.010' → 2, '1' → 0."""
    s = s.rstrip("0")
    return len(s.split(".")[-1]) if "." in s else 0

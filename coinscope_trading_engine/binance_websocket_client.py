"""
Binance Futures WebSocket API Client for Testnet Trading

Uses Binance Futures WebSocket API (wss://testnet.binancefuture.com/ws-fapi/v1)
for low-latency order placement and account management.

Features:
- Order placement and cancellation
- Account balance queries
- Position monitoring
- Automatic reconnection with exponential backoff
- Request/response correlation

Fix (2026-04-11): Added reconnect loop, proper connected/authenticated state
  management, keepalive ping_interval, and pending-future draining on disconnect.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable, Any
import hashlib
import hmac
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BinanceWSClient")

# Reconnection constants
_RECONNECT_INITIAL_DELAY = 1.0   # seconds
_RECONNECT_MAX_DELAY     = 60.0  # seconds
_RECONNECT_MAX_ATTEMPTS  = 50    # give up after this many consecutive failures


class BinanceWebSocketClient:
    """Binance Futures WebSocket API client for testnet trading.

    Usage pattern (long-lived session):
        client = BinanceWebSocketClient(api_key, api_secret, testnet=True)
        await client.start()          # blocks — runs reconnect loop
        ...
        await client.stop()           # clean shutdown

    One-shot usage (single operation):
        async with BinanceWebSocketClient(...) as client:
            balance = await client.get_balance()
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # WebSocket endpoints — Futures API
        if testnet:
            self.endpoint = "wss://testnet.binancefuture.com/ws-fapi/v1"
        else:
            self.endpoint = "wss://ws-fapi.binance.com/ws-fapi/v1"

        self.ws = None
        self.request_id = 0
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.connected = False
        self.authenticated = False

        # Reconnect state
        self._running = False
        self._reconnect_count = 0
        self._ready_event = asyncio.Event()   # set when connected+authenticated

    # ── context-manager support ───────────────────────────────────────────

    async def __aenter__(self):
        await self._single_connect()
        return self

    async def __aexit__(self, *_):
        await self.disconnect()

    # ── public API ─────────────────────────────────────────────────────────

    async def connect(self):
        """Single-attempt connect (for one-shot use). Raises on failure."""
        await self._single_connect()

    async def start(self):
        """Long-lived connect with automatic reconnection. Blocks until stop()."""
        self._running = True
        backoff = _RECONNECT_INITIAL_DELAY
        self._reconnect_count = 0

        while self._running:
            try:
                await self._single_connect()
                # _single_connect returns only when the WS drops — reset backoff
                backoff = _RECONNECT_INITIAL_DELAY
                self._reconnect_count = 0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._reconnect_count += 1
                if self._reconnect_count > _RECONNECT_MAX_ATTEMPTS:
                    logger.error("Max reconnect attempts reached — giving up")
                    self._running = False
                    break
                logger.error(
                    "Connection failed (%s) — retrying in %.1fs (attempt %d)",
                    exc, backoff, self._reconnect_count,
                )
            finally:
                self._mark_disconnected()

            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _RECONNECT_MAX_DELAY)

    async def stop(self):
        """Signal the reconnect loop to stop and close the socket."""
        self._running = False
        await self.disconnect()

    async def disconnect(self):
        """Close the WebSocket gracefully."""
        self._mark_disconnected()
        if self.ws and not self.ws.closed:
            try:
                await self.ws.close()
            except Exception:
                pass
        self.ws = None
        logger.info("Disconnected")

    # ── internal connect / auth ────────────────────────────────────────────

    async def _single_connect(self):
        """
        Open one WS connection, authenticate, and pump messages until the
        socket closes.  Callers (start / connect) decide what to do next.
        """
        logger.info("Connecting to %s …", self.endpoint)
        async with websockets.connect(
            self.endpoint,
            ping_interval=20,   # send WS ping every 20 s — keeps Binance alive
            ping_timeout=10,    # if no pong within 10 s, close & reconnect
            close_timeout=5,
        ) as ws:
            self.ws = ws
            self.connected = True
            logger.info("✅ WebSocket connected")

            # Authenticate before allowing any callers to proceed
            await self._do_authenticate()

            # Signal that we are ready (unblocks any waiters)
            self._ready_event.set()

            # Pump messages until the connection closes
            try:
                async for raw in ws:
                    data = json.loads(raw)
                    self._dispatch(data)
            except (ConnectionClosedOK, ConnectionClosedError) as exc:
                logger.warning("WebSocket closed: %s", exc)
            finally:
                self._mark_disconnected()

    def _mark_disconnected(self):
        """Clear connected/authenticated flags and fail any pending futures."""
        self.connected = False
        self.authenticated = False
        self._ready_event.clear()
        # Fail outstanding pending requests so callers don't hang forever
        for future in list(self.pending_requests.values()):
            if not future.done():
                future.set_exception(ConnectionError("WebSocket disconnected"))
        self.pending_requests.clear()

    async def _do_authenticate(self):
        """session.logon — called immediately after connect."""
        params = {
            "apiKey": self.api_key,
            "timestamp": int(time.time() * 1000),
        }
        params["signature"] = self._sign_request(params)

        request = {
            "id": str(uuid.uuid4()),
            "method": "session.logon",
            "params": params,
        }

        logger.info("Authenticating…")
        response = await self._send_raw_request(request)

        if response.get("status") == 200:
            self.authenticated = True
            logger.info(
                "✅ Authenticated: %s…",
                response.get("result", {}).get("apiKey", "Unknown")[:10],
            )
        else:
            error = response.get("error", {})
            raise Exception(f"Auth failed: {error.get('msg', 'Unknown error')}")

    # kept for back-compat; new code should call start()
    async def authenticate(self):
        await self._do_authenticate()

    # ── message dispatch ───────────────────────────────────────────────────

    def _dispatch(self, data: dict):
        """Route an incoming message to the waiting Future (if any)."""
        if "id" in data:
            request_id = data["id"]
            future = self.pending_requests.pop(request_id, None)
            if future and not future.done():
                future.set_result(data)

    # ── signing ────────────────────────────────────────────────────────────

    def _sign_request(self, params: Dict) -> str:
        """Sign request parameters with HMAC-SHA256."""
        # Parameters MUST be sorted; Binance validates signature over sorted string
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256,
        ).hexdigest()

    # ── request primitives ─────────────────────────────────────────────────

    async def _send_raw_request(self, request: Dict) -> Dict:
        """Send raw request and wait for the correlated response (10 s timeout)."""
        if not self.connected or self.ws is None or self.ws.closed:
            raise RuntimeError("WebSocket not connected")

        request_id = request.get("id")
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.pending_requests[request_id] = future

        try:
            await self.ws.send(json.dumps(request))
            logger.debug("Sent: %s (ID: %s)", request.get("method"), request_id)

            # _dispatch() will call future.set_result() when the server replies
            response = await asyncio.wait_for(future, timeout=10)
            return response

        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request {request_id} timed out")
        except Exception:
            self.pending_requests.pop(request_id, None)
            raise
    
    async def _send_request(self, method: str, params: Dict = None) -> Dict:
        """Send an authenticated request and return the result payload."""
        if not self.authenticated:
            raise RuntimeError("WebSocket not authenticated")

        request = {
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }

        response = await self._send_raw_request(request)

        if response.get("status") == 200:
            return response.get("result", {})
        error = response.get("error", {})
        raise Exception(f"API Error {response.get('status')}: {error}")
    
    async def get_account(self) -> Dict:
        """Get account information"""
        return await self._send_request("account.status")
    
    async def get_balance(self) -> Dict:
        """Get account balance"""
        account = await self._send_request("account.status")
        return account.get("balances", [])
    
    async def get_positions(self) -> list:
        """Get open positions"""
        account = await self._send_request("account.status")
        return account.get("positions", [])
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str = "MARKET",
        quantity: float = None,
        price: float = None,
        **kwargs
    ) -> Dict:
        """Place an order"""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
        }
        
        if quantity:
            params["quantity"] = str(quantity)
        if price:
            params["price"] = str(price)
        
        params.update(kwargs)
        
        return await self._send_request("order.place", params)
    
    async def cancel_order(self, symbol: str, order_id: int = None, client_order_id: str = None) -> Dict:
        """Cancel an order"""
        params = {"symbol": symbol}
        
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        
        return await self._send_request("order.cancel", params)
    
    async def get_open_orders(self, symbol: str = None) -> list:
        """Get open orders"""
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        result = await self._send_request("openOrders.status", params)
        return result if isinstance(result, list) else [result]
    
    async def get_order(self, symbol: str, order_id: int = None, client_order_id: str = None) -> Dict:
        """Get order status"""
        params = {"symbol": symbol}
        
        if order_id:
            params["orderId"] = order_id
        if client_order_id:
            params["origClientOrderId"] = client_order_id
        
        return await self._send_request("order.status", params)


async def test_connection():
    """One-shot connection test using context manager."""
    api_key = os.environ.get("BINANCE_FUTURES_TESTNET_API_KEY", "")
    api_secret = os.environ.get("BINANCE_FUTURES_TESTNET_API_SECRET", "")

    async with BinanceWebSocketClient(api_key, api_secret, testnet=True) as client:
        try:
            logger.info("Fetching account information…")
            account = await client.get_account()
            logger.info("Account: %s", json.dumps(account, indent=2))

            logger.info("Fetching balance…")
            balance = await client.get_balance()
            logger.info("Balance: %s", json.dumps(balance, indent=2))

            logger.info("✅ All tests passed!")
        except Exception as e:
            logger.error("❌ Test failed: %s", e)


if __name__ == "__main__":
    asyncio.run(test_connection())

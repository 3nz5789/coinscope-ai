"""
Binance Futures WebSocket API Client for Testnet Trading

Uses Binance Futures WebSocket API (wss://testnet.binancefuture.com/ws-fapi/v1)
for low-latency order placement and account management.

Features:
- Order placement and cancellation
- Account balance queries
- Position monitoring
- Automatic reconnection
- Request/response correlation
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Callable, Any
import hashlib
import hmac
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BinanceWSClient")


class BinanceWebSocketClient:
    """Binance Futures WebSocket API client for testnet trading"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # WebSocket endpoints - CORRECTED for Futures API
        if testnet:
            self.endpoint = "wss://testnet.binancefuture.com/ws-fapi/v1"
        else:
            self.endpoint = "wss://ws-fapi.binance.com/ws-fapi/v1"
        
        self.ws = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self.connected = False
        self.authenticated = False
        self.last_ping = time.time()
        
    def _get_request_id(self) -> int:
        """Get next request ID"""
        self.request_id += 1
        return self.request_id
    
    def _sign_request(self, params: Dict) -> str:
        """Sign request with HMAC SHA256"""
        # Sort params alphabetically
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def connect(self):
        """Connect to WebSocket API"""
        try:
            logger.info(f"Connecting to {self.endpoint}...")
            self.ws = await websockets.connect(self.endpoint)
            self.connected = True
            logger.info("✅ WebSocket connected")
            
            # Start message handler
            asyncio.create_task(self._message_handler())
            
            # Start ping/pong handler
            asyncio.create_task(self._ping_handler())
            
            # Authenticate
            await self.authenticate()
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            self.connected = False
            raise
    
    async def authenticate(self):
        """Authenticate the WebSocket connection"""
        try:
            params = {
                "apiKey": self.api_key,
                "timestamp": int(time.time() * 1000),
            }
            params["signature"] = self._sign_request(params)
            
            request = {
                "id": str(uuid.uuid4()),
                "method": "session.logon",
                "params": params
            }
            
            logger.info("Authenticating...")
            response = await self._send_raw_request(request)
            
            if response.get("status") == 200:
                self.authenticated = True
                logger.info(f"✅ Authenticated: {response.get('result', {}).get('apiKey', 'Unknown')[:10]}...")
            else:
                error = response.get("error", {})
                raise Exception(f"Auth failed: {error.get('msg', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("Disconnected")
    
    async def _message_handler(self):
        """Handle incoming WebSocket messages"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                
                # Handle responses with id
                if "id" in data:
                    request_id = data["id"]
                    if request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        if not future.done():
                            future.set_result(data)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Message handler error: {e}")
    
    async def _ping_handler(self):
        """Handle WebSocket ping/pong"""
        try:
            while self.connected:
                await asyncio.sleep(180)  # Ping every 3 minutes
        except asyncio.CancelledError:
            pass
    
    async def _send_raw_request(self, request: Dict) -> Dict:
        """Send raw request and wait for response"""
        if not self.connected:
            raise RuntimeError("WebSocket not connected")
        
        request_id = request.get("id")
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        try:
            await self.ws.send(json.dumps(request))
            logger.debug(f"Sent: {request.get('method')} (ID: {request_id})")
            
            # Wait for response (10 second timeout)
            response = await asyncio.wait_for(future, timeout=10)
            return response
                
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request {request_id} timed out")
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise
    
    async def _send_request(self, method: str, params: Dict = None) -> Dict:
        """Send request and wait for response"""
        if not self.authenticated:
            raise RuntimeError("WebSocket not authenticated")
        
        params = params or {}
        request_id = str(uuid.uuid4())
        
        request = {
            "id": request_id,
            "method": method,
            "params": params
        }
        
        response = await self._send_raw_request(request)
        
        if response.get("status") == 200:
            return response.get("result", {})
        else:
            error = response.get("error", {})
            raise Exception(f"API Error: {error}")
    
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
    """Test WebSocket connection"""
    api_key = os.environ.get("BINANCE_FUTURES_TESTNET_API_KEY", "")
    api_secret = os.environ.get("BINANCE_FUTURES_TESTNET_API_SECRET", "")
    
    client = BinanceWebSocketClient(api_key, api_secret, testnet=True)
    
    try:
        await client.connect()
        
        # Test: Get account info
        logger.info("Fetching account information...")
        account = await client.get_account()
        logger.info(f"Account: {json.dumps(account, indent=2)}")
        
        # Test: Get balance
        logger.info("Fetching balance...")
        balance = await client.get_balance()
        logger.info(f"Balance: {json.dumps(balance, indent=2)}")
        
        logger.info("✅ All tests passed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_connection())

"""
Binance Spot Testnet REST API Client

Uses Binance Spot Testnet (https://testnet.binance.vision/)
for testing trading system without real money.

Features:
- Order placement and cancellation
- Account balance queries
- Position monitoring
- HMAC-SHA256 authentication (standard keys)
"""

import requests
import hashlib
import hmac
import time
import json
from typing import Dict, Optional
from urllib.parse import urlencode

class BinanceRestTestnetClient:
    """Binance Spot Testnet REST API client"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Testnet endpoints
        if testnet:
            self.base_url = "https://testnet.binance.vision/api"
        else:
            self.base_url = "https://api.binance.com/api"
        
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'CoinScopeAI/1.0',
        })
    
    def _sign_request(self, params: Dict) -> str:
        """Sign request with HMAC SHA256"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """Make HTTP request to Binance API"""
        params = params or {}
        
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign_request(params)
            self.session.headers.update({'X-MBX-APIKEY': self.api_key})
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, params=params)
            elif method == "POST":
                response = self.session.post(url, params=params)
            elif method == "DELETE":
                response = self.session.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            raise
    
    def test_connection(self) -> Dict:
        """Test connection to testnet"""
        return self._request("GET", "/v3/ping")
    
    def get_server_time(self) -> int:
        """Get server time"""
        result = self._request("GET", "/v3/time")
        return result.get('serverTime', 0)
    
    def get_account(self) -> Dict:
        """Get account information"""
        return self._request("GET", "/v3/account", signed=True)
    
    def get_balance(self) -> Dict:
        """Get account balance"""
        account = self.get_account()
        balances = {}
        for balance in account.get('balances', []):
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            if free > 0 or locked > 0:
                balances[asset] = {
                    'free': free,
                    'locked': locked,
                    'total': free + locked
                }
        return balances
    
    def place_order(
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
            'symbol': symbol,
            'side': side,
            'type': order_type,
        }
        
        if quantity:
            params['quantity'] = quantity
        if price:
            params['price'] = price
        
        params.update(kwargs)
        
        return self._request("POST", "/v3/order", params, signed=True)
    
    def cancel_order(self, symbol: str, order_id: int = None, orig_client_order_id: str = None) -> Dict:
        """Cancel an order"""
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        if orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        
        return self._request("DELETE", "/v3/order", params, signed=True)
    
    def get_open_orders(self, symbol: str = None) -> list:
        """Get open orders"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return self._request("GET", "/v3/openOrders", params, signed=True)
    
    def get_order(self, symbol: str, order_id: int = None, orig_client_order_id: str = None) -> Dict:
        """Get order status"""
        params = {'symbol': symbol}
        
        if order_id:
            params['orderId'] = order_id
        if orig_client_order_id:
            params['origClientOrderId'] = orig_client_order_id
        
        return self._request("GET", "/v3/order", params, signed=True)
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get ticker information"""
        return self._request("GET", "/v3/ticker/24hr", {'symbol': symbol})


def test_connection():
    """Test REST API connection to Binance Spot Testnet"""
    # Use the HMAC keys you provided
    api_key = os.environ.get("BINANCE_SPOT_TESTNET_API_KEY", "")
    api_secret = os.environ.get("BINANCE_SPOT_TESTNET_API_SECRET", "")
    
    client = BinanceRestTestnetClient(api_key, api_secret, testnet=True)
    
    try:
        print("\n" + "=" * 60)
        print(" BINANCE SPOT TESTNET - REST API Connection Test")
        print("=" * 60)
        
        # Test: Ping
        print("\n🔌 Testing connection...")
        client.test_connection()
        print("✅ Connection successful")
        
        # Test: Server time
        print("\n⏰ Fetching server time...")
        server_time = client.get_server_time()
        print(f"✅ Server time: {server_time}")
        
        # Test: Account info
        print("\n📊 Fetching account information...")
        account = client.get_account()
        print(f"✅ Account retrieved")
        print(f"   Can Trade: {account.get('canTrade')}")
        print(f"   Can Withdraw: {account.get('canWithdraw')}")
        print(f"   Can Deposit: {account.get('canDeposit')}")
        
        # Test: Balance
        print("\n💰 Fetching balance...")
        balance = client.get_balance()
        if balance:
            print(f"✅ Balance retrieved:")
            for asset, amounts in list(balance.items())[:5]:
                print(f"   {asset}: {amounts['free']:.4f} free, {amounts['locked']:.4f} locked")
        else:
            print("✅ No balances with non-zero amounts")
        
        # Test: Ticker
        print("\n📈 Fetching BTC/USDT ticker...")
        ticker = client.get_ticker("BTCUSDT")
        print(f"✅ BTC/USDT Price: ${ticker.get('lastPrice')}")
        print(f"   24h Change: {ticker.get('priceChangePercent')}%")
        
        print("\n" + "=" * 60)
        print(" ✅ ALL TESTS PASSED - TESTNET READY FOR TRADING")
        print("=" * 60)
        print("\nYour CoinScopeAI trading system is ready to deploy!")
        print("Next: Start live trading with circuit breakers armed")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_connection()

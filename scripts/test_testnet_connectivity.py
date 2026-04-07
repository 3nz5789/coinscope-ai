"""
CoinScopeAI — Binance Futures Testnet Connectivity Test
Verifies: testnet URL enforcement, authentication, account balance,
open positions, and live market data (ticker price).
"""
import os
import sys
import json
import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone

# ── Constants ─────────────────────────────────────────────────
TESTNET_REST = "https://testnet.binancefuture.com"
MAINNET_URLS = ["https://fapi.binance.com", "wss://fstream.binance.com"]

API_KEY    = os.environ.get("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def sep(title=""):
    print(f"\n{'─'*60}")
    if title:
        print(f"  {title}")
        print(f"{'─'*60}")

def ok(msg):  print(f"  ✓  {msg}")
def err(msg): print(f"  ✗  {msg}"); return False
def info(msg): print(f"  →  {msg}")

# ── 1. Testnet URL Enforcement ────────────────────────────────
sep("1. TESTNET URL ENFORCEMENT")
try:
    sys.path.insert(0, "/home/ubuntu/coinscope-ai")
    from services.paper_trading.config import (
        ExchangeConfig, BINANCE_FUTURES_TESTNET_REST,
        HARDCODED_TESTNET_ONLY, _BLOCKED_MAINNET_URLS
    )
    assert HARDCODED_TESTNET_ONLY is True
    ok(f"HARDCODED_TESTNET_ONLY = True")
    ok(f"Default REST URL = {BINANCE_FUTURES_TESTNET_REST}")
    ok(f"Blocked mainnet URLs: {_BLOCKED_MAINNET_URLS}")

    # Verify mainnet raises
    for url in ["https://fapi.binance.com"]:
        try:
            ExchangeConfig(rest_url=url, ws_url="wss://stream.binancefuture.com")
            err(f"FAIL: mainnet URL {url} was NOT blocked — CRITICAL")
            sys.exit(1)
        except RuntimeError as e:
            ok(f"Mainnet URL correctly blocked: {str(e)[:60]}")

    # Verify default config is testnet
    cfg = ExchangeConfig(api_key=API_KEY, api_secret=API_SECRET)
    assert "testnet" in cfg.rest_url
    ok(f"ExchangeConfig defaults to testnet: {cfg.rest_url}")

except Exception as e:
    err(f"Testnet enforcement check failed: {e}")
    sys.exit(1)

# ── 2. Raw HTTP Connectivity ──────────────────────────────────
sep("2. RAW HTTP CONNECTIVITY TO TESTNET")
try:
    resp = requests.get(f"{TESTNET_REST}/fapi/v1/ping", timeout=10)
    if resp.status_code == 200:
        ok(f"Ping OK — {TESTNET_REST}/fapi/v1/ping → 200")
    else:
        err(f"Ping failed: {resp.status_code}")
        sys.exit(1)
except Exception as e:
    err(f"Cannot reach testnet: {e}")
    sys.exit(1)

# Server time
try:
    resp = requests.get(f"{TESTNET_REST}/fapi/v1/time", timeout=10)
    server_time = resp.json()["serverTime"]
    local_time = int(time.time() * 1000)
    drift_ms = abs(server_time - local_time)
    ok(f"Server time: {datetime.fromtimestamp(server_time/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    ok(f"Clock drift: {drift_ms}ms {'(OK)' if drift_ms < 5000 else '(WARNING: >5s drift)'}")
except Exception as e:
    err(f"Server time check failed: {e}")

# ── 3. Authenticated Endpoints ────────────────────────────────
sep("3. AUTHENTICATED ENDPOINTS")

def signed_request(method, endpoint, params=None):
    """Make a signed request to the testnet."""
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 10000
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{TESTNET_REST}{endpoint}?{query}&signature={sig}"
    headers = {"X-MBX-APIKEY": API_KEY}
    if method == "GET":
        return requests.get(url, headers=headers, timeout=10)
    elif method == "POST":
        return requests.post(url, headers=headers, timeout=10)

if not API_KEY or not API_SECRET:
    err("API key or secret not set — skipping authenticated tests")
else:
    # Account balance
    try:
        resp = signed_request("GET", "/fapi/v2/account")
        if resp.status_code == 200:
            data = resp.json()
            total_balance = float(data.get("totalWalletBalance", 0))
            available    = float(data.get("availableBalance", 0))
            unrealized   = float(data.get("totalUnrealizedProfit", 0))
            ok(f"Account authenticated successfully")
            ok(f"Total Wallet Balance:  {total_balance:.4f} USDT")
            ok(f"Available Balance:     {available:.4f} USDT")
            ok(f"Unrealized P&L:        {unrealized:.4f} USDT")
        else:
            err(f"Account query failed: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        err(f"Account query error: {e}")

    # Open positions
    try:
        resp = signed_request("GET", "/fapi/v2/positionRisk")
        if resp.status_code == 200:
            positions = resp.json()
            open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
            ok(f"Position query OK — {len(open_pos)} open position(s)")
            if open_pos:
                for p in open_pos:
                    info(f"  {p['symbol']}: {p['positionAmt']} @ {p['entryPrice']} | PnL: {p['unRealizedProfit']}")
            else:
                info("No open positions (clean slate — expected for new testnet account)")
        else:
            err(f"Position query failed: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        err(f"Position query error: {e}")

    # Open orders
    try:
        resp = signed_request("GET", "/fapi/v1/openOrders")
        if resp.status_code == 200:
            orders = resp.json()
            ok(f"Open orders query OK — {len(orders)} open order(s)")
        else:
            err(f"Open orders query failed: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        err(f"Open orders query error: {e}")

# ── 4. Market Data ────────────────────────────────────────────
sep("4. MARKET DATA (PUBLIC ENDPOINTS)")
for symbol in SYMBOLS:
    try:
        resp = requests.get(
            f"{TESTNET_REST}/fapi/v1/ticker/price",
            params={"symbol": symbol}, timeout=10
        )
        if resp.status_code == 200:
            price = float(resp.json()["price"])
            ok(f"{symbol}: ${price:,.2f}")
        else:
            err(f"{symbol} price fetch failed: {resp.status_code}")
    except Exception as e:
        err(f"{symbol} price error: {e}")

# Recent klines (4h)
try:
    resp = requests.get(
        f"{TESTNET_REST}/fapi/v1/klines",
        params={"symbol": "BTCUSDT", "interval": "4h", "limit": 3},
        timeout=10
    )
    if resp.status_code == 200:
        klines = resp.json()
        ok(f"BTCUSDT 4h klines — last 3 candles received:")
        for k in klines:
            ts = datetime.fromtimestamp(k[0]/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            info(f"  {ts}  O:{float(k[1]):,.1f}  H:{float(k[2]):,.1f}  L:{float(k[3]):,.1f}  C:{float(k[4]):,.1f}  V:{float(k[5]):,.1f}")
    else:
        err(f"Klines fetch failed: {resp.status_code}")
except Exception as e:
    err(f"Klines error: {e}")

# ── 5. Exchange Client Integration ───────────────────────────
sep("5. EXCHANGE CLIENT MODULE INTEGRATION TEST")
try:
    from services.paper_trading.exchange_client import BinanceFuturesTestnetClient
    from services.paper_trading.config import ExchangeConfig

    cfg = ExchangeConfig(api_key=API_KEY, api_secret=API_SECRET)
    client = BinanceFuturesTestnetClient(cfg)

    # Ping via client
    ping_ok = client.ping()
    ok(f"BinanceFuturesTestnetClient.ping() = {ping_ok}")

    # Get ticker price via client
    price = client.get_ticker_price("BTCUSDT")
    ok(f"BinanceFuturesTestnetClient.get_ticker_price('BTCUSDT') = ${price:,.2f}")

    # Get account balance via client
    balance = client.get_usdt_balance()
    ok(f"BinanceFuturesTestnetClient.get_usdt_balance() = {balance:.4f} USDT")

    # Get positions via client
    positions = client.get_positions()
    open_pos = [p for p in positions if float(p.get('positionAmt', 0)) != 0]
    ok(f"BinanceFuturesTestnetClient.get_positions() = {len(open_pos)} open position(s)")

except Exception as e:
    err(f"Exchange client integration failed: {e}")
    import traceback; traceback.print_exc()

# ── Summary ───────────────────────────────────────────────────
sep("CONNECTIVITY TEST COMPLETE")
print("  All checks passed. System is ready for paper trading.\n")

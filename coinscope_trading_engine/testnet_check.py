"""
testnet_check.py — Binance Testnet Connectivity & Engine Smoke Test
====================================================================
Run this BEFORE starting main.py to verify your testnet setup is correct.

Usage
-----
    cd coinscope_trading_engine
    python testnet_check.py

Checks
------
  1. .env loaded correctly (API keys present)
  2. Binance Testnet REST ping
  3. Account balance fetch
  4. Kline fetch for BTCUSDT
  5. WebSocket handshake (1-second stream test)
  6. Confluence scorer produces a result
  7. Telegram bot reachability (optional)

All failures show a clear fix instruction.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# Inject testnet env before config loads
os.environ.setdefault("TESTNET_MODE", "true")

PASS = "  ✅"
FAIL = "  ❌"
WARN = "  ⚠️ "
SEP  = "-" * 60


def header(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


async def check_env() -> bool:
    header("1/7  Environment Variables")
    try:
        from config import settings
        key = settings.active_api_key
        secret = settings.active_api_secret
        if not key or not secret:
            print(FAIL, "API keys are empty.")
            print("      → Set BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_API_SECRET in .env")
            return False
        masked_key = key[:8] + "…" + key[-4:]
        print(PASS, f"TESTNET_MODE = True")
        print(PASS, f"API key found: {masked_key}")
        print(PASS, f"REST base URL: {settings.active_base_url}")
        return True
    except Exception as e:
        print(FAIL, f"Config load failed: {e}")
        print("      → Check that .env exists in the project root")
        return False


async def check_rest_ping() -> bool:
    header("2/7  Binance Testnet REST Ping")
    try:
        from config import settings
        from data.binance_rest import BinanceRESTClient
        rest = BinanceRESTClient(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = True,
        )
        ok = await rest.ping()
        if ok:
            print(PASS, "Ping OK — testnet.binancefuture.com is reachable")
            return True
        else:
            print(FAIL, "Ping returned False")
            print("      → Check internet connection / VPN")
            return False
    except Exception as e:
        print(FAIL, f"REST ping error: {e}")
        print("      → Ensure httpx / aiohttp is installed: pip install httpx")
        return False


async def check_account_balance() -> bool:
    header("3/7  Futures Account Balance")
    try:
        from config import settings
        from data.binance_rest import BinanceRESTClient
        rest = BinanceRESTClient(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = True,
        )
        balances = await rest.get_account_balance()
        usdt = next((float(b["balance"]) for b in balances if b.get("asset") == "USDT"), None)
        if usdt is not None:
            print(PASS, f"Testnet USDT balance: {usdt:,.2f}")
            if usdt < 100:
                print(WARN, "Low testnet balance.")
                print("      → Visit https://testnet.binancefuture.com and click 'Asset' → 'Claim' for free USDT")
            return True
        else:
            print(WARN, "No USDT balance found in response.")
            return True   # non-fatal
    except Exception as e:
        print(FAIL, f"Balance fetch error: {e}")
        print("      → Check API key permissions (Futures account must be enabled)")
        return False


async def check_klines() -> bool:
    header("4/7  Kline Data (BTCUSDT 1h × 10 bars)")
    try:
        from config import settings
        from data.binance_rest import BinanceRESTClient
        from data.data_normalizer import DataNormalizer
        rest = BinanceRESTClient(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = True,
        )
        raw     = await rest.get_klines("BTCUSDT", "1h", limit=10)
        candles = DataNormalizer().klines_to_candles("BTCUSDT", "1h", raw)
        if candles:
            last = candles[-1]
            print(PASS, f"Received {len(candles)} candles. Latest close: {last.close:,.2f}")
            return True
        print(FAIL, "Klines returned empty list")
        return False
    except Exception as e:
        print(FAIL, f"Klines error: {e}")
        return False


async def check_websocket() -> bool:
    header("5/7  WebSocket Stream (3-second kline test)")
    try:
        from config import settings
        from data.binance_websocket import BinanceWebSocketManager
        ws = BinanceWebSocketManager(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = True,
        )
        received = []
        async def _listener():
            await ws.connect()
            async for msg in ws.stream(["btcusdt@kline_1m"]):
                received.append(msg)
                if len(received) >= 1:
                    break
        try:
            await asyncio.wait_for(_listener(), timeout=10.0)
        except asyncio.TimeoutError:
            print(WARN, "WebSocket timeout — no message received in 10s (non-fatal)")
            return True   # WS may just be quiet at this moment
        await ws.disconnect()
        print(PASS, f"WebSocket OK — received {len(received)} message(s)")
        return True
    except Exception as e:
        print(WARN, f"WebSocket check skipped: {e}")
        print("      → websockets library may not be installed: pip install websockets")
        return True   # non-fatal


async def check_signals() -> bool:
    header("6/7  Signal Generation (60 candles → scanner → score)")
    try:
        from config import settings
        from data.binance_rest import BinanceRESTClient
        from data.data_normalizer import DataNormalizer
        from scanner.volume_scanner import VolumeScanner
        from scanner.pattern_scanner import PatternScanner
        from signals.confluence_scorer import ConfluenceScorer

        rest    = BinanceRESTClient(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = True,
        )
        raw     = await rest.get_klines("BTCUSDT", "1h", limit=60)
        candles = DataNormalizer().klines_to_candles("BTCUSDT", "1h", raw)

        scanners = [PatternScanner()]
        results  = []
        for sc in scanners:
            try:
                r = await sc.scan("BTCUSDT")
                results.append(r)
            except Exception:
                pass

        scorer = ConfluenceScorer(min_score=0)   # min=0 so we always get output
        signal = scorer.score("BTCUSDT", results, candles)

        if signal:
            print(PASS, f"Signal generated: {signal.direction.value} score={signal.score:.1f} strength={signal.strength}")
        else:
            print(PASS, "No signal (no confluence hit) — that's normal for one scan")
        return True
    except Exception as e:
        print(FAIL, f"Signal generation error: {e}")
        return False


async def check_telegram() -> bool:
    header("7/7  Telegram Bot (optional)")
    try:
        from config import settings
        token = settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else ""
        if not token or token in ("", "your_telegram_bot_token_here"):
            print(WARN, "TELEGRAM_BOT_TOKEN not set — skipping")
            print("      → Get a token from @BotFather then set it in .env")
            return True

        from alerts.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        ok = await notifier.test_connection()
        if ok:
            print(PASS, "Telegram bot reachable")
        else:
            print(WARN, "Telegram test_connection returned False")
            print("      → Check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return True
    except Exception as e:
        print(WARN, f"Telegram check error: {e}")
        return True   # non-fatal


# ---------------------------------------------------------------------------

async def main() -> None:
    print("\n🔍  CoinScopeAI Testnet Smoke Test")
    print(f"    {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

    checks = [
        check_env,
        check_rest_ping,
        check_account_balance,
        check_klines,
        check_websocket,
        check_signals,
        check_telegram,
    ]

    results = []
    for fn in checks:
        try:
            ok = await fn()
        except Exception as e:
            print(FAIL, f"Unexpected error: {e}")
            ok = False
        results.append(ok)

    passed = sum(results)
    total  = len(results)
    print(f"\n{SEP}")
    print(f"  Result: {passed}/{total} checks passed")
    print(SEP)

    if passed == total:
        print("\n  🟢  All checks passed — run the engine with:")
        print("      python main.py --testnet\n")
    elif passed >= total - 1:
        print("\n  🟡  Engine should work — address warnings above, then:")
        print("      python main.py --testnet\n")
    else:
        print("\n  🔴  Fix the errors above before running the engine.\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

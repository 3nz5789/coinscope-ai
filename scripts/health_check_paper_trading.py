"""
CoinScopeAI — Paper Trading Full Health Check
Tests all components before starting the engine:
- Exchange client (REST + authenticated)
- Safety gate initialization
- Signal engine (model loading)
- Alerting system
- Order manager
- Risk gate state
"""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/coinscope-ai")

API_KEY    = os.environ.get("BINANCE_TESTNET_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_TESTNET_API_SECRET", "")
TG_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")

results = []

def sep(title):
    print(f"\n{'─'*60}\n  {title}\n{'─'*60}")

def chk(label, passed, detail=""):
    status = "✓" if passed else "✗"
    msg = f"  {status}  {label}"
    if detail:
        msg += f"\n     → {detail}"
    print(msg)
    results.append((label, passed))
    return passed

# ── 1. Exchange Client ────────────────────────────────────────
sep("1. EXCHANGE CLIENT")
try:
    from services.paper_trading.config import ExchangeConfig
    from services.paper_trading.exchange_client import BinanceFuturesTestnetClient

    cfg = ExchangeConfig(api_key=API_KEY, api_secret=API_SECRET)
    client = BinanceFuturesTestnetClient(cfg)

    chk("Config loads with testnet URL", "testnet" in cfg.rest_url, cfg.rest_url)
    chk("Ping testnet", client.ping())

    server_time = client.get_server_time()
    drift = abs(server_time - int(time.time() * 1000))
    chk("Clock drift < 1000ms", drift < 1000, f"{drift}ms")

    balance = client.get_usdt_balance()
    chk("USDT balance query", balance >= 0, f"{balance:.4f} USDT")

    btc_price = client.get_ticker_price("BTCUSDT")
    chk("BTCUSDT ticker price", btc_price > 0, f"${btc_price:,.2f}")

    klines = client.get_klines("BTCUSDT", "4h", limit=10)
    chk("BTCUSDT 4h klines (10 candles)", len(klines) == 10, f"{len(klines)} candles received")

    positions = client.get_positions()
    open_pos = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
    chk("Position risk query", True, f"{len(open_pos)} open positions")

    open_orders = client.get_open_orders()
    chk("Open orders query", True, f"{len(open_orders)} open orders")

    # Exchange info
    info = client.get_exchange_info("BTCUSDT")
    chk("Exchange info (BTCUSDT)", "symbol" in info or "symbols" in info)

except Exception as e:
    chk("Exchange client initialization", False, str(e))
    import traceback; traceback.print_exc()

# ── 2. Safety Gate ────────────────────────────────────────────
sep("2. SAFETY GATE")
try:
    from services.paper_trading.config import TradingConfig, HARDCODED_TESTNET_ONLY
    from services.paper_trading.safety import SafetyGate, KillSwitch

    chk("HARDCODED_TESTNET_ONLY = True", HARDCODED_TESTNET_ONLY is True)

    trading_cfg = TradingConfig(
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        timeframe="4h",
    )
    chk("TradingConfig clamped to hardcoded limits",
        trading_cfg.leverage <= 5,
        f"leverage={trading_cfg.leverage}, max_dd={trading_cfg.max_drawdown_pct:.0%}")

    safety = SafetyGate(trading_cfg)
    status = safety.get_status()
    chk("SafetyGate initialized", isinstance(status, dict) and "kill_switch" in status)
    chk("Kill switch not triggered", not status["kill_switch"]["active"])
    chk("Daily loss within limits", status["daily_loss_pct"] == 0.0)
    chk("Drawdown within limits", status["drawdown_pct"] == 0.0)

    # Test kill switch
    ks = KillSwitch()
    chk("KillSwitch not triggered at start", not ks.is_active)

except Exception as e:
    chk("Safety gate initialization", False, str(e))
    safety = None  # ensure variable exists for later sections
    trading_cfg = None
    import traceback; traceback.print_exc()

# ── 3. Signal Engine (Model Loading) ─────────────────────────
sep("3. SIGNAL ENGINE (ML MODELS)")
try:
    from services.paper_trading.signal_engine import MLSignalEngine
    from pathlib import Path

    models_dir = Path("/home/ubuntu/coinscope-ai/models")
    model_files = list(models_dir.glob("**/*.joblib")) if models_dir.exists() else []
    chk("Models directory exists", models_dir.exists(), str(models_dir))
    chk("Trained model files found", len(model_files) > 0, f"{len(model_files)} .joblib files")

    if model_files:
        # List available v2 4h models
        v2_4h_models = [f for f in model_files if "v2" in str(f) and "4h" in str(f)]
        chk("v2 4h models available", len(v2_4h_models) > 0,
            f"{len(v2_4h_models)} v2 4h models found")

        # Try loading the signal engine with a v2 model
        import joblib
        btc_model_path = models_dir / "v2" / "logreg_BTCUSDT_4h.joblib"
        chk("BTCUSDT 4h LogReg model exists", btc_model_path.exists(), str(btc_model_path))

        if btc_model_path.exists():
            import pandas as pd
            engine = MLSignalEngine()
            engine.load_model(str(btc_model_path))
            chk("MLSignalEngine loads BTCUSDT model", engine._model is not None)

            # Initialize buffer for BTCUSDT with empty DataFrame
            engine.initialize_buffer("BTCUSDT", pd.DataFrame())
            chk("Candle buffer initialized for BTCUSDT",
                "BTCUSDT" in engine._buffers,
                f"buffer size: {len(engine._buffers.get('BTCUSDT', []))} candles")

except Exception as e:
    chk("Signal engine initialization", False, str(e))
    import traceback; traceback.print_exc()

# ── 4. Alerting System ────────────────────────────────────────
sep("4. ALERTING SYSTEM")
try:
    from services.paper_trading.config import TelegramConfig
    from services.paper_trading.alerting import TelegramAlerter

    tg_cfg = TelegramConfig(
        bot_token=TG_TOKEN,
        chat_id="0",
        enabled=bool(TG_TOKEN and TG_TOKEN != "your-telegram-bot-token-here"),
    )
    alerter = TelegramAlerter(tg_cfg)
    stats = alerter.get_stats()

    chk("TelegramAlerter instantiated", True)
    chk("Alerter enabled status",
        True,  # Just check it has a valid state
        f"enabled={stats['enabled']} (token {'valid' if tg_cfg.enabled else 'placeholder — alerts disabled'})")

    if not tg_cfg.enabled:
        print("     → NOTE: Telegram token is placeholder. Alerts will be logged locally only.")
        print("       Set TELEGRAM_BOT_TOKEN to a real bot token to enable Telegram notifications.")

except Exception as e:
    chk("Alerting system initialization", False, str(e))

# ── 5. ORDER MANAGER ─────────────────────────────────────────
sep("5. ORDER MANAGER")
try:
    from services.paper_trading.order_manager import OrderManager

    if safety is None or trading_cfg is None:
        raise RuntimeError("Safety gate failed to initialize — skipping order manager test")

    om = OrderManager(
        exchange=client,
        safety=safety,
        config=trading_cfg,
    )
    chk("OrderManager instantiated", True)
    chk("No open positions in order manager", len(om.positions) == 0)
    chk("No pending orders", len(om.open_orders) == 0)

    summary = om.get_portfolio_summary()
    chk("Portfolio summary available",
        "open_positions" in summary,
        f"positions={summary.get('open_positions', 0)}, equity={summary.get('total_unrealized_pnl', 0):.2f} USDT unrealized PnL")

except Exception as e:
    chk("Order manager initialization", False, str(e))
    import traceback; traceback.print_exc()

# ── 6. Live Market Data Spot Check ───────────────────────────
sep("6. LIVE MARKET DATA SPOT CHECK")
try:
    symbols_to_check = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
    for sym in symbols_to_check:
        try:
            price = client.get_ticker_price(sym)
            chk(f"{sym} live price", price > 0, f"${price:,.4f}")
        except Exception as e:
            chk(f"{sym} live price", False, str(e))

except Exception as e:
    chk("Market data spot check", False, str(e))

# ── Summary ───────────────────────────────────────────────────
sep("HEALTH CHECK SUMMARY")
passed = sum(1 for _, p in results if p)
failed = sum(1 for _, p in results if not p)
total  = len(results)
print(f"  Passed: {passed}/{total}")
print(f"  Failed: {failed}/{total}")
if failed > 0:
    print(f"\n  Failed checks:")
    for label, p in results:
        if not p:
            print(f"    ✗  {label}")
print()
if failed == 0:
    print("  ✓  ALL CHECKS PASSED — System ready to start paper trading.\n")
    sys.exit(0)
else:
    print(f"  ✗  {failed} CHECK(S) FAILED — Review issues before starting engine.\n")
    sys.exit(1)

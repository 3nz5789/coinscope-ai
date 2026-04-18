"""
config.py — CoinScopeAI Binance Futures environment configuration.

Controls testnet vs mainnet via a single env var (BINANCE_TESTNET).
All modules import `load_config()` — never hardcode URLs or keys.

Usage:
    from config import load_config, startup_check
    cfg = load_config()
    startup_check(cfg)
"""

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv  # pip install python-dotenv

# Load .env file from the current working directory (or project root)
load_dotenv()


@dataclass
class BinanceConfig:
    rest_url:   str
    ws_url:     str
    api_key:    str
    api_secret: str
    is_testnet: bool


def load_config() -> BinanceConfig:
    """
    Build config from environment variables.

    Required .env vars:
        BINANCE_API_KEY      — API key (testnet or mainnet, must match BINANCE_TESTNET)
        BINANCE_API_SECRET   — API secret
        BINANCE_TESTNET      — "true" for paper trading, "false" (default) for live

    Optional .env vars:
        RISK_PCT             — % of balance to risk per trade  (default: 1.0)
        LEVERAGE             — futures leverage per trade       (default: 10)
        SL_PCT               — stop-loss % distance            (default: 1.5)
        RR_RATIO             — reward:risk ratio for TP        (default: 2.0)
    """
    is_testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"

    if is_testnet:
        rest_url = "https://testnet.binancefuture.com"
        ws_url   = "wss://stream.binancefuture.com"
    else:
        rest_url = "https://fapi.binance.com"
        ws_url   = "wss://fstream.binance.com"

    api_key    = os.getenv("BINANCE_API_KEY",    "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")

    if not api_key or not api_secret:
        raise EnvironmentError(
            "\n[Config] BINANCE_API_KEY and BINANCE_API_SECRET must be set.\n"
            "Copy .env.example to .env and fill in your testnet keys.\n"
            "Get them from: https://testnet.binancefuture.com"
        )

    env_label = "TESTNET ⚠️  (paper money)" if is_testnet else "MAINNET 🔴 (REAL FUNDS)"
    print(f"\n[Config] ══════════════════════════════════════")
    print(f"[Config]  Environment : {env_label}")
    print(f"[Config]  REST URL    : {rest_url}")
    print(f"[Config]  WS URL      : {ws_url}")
    print(f"[Config] ══════════════════════════════════════\n")

    return BinanceConfig(
        rest_url=rest_url,
        ws_url=ws_url,
        api_key=api_key,
        api_secret=api_secret,
        is_testnet=is_testnet,
    )


def startup_check(cfg: BinanceConfig) -> None:
    """
    Guard against accidentally running on mainnet during development.
    On testnet: prints a green confirmation and continues.
    On mainnet: requires the user to type 'MAINNET' to proceed.
    """
    if cfg.is_testnet:
        print("[Startup] ✅ Testnet confirmed — no real funds at risk.\n")
        return

    # Mainnet: make the user explicitly acknowledge
    print("\n" + "!" * 60)
    print("  ⚠️  WARNING: MAINNET MODE")
    print("  Real funds are at risk. Every order is live.")
    print("!" * 60)
    confirm = input("\nType 'MAINNET' to confirm you intend to trade live: ").strip()
    if confirm != "MAINNET":
        print("[Startup] Aborted — type exactly 'MAINNET' to proceed on live.")
        sys.exit(0)
    print("[Startup] Mainnet confirmed by user. Proceeding with caution.\n")


# ── Trade parameters (loaded from env so you can override without changing code) ─

def trade_params() -> dict:
    """Risk/sizing parameters — all overridable via .env."""
    return {
        "risk_pct":  float(os.getenv("RISK_PCT",  "1.0")),   # % of balance per trade
        "leverage":  int(os.getenv("LEVERAGE",    "10")),     # futures leverage
        "sl_pct":    float(os.getenv("SL_PCT",    "1.5")),    # stop-loss % from entry
        "rr_ratio":  float(os.getenv("RR_RATIO",  "2.0")),    # reward:risk (TP = SL * rr)
    }

"""
config.py — Binance Futures environment config for the Funding Rate Pipeline.

Reads from environment variables (or a .env file loaded by the caller).
Toggle between testnet (safe) and mainnet (real funds) via BINANCE_TESTNET.

Usage:
    from data.funding_rates.config import load_config
    cfg = load_config()
"""

import os
from dataclasses import dataclass, field


# ── Binance URLs ───────────────────────────────────────────────────────────────

MAINNET_REST_URL = "https://fapi.binance.com"
MAINNET_WS_URL   = "wss://fstream.binance.com"

TESTNET_REST_URL = "https://testnet.binancefuture.com"
TESTNET_WS_URL   = "wss://stream.binancefuture.com"

# ── Funding Rate Alert Thresholds ─────────────────────────────────────────────

# Funding rate is expressed as a decimal (e.g. 0.001 = 0.1%)
FUNDING_RATE_WARNING  = 0.001   # |rate| > 0.1%  → warning alert
FUNDING_RATE_CRITICAL = 0.003   # |rate| > 0.3%  → critical alert

# Alert cooldown per symbol — prevents spam on sustained extreme rates
ALERT_COOLDOWN_SECONDS = 3600   # 1 hour between repeated alerts per symbol

# ── Pipeline Timings ──────────────────────────────────────────────────────────

REST_BOOTSTRAP_INTERVAL = 300   # Re-sync full snapshot via REST every 5 min (seconds)
SNAPSHOT_SAVE_INTERVAL  = 3600  # Save hourly snapshot to history table (seconds)

# ── Storage ───────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "funding_rates.db")


@dataclass
class FundingRateConfig:
    rest_url:      str
    ws_url:        str
    api_key:       str
    api_secret:    str
    is_testnet:    bool
    telegram_token: str = ""
    telegram_chat_id: str = ""
    db_path:       str = DB_PATH


def load_config(dotenv_path: str = None) -> FundingRateConfig:
    """
    Load configuration from environment variables.

    If dotenv_path is provided, loads that file first.
    Falls back to reading from the process environment.

    Required env vars:
        BINANCE_API_KEY      — Binance Futures API key
        BINANCE_API_SECRET   — Binance Futures API secret
        BINANCE_TESTNET      — "true" for testnet (default), "false" for mainnet

    Optional env vars:
        TELEGRAM_BOT_TOKEN   — Telegram bot token for alerts
        TELEGRAM_CHAT_ID     — Telegram chat ID for alerts
    """
    # Load .env file if specified or auto-discover from project root
    _load_dotenv(dotenv_path)

    is_testnet = os.getenv("BINANCE_TESTNET", "true").lower() != "false"

    if is_testnet:
        rest_url = TESTNET_REST_URL
        ws_url   = TESTNET_WS_URL
    else:
        rest_url = MAINNET_REST_URL
        ws_url   = MAINNET_WS_URL

    api_key    = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")

    # API keys are required even for public market data streams
    # (rate limit tracking works best with authenticated identity)
    if not api_key:
        raise EnvironmentError(
            "BINANCE_API_KEY is not set.\n"
            "Create a .env file in the project root with:\n"
            "  BINANCE_API_KEY=your_testnet_key\n"
            "  BINANCE_API_SECRET=your_testnet_secret\n"
            "  BINANCE_TESTNET=true\n"
            "Get testnet keys at: https://testnet.binancefuture.com"
        )

    cfg = FundingRateConfig(
        rest_url      = rest_url,
        ws_url        = ws_url,
        api_key       = api_key,
        api_secret    = api_secret,
        is_testnet    = is_testnet,
        telegram_token   = os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", ""),
    )

    _print_banner(cfg)
    return cfg


def _print_banner(cfg: FundingRateConfig) -> None:
    env_label = "TESTNET ✅ (paper trading)" if cfg.is_testnet else "MAINNET 🔴 (REAL FUNDS)"
    print("=" * 60)
    print(f"  CoinScopeAI — Funding Rate Pipeline")
    print(f"  Environment : {env_label}")
    print(f"  REST URL    : {cfg.rest_url}")
    print(f"  WS URL      : {cfg.ws_url}")
    print(f"  Telegram    : {'enabled' if cfg.telegram_token else 'disabled'}")
    print(f"  DB Path     : {cfg.db_path}")
    print("=" * 60)


def _load_dotenv(dotenv_path: str = None) -> None:
    """
    Minimal .env loader — avoids requiring python-dotenv as a hard dependency.
    Loads KEY=VALUE pairs, strips quotes and comments.
    """
    search_paths = [dotenv_path] if dotenv_path else [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    ]

    for path in search_paths:
        if path and os.path.isfile(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key   = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Don't override already-set env vars
                    if key and key not in os.environ:
                        os.environ[key] = value
            break  # Stop after first found .env

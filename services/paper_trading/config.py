"""
CoinScopeAI Paper Trading — Configuration
============================================
All configuration with conservative defaults.
Safety limits are HARDCODED and non-configurable.
"""

import os
from dataclasses import dataclass, field
from typing import List


# ═══════════════════════════════════════════════════════════════════
# HARDCODED SAFETY LIMITS — NON-BYPASSABLE, NON-CONFIGURABLE
# These exist to prevent catastrophic loss even if all other
# safety mechanisms fail. They cannot be overridden by env vars,
# config files, or code changes without modifying this file.
# ═══════════════════════════════════════════════════════════════════

HARDCODED_MAX_DAILY_LOSS_PCT = 0.05       # 5% absolute max daily loss
HARDCODED_MAX_DRAWDOWN_PCT = 0.15         # 15% absolute max drawdown
HARDCODED_MAX_POSITION_SIZE_PCT = 0.10    # 10% max single position
HARDCODED_MAX_CONCURRENT_POSITIONS = 5    # 5 max concurrent positions
HARDCODED_MAX_LEVERAGE = 5                # 5x max leverage
HARDCODED_TESTNET_ONLY = True             # CANNOT be set to False

# Testnet base URLs — hardcoded, no mainnet allowed
BINANCE_FUTURES_TESTNET_REST = "https://testnet.binancefuture.com"
BINANCE_FUTURES_TESTNET_WS = "wss://stream.binancefuture.com"

# Mainnet URLs — listed here ONLY to block them
_BLOCKED_MAINNET_URLS = [
    "https://fapi.binance.com",
    "https://api.binance.com",
    "wss://fstream.binance.com",
    "wss://stream.binance.com",
]


@dataclass
class TradingConfig:
    """Configurable trading parameters (within hardcoded safety bounds)."""

    # Symbols to trade
    symbols: List[str] = field(default_factory=lambda: [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"
    ])

    # Timeframe for ML signals
    timeframe: str = "4h"

    # Risk parameters (must be <= hardcoded limits)
    max_daily_loss_pct: float = 0.02       # 2% default daily loss limit
    max_drawdown_pct: float = 0.10         # 10% default max drawdown
    max_position_size_pct: float = 0.05    # 5% default max position size
    max_concurrent_positions: int = 3      # 3 default concurrent positions
    leverage: int = 3                      # 3x default leverage

    # Signal thresholds
    min_confidence: float = 0.42           # Minimum model confidence
    min_edge: float = 0.05                # Minimum edge over neutral

    # Execution
    order_type: str = "LIMIT"              # Default to limit orders (maker)
    limit_offset_pct: float = 0.001        # 0.1% offset for limit orders
    order_timeout_seconds: int = 300       # Cancel unfilled limits after 5min

    # Monitoring
    heartbeat_interval_seconds: int = 900  # 15 minutes
    daily_report_hour_utc: int = 0         # Midnight UTC

    # Cooldown
    cooldown_after_loss_minutes: int = 60  # 1 hour cooldown after loss
    max_consecutive_losses: int = 5        # Circuit breaker trigger

    def __post_init__(self):
        """Enforce hardcoded safety limits — cannot be bypassed."""
        self.max_daily_loss_pct = min(
            self.max_daily_loss_pct, HARDCODED_MAX_DAILY_LOSS_PCT
        )
        self.max_drawdown_pct = min(
            self.max_drawdown_pct, HARDCODED_MAX_DRAWDOWN_PCT
        )
        self.max_position_size_pct = min(
            self.max_position_size_pct, HARDCODED_MAX_POSITION_SIZE_PCT
        )
        self.max_concurrent_positions = min(
            self.max_concurrent_positions, HARDCODED_MAX_CONCURRENT_POSITIONS
        )
        self.leverage = min(self.leverage, HARDCODED_MAX_LEVERAGE)

        # Enforce testnet only
        if not HARDCODED_TESTNET_ONLY:
            raise RuntimeError("CRITICAL: HARDCODED_TESTNET_ONLY must be True")


@dataclass
class ExchangeConfig:
    """Binance Futures Testnet connection config."""

    api_key: str = ""
    api_secret: str = ""
    rest_url: str = BINANCE_FUTURES_TESTNET_REST
    ws_url: str = BINANCE_FUTURES_TESTNET_WS

    def __post_init__(self):
        """Load from env vars and validate testnet only."""
        if not self.api_key:
            self.api_key = os.environ.get("BINANCE_TESTNET_API_KEY", "")
        if not self.api_secret:
            self.api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET", "")

        # CRITICAL: Block any mainnet URL
        for blocked in _BLOCKED_MAINNET_URLS:
            if blocked in self.rest_url or blocked in self.ws_url:
                raise RuntimeError(
                    f"CRITICAL: Mainnet URL detected: {blocked}. "
                    "Paper trading is TESTNET ONLY."
                )

        # Force testnet URLs
        self.rest_url = BINANCE_FUTURES_TESTNET_REST
        self.ws_url = BINANCE_FUTURES_TESTNET_WS


@dataclass
class TelegramConfig:
    """Telegram alerting config."""

    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True

    def __post_init__(self):
        if not self.bot_token:
            self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not self.chat_id:
            self.chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not self.bot_token or not self.chat_id:
            self.enabled = False


@dataclass
class PaperTradingConfig:
    """Top-level paper trading configuration."""

    trading: TradingConfig = field(default_factory=TradingConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

    # Database
    db_url: str = ""

    def __post_init__(self):
        if not self.db_url:
            self.db_url = os.environ.get(
                "DATABASE_URL",
                "postgresql://coinscopeai:coinscopeai_dev@localhost:5432/coinscopeai_dev"
            )

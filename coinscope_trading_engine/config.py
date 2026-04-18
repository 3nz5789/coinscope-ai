"""
config.py — CoinScopeAI Configuration Loader
=============================================
Loads and validates all environment variables using Pydantic Settings.
Exports a singleton ``settings`` instance that every module should import.

Usage
-----
    from config import settings

    print(settings.binance_api_key)
    print(settings.max_leverage)

Requirements
------------
    pip install pydantic-settings python-dotenv
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import (
    AnyHttpUrl,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Environment(str, Enum):
    PRODUCTION  = "production"
    STAGING     = "staging"
    DEVELOPMENT = "development"


class ParseMode(str, Enum):
    HTML        = "HTML"
    MARKDOWN    = "Markdown"
    MARKDOWNV2  = "MarkdownV2"


class Timeframe(str, Enum):
    ONE_MIN    = "1m"
    FIVE_MIN   = "5m"
    FIFTEEN_MIN = "15m"
    ONE_HOUR   = "1h"
    FOUR_HOUR  = "4h"
    ONE_DAY    = "1d"


class LogLevel(str, Enum):
    DEBUG    = "DEBUG"
    INFO     = "INFO"
    WARNING  = "WARNING"
    ERROR    = "ERROR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Settings model
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """
    Typed, validated configuration for the CoinScopeAI Trading Engine.

    All fields map 1-to-1 to variables in .env / the process environment.
    Required fields (no default) will raise a ``ValidationError`` on startup
    if they are missing or empty — giving a clear, actionable error message.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,       # ENV and env are the same key
        extra="ignore",             # silently ignore unknown vars
        populate_by_name=True,
    )

    # ── Environment ───────────────────────────────────────────────────────
    env: Environment = Field(Environment.DEVELOPMENT, description="Runtime environment")
    debug_mode: bool = Field(False, description="Verbose debug logging")
    testnet_mode: bool = Field(True, description="Route traffic via Binance Testnet")

    # ── Binance Testnet ───────────────────────────────────────────────────
    binance_testnet_api_key: SecretStr = Field(
        ..., description="[REQUIRED] Binance Testnet API key"
    )
    binance_testnet_api_secret: SecretStr = Field(
        ..., description="[REQUIRED] Binance Testnet API secret"
    )
    binance_testnet_base_url: str = Field(
        "https://testnet.binancefuture.com",
        description="Testnet REST base URL",
    )
    binance_testnet_ws_url: str = Field(
        "wss://stream.binancefuture.com",
        description="Testnet WebSocket base URL",
    )

    # ── Binance Mainnet ───────────────────────────────────────────────────
    binance_api_key: Optional[SecretStr] = Field(
        None, description="Mainnet API key (required when TESTNET_MODE=false)"
    )
    binance_api_secret: Optional[SecretStr] = Field(
        None, description="Mainnet API secret (required when TESTNET_MODE=false)"
    )
    binance_base_url: str = Field(
        "https://fapi.binance.com", description="Mainnet REST base URL"
    )
    binance_ws_url: str = Field(
        "wss://fstream.binance.com", description="Mainnet WebSocket base URL"
    )

    # ── Telegram ──────────────────────────────────────────────────────────
    telegram_bot_token: SecretStr = Field(
        ..., description="[REQUIRED] Telegram Bot token from @BotFather"
    )
    telegram_chat_id: str = Field(
        ..., description="[REQUIRED] Telegram chat / channel ID for alerts"
    )
    telegram_parse_mode: ParseMode = Field(ParseMode.HTML, description="Message parse mode")
    telegram_send_startup_msg: bool = Field(True, description="Notify on engine startup")

    # ── Redis ─────────────────────────────────────────────────────────────
    redis_host: str = Field("localhost", description="Redis server hostname")
    redis_port: int = Field(6379, ge=1, le=65535, description="Redis server port")
    redis_db: int = Field(0, ge=0, le=15, description="Redis database index")
    redis_password: Optional[SecretStr] = Field(None, description="Redis auth password")
    redis_cache_ttl_seconds: int = Field(60, ge=1, description="Default cache TTL (s)")
    redis_pool_size: int = Field(10, ge=1, description="Redis connection pool size")

    # ── Database ──────────────────────────────────────────────────────────
    database_url: str = Field(
        "sqlite:///./coinscope.db", description="SQLAlchemy database URL"
    )
    db_pool_size: int = Field(5, ge=1, description="DB connection pool size")
    db_reset_on_startup: bool = Field(
        False, description="Drop & recreate all tables on startup (DANGER)"
    )

    # ── Risk Parameters ───────────────────────────────────────────────────
    max_daily_loss_pct: float = Field(
        2.0, ge=0.1, le=100.0, description="Max daily loss % before trading halts"
    )
    max_leverage: int = Field(10, ge=1, le=125, description="Hard leverage cap per position")
    max_open_positions: int = Field(5, ge=1, description="Max simultaneous open positions")
    max_single_position_pct: float = Field(
        20.0, ge=0.1, le=100.0, description="Max equity allocation per position (%)"
    )
    max_total_exposure_pct: float = Field(
        80.0, ge=0.1, le=100.0, description="Max total portfolio exposure (%)"
    )
    min_risk_reward_ratio: float = Field(
        1.5, ge=0.1, description="Minimum RR ratio required to act on a signal"
    )
    atr_period: int = Field(14, ge=1, description="ATR lookback period for position sizing")

    # ── Scanner Settings ──────────────────────────────────────────────────
    scan_pairs_raw: str = Field(
        "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT",
        alias="scan_pairs",
        description="Comma-separated list of Binance Futures pairs",
    )
    scan_interval_seconds: int = Field(
        5, ge=1, description="Scanner cycle interval in seconds"
    )
    volume_spike_multiplier: float = Field(
        3.0, ge=1.0, description="Volume spike threshold (× rolling average)"
    )
    volume_baseline_period: int = Field(
        20, ge=2, description="Rolling window (candles) for volume baseline"
    )
    funding_rate_threshold_pct: float = Field(
        0.1, ge=0.0, description="Funding rate deviation (%) that triggers an alert"
    )
    min_confluence_score: int = Field(
        65, ge=0, le=100, description="Minimum confluence score (0-100) to emit a signal"
    )
    default_timeframe: Timeframe = Field(
        Timeframe.FIVE_MIN, description="Default candle interval for scanners"
    )

    # ── Signal & Alert Settings ───────────────────────────────────────────
    alert_rate_limit_per_min: int = Field(
        10, ge=1, description="Max alerts sent per minute across all channels"
    )
    signal_cooldown_seconds: int = Field(
        300, ge=0, description="Min gap (s) between duplicate signals for the same pair"
    )
    alert_queue_max_size: int = Field(
        100, ge=1, description="Max items held in the in-memory alert queue"
    )
    webhook_urls_raw: str = Field(
        "", alias="webhook_urls", description="Comma-separated external webhook URLs"
    )

    # ── API Server ────────────────────────────────────────────────────────
    api_host: str = Field("0.0.0.0", description="FastAPI bind host")
    api_port: int = Field(8000, ge=1, le=65535, description="FastAPI listen port")
    api_workers: int = Field(1, ge=1, description="Uvicorn worker count")
    cors_origins_raw: str = Field(
        "http://localhost:3000",
        alias="cors_origins",
        description="Comma-separated allowed CORS origins",
    )
    secret_key: SecretStr = Field(
        ..., description="[REQUIRED] JWT signing secret (generate: openssl rand -hex 32)"
    )


    # ── Stripe Billing ────────────────────────────────────────────────────
    stripe_publishable_key: str = Field(
        "", description="Stripe publishable key (pk_test_... / pk_live_...)"
    )
    stripe_secret_key: Optional[SecretStr] = Field(
        None, description="Stripe secret key (sk_test_... / sk_live_...)"
    )
    stripe_webhook_secret: Optional[SecretStr] = Field(
        None, description="Stripe webhook signing secret (whsec_...)"
    )
    # Price IDs — populate after running setup_stripe_products.py
    stripe_starter_price_id: str = Field("", description="Stripe Price ID: Starter $19/mo")
    stripe_pro_price_id: str = Field("", description="Stripe Price ID: Pro $49/mo")
    stripe_elite_price_id: str = Field("", description="Stripe Price ID: Elite $99/mo")
    stripe_team_price_id: str = Field("", description="Stripe Price ID: Team $299/mo")
    stripe_success_url: str = Field(
        "http://localhost:3000/billing/success",
        description="Redirect URL after successful checkout"
    )
    stripe_cancel_url: str = Field(
        "http://localhost:3000/billing/cancel",
        description="Redirect URL on checkout cancel"
    )

    # ── Logging ───────────────────────────────────────────────────────────
    log_level: LogLevel = Field(LogLevel.INFO, description="Application log level")
    log_file: str = Field("logs/coinscope.log", description="Rotating log file path")
    log_max_mb: int = Field(10, ge=1, description="Max log file size in MB before rotation")
    log_backup_count: int = Field(5, ge=0, description="Rotated log files to keep")

    # ── Derived / computed properties ─────────────────────────────────────

    @property
    def scan_pairs(self) -> list[str]:
        """Returns the list of trading pairs to scan."""
        return [p.strip().upper() for p in self.scan_pairs_raw.split(",") if p.strip()]

    @property
    def webhook_urls(self) -> list[str]:
        """Returns the list of external webhook URLs (empty list if none configured)."""
        return [u.strip() for u in self.webhook_urls_raw.split(",") if u.strip()]

    @property
    def cors_origins(self) -> list[str]:
        """Returns the list of allowed CORS origins."""
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def active_api_key(self) -> SecretStr:
        """Returns the API key appropriate for the current mode (testnet vs mainnet)."""
        if self.testnet_mode:
            return self.binance_testnet_api_key
        if self.binance_api_key is None:
            raise RuntimeError(
                "BINANCE_API_KEY is required when TESTNET_MODE=false. "
                "Set it in your .env file."
            )
        return self.binance_api_key

    @property
    def active_api_secret(self) -> SecretStr:
        """Returns the API secret appropriate for the current mode (testnet vs mainnet)."""
        if self.testnet_mode:
            return self.binance_testnet_api_secret
        if self.binance_api_secret is None:
            raise RuntimeError(
                "BINANCE_API_SECRET is required when TESTNET_MODE=false. "
                "Set it in your .env file."
            )
        return self.binance_api_secret

    @property
    def active_base_url(self) -> str:
        """Returns the REST base URL for the active mode."""
        return self.binance_testnet_base_url if self.testnet_mode else self.binance_base_url

    @property
    def active_ws_url(self) -> str:
        """Returns the WebSocket base URL for the active mode."""
        return self.binance_testnet_ws_url if self.testnet_mode else self.binance_ws_url

    @property
    def redis_url(self) -> str:
        """Constructs the full Redis connection URL."""
        pwd = self.redis_password.get_secret_value() if self.redis_password else ""
        auth = f":{pwd}@" if pwd else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── Validators ────────────────────────────────────────────────────────

    @model_validator(mode="after")
    def validate_mainnet_keys(self) -> "Settings":
        """Enforce that mainnet keys are provided when TESTNET_MODE is disabled."""
        if not self.testnet_mode:
            missing = []
            if self.binance_api_key is None:
                missing.append("BINANCE_API_KEY")
            if self.binance_api_secret is None:
                missing.append("BINANCE_API_SECRET")
            if missing:
                raise ValueError(
                    f"TESTNET_MODE is false but the following mainnet credentials are "
                    f"missing from your .env file: {', '.join(missing)}"
                )
        return self

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """Apply extra safety checks when running in production."""
        if self.env == Environment.PRODUCTION:
            if self.testnet_mode:
                raise ValueError(
                    "ENV=production is incompatible with TESTNET_MODE=true. "
                    "Set TESTNET_MODE=false before going live."
                )
            if self.db_reset_on_startup:
                raise ValueError(
                    "DB_RESET_ON_STARTUP=true is not allowed in production. "
                    "This would destroy all trading history."
                )
            raw_secret = self.secret_key.get_secret_value()
            if raw_secret in ("", "change_me_to_a_random_secret_key"):
                raise ValueError(
                    "SECRET_KEY must be set to a strong random value in production. "
                    "Generate one with: openssl rand -hex 32"
                )
        return self

    @field_validator("scan_pairs_raw")
    @classmethod
    def validate_scan_pairs(cls, v: str) -> str:
        pairs = [p.strip().upper() for p in v.split(",") if p.strip()]
        if not pairs:
            raise ValueError(
                "SCAN_PAIRS must contain at least one trading pair (e.g. BTCUSDT)."
            )
        invalid = [p for p in pairs if not p.endswith("USDT") and not p.endswith("BTC")]
        if invalid:
            logging.getLogger(__name__).warning(
                "Unusual pair format detected (expected *USDT or *BTC): %s", invalid
            )
        return v

    # ── String representation (masks secrets) ─────────────────────────────

    def __repr__(self) -> str:
        return (
            f"<Settings env={self.env.value} testnet={self.testnet_mode} "
            f"pairs={self.scan_pairs} leverage_cap={self.max_leverage}x>"
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns the application-wide Settings singleton.

    The result is cached after the first call — environment variables are
    read once at startup.  Call ``get_settings.cache_clear()`` in tests to
    force re-loading from a different .env file.
    """
    return Settings()


# Convenience alias — import this throughout the codebase
settings = get_settings()


# ---------------------------------------------------------------------------
# Logging bootstrap (called once at import time)
# ---------------------------------------------------------------------------

def _bootstrap_logging(cfg: Settings) -> None:
    """Configure the root logger according to settings."""
    import logging.handlers

    log_dir = Path(cfg.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(cfg.log_level.value)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        filename=cfg.log_file,
        maxBytes=cfg.log_max_mb * 1024 * 1024,
        backupCount=cfg.log_backup_count,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)


_bootstrap_logging(settings)

logger = logging.getLogger(__name__)
logger.info(
    "CoinScopeAI config loaded | env=%s testnet=%s pairs=%d",
    settings.env.value,
    settings.testnet_mode,
    len(settings.scan_pairs),
)

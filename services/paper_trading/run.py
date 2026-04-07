"""
CoinScopeAI Paper Trading — Run CLI
======================================
Start the paper trading engine.

Usage:
    python -m services.paper_trading.run [--model MODEL_PATH] [--symbols SYMBOLS] [--timeframe TF]
"""

import argparse
import logging
import sys

from .config import PaperTradingConfig, TradingConfig, ExchangeConfig, TelegramConfig
from .engine import PaperTradingEngine


def setup_logging(level: str = "INFO"):
    """Configure structured logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-40s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("/tmp/coinscopeai_paper_trading.log"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="CoinScopeAI Paper Trading Engine (TESTNET ONLY)",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Path to trained ML model (.joblib)",
    )
    parser.add_argument(
        "--symbols", type=str, default=None,
        help="Comma-separated symbols (e.g., BTCUSDT,ETHUSDT)",
    )
    parser.add_argument(
        "--timeframe", type=str, default="4h",
        help="Candle timeframe (default: 4h)",
    )
    parser.add_argument(
        "--leverage", type=int, default=3,
        help="Leverage (default: 3, max: 5)",
    )
    parser.add_argument(
        "--max-daily-loss", type=float, default=0.02,
        help="Max daily loss percent (default: 0.02)",
    )
    parser.add_argument(
        "--max-positions", type=int, default=3,
        help="Max concurrent positions (default: 3)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)

    logger = logging.getLogger("coinscopeai.paper_trading.cli")
    logger.info("=" * 60)
    logger.info("CoinScopeAI Paper Trading — TESTNET ONLY")
    logger.info("=" * 60)

    # Build config
    trading_config = TradingConfig(
        timeframe=args.timeframe,
        leverage=args.leverage,
        max_daily_loss_pct=args.max_daily_loss,
        max_concurrent_positions=args.max_positions,
    )

    if args.symbols:
        trading_config.symbols = [s.strip().upper() for s in args.symbols.split(",")]

    config = PaperTradingConfig(
        trading=trading_config,
        exchange=ExchangeConfig(),
        telegram=TelegramConfig(),
    )

    # Create and start engine
    engine = PaperTradingEngine(config)

    try:
        engine.start(model_path=args.model)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error("Fatal error: %s", e)
        engine.stop(f"fatal_error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

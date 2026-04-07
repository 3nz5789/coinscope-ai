#!/usr/bin/env python3
"""
CoinScopeAI — CLI

Usage:
  python -m services.market_data.cli [OPTIONS]

Options:
  --symbols       Comma-separated symbol list (default: BTCUSDT,ETHUSDT)
  --exchanges     Comma-separated exchange list (default: all)
  --scanners      Comma-separated scanner list (default: all)
  --scan-interval Scanner evaluation interval in seconds (default: 5)
  --window        Scanner rolling window in seconds (default: 300)
  --duration      Run duration in seconds; 0 = forever (default: 0)
  --log-level     Logging level (default: INFO)
  --metrics-interval  Print metrics every N seconds (default: 30)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from typing import List

# Ensure the project root is importable
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.market_data.aggregator import Aggregator
from services.market_data.base import EventBus
from services.market_data.models import Exchange, EventType, MarketEvent, ScanSignal
from services.market_data.binance.client import BinanceFuturesClient
from services.market_data.bybit.client import BybitClient
from services.market_data.okx.client import OKXClient
from services.market_data.hyperliquid.client import HyperliquidClient
from services.market_data.scanner import (
    BreakoutOIScanner,
    FundingExtremeScanner,
    LiquidityDeteriorationScanner,
    ScannerConfig,
    SpreadDivergenceScanner,
)

logger = logging.getLogger("coinscopeai.cli")

EXCHANGE_MAP = {
    "binance": (Exchange.BINANCE, BinanceFuturesClient),
    "bybit": (Exchange.BYBIT, BybitClient),
    "okx": (Exchange.OKX, OKXClient),
    "hyperliquid": (Exchange.HYPERLIQUID, HyperliquidClient),
}

SCANNER_MAP = {
    "breakout_oi": BreakoutOIScanner,
    "funding_extreme": FundingExtremeScanner,
    "spread_divergence": SpreadDivergenceScanner,
    "liquidity_deterioration": LiquidityDeteriorationScanner,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CoinScopeAI Market Data CLI")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT",
                        help="Comma-separated symbols")
    parser.add_argument("--exchanges", default="all",
                        help="Comma-separated exchanges or 'all'")
    parser.add_argument("--scanners", default="all",
                        help="Comma-separated scanners or 'all'")
    parser.add_argument("--scan-interval", type=float, default=5.0,
                        help="Scanner evaluation interval (seconds)")
    parser.add_argument("--window", type=float, default=300.0,
                        help="Scanner rolling window (seconds)")
    parser.add_argument("--duration", type=float, default=0,
                        help="Run duration (seconds); 0 = forever")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--metrics-interval", type=float, default=30.0,
                        help="Print metrics every N seconds")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    logger.info("Symbols: %s", symbols)

    # Determine exchanges
    if args.exchanges == "all":
        exchange_keys = list(EXCHANGE_MAP.keys())
    else:
        exchange_keys = [e.strip().lower() for e in args.exchanges.split(",")]

    # Determine scanners
    if args.scanners == "all":
        scanner_keys = list(SCANNER_MAP.keys())
    else:
        scanner_keys = [s.strip().lower() for s in args.scanners.split(",")]

    # Build aggregator
    aggregator = Aggregator()

    # Create exchange clients
    active_exchanges: List[Exchange] = []
    for key in exchange_keys:
        if key not in EXCHANGE_MAP:
            logger.warning("Unknown exchange: %s", key)
            continue
        exchange_enum, client_cls = EXCHANGE_MAP[key]
        client = client_cls(symbols=symbols, event_bus=aggregator.event_bus)
        aggregator.add_client(client)
        active_exchanges.append(exchange_enum)
        logger.info("Added exchange client: %s", key)

    # Create scanners
    for key in scanner_keys:
        if key not in SCANNER_MAP:
            logger.warning("Unknown scanner: %s", key)
            continue
        config = ScannerConfig(
            symbols=symbols,
            exchanges=active_exchanges,
            window_seconds=args.window,
            scan_interval=args.scan_interval,
        )
        scanner = SCANNER_MAP[key](config=config, event_bus=aggregator.event_bus)
        aggregator.add_scanner(scanner)
        logger.info("Added scanner: %s", key)

    # Signal callback — print to stdout
    async def on_signal(sig: ScanSignal) -> None:
        print(f"\n{'='*60}")
        print(f"  SIGNAL: {sig.signal_type}")
        print(f"  Exchange: {sig.exchange.value}  Symbol: {sig.symbol}")
        print(f"  Strength: {sig.strength:.2f}")
        print(f"  Details: {json.dumps(sig.details, indent=2, default=str)}")
        print(f"{'='*60}\n")

    aggregator.on_signal(on_signal)

    # Graceful shutdown
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, sig_name), _signal_handler)
        except (NotImplementedError, AttributeError):
            pass

    # Start
    await aggregator.start()
    logger.info("Aggregator running. Press Ctrl+C to stop.")

    # Metrics printer
    async def print_metrics():
        while not stop_event.is_set():
            await asyncio.sleep(args.metrics_interval)
            metrics = aggregator.get_metrics()
            logger.info("--- Metrics ---")
            for ex, m in metrics.items():
                logger.info("  %s: state=%s msgs=%d mps=%.1f reconnects=%d errors=%d",
                            ex, m["state"], m["messages_received"],
                            m["messages_per_second"], m["reconnect_count"], m["errors"])

    metrics_task = asyncio.create_task(print_metrics())

    # Wait for duration or stop signal
    if args.duration > 0:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=args.duration)
        except asyncio.TimeoutError:
            pass
    else:
        await stop_event.wait()

    metrics_task.cancel()
    await aggregator.stop()
    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())

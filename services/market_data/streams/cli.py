"""
CLI for CoinScopeAI Market Data Streams.

Commands:
  record     — Start live recording of one or more streams
  replay     — Replay recorded data through the EventBus
  download   — Bulk download historical data (Bybit portal, Binance REST, etc.)
  status     — Show stream status and recorded data inventory

Usage examples:
  # Record all 5 streams for BTC and ETH:
  python -m services.market_data.streams.cli record --symbols BTCUSDT,ETHUSDT --streams all

  # Record only trades and orderbook:
  python -m services.market_data.streams.cli record --symbols BTCUSDT --streams trades,orderbook

  # Replay 2025-01-01 data at 10x speed:
  python -m services.market_data.streams.cli replay --data-dir ./data/recordings \\
      --start 2025-01-01T00:00:00 --end 2025-01-01T23:59:59 --speed 10.0

  # Download Bybit orderbook history (PRIMARY backfill — 500 levels, ~100ms resolution):
  python -m services.market_data.streams.cli download orderbook \\
      --symbol BTCUSDT --start 2025-01-01 --end 2025-01-31

  # Download trade history from Bybit public.bybit.com:
  python -m services.market_data.streams.cli download trades \\
      --symbol BTCUSDT --start 2025-01-01 --end 2025-01-31 --source bybit_public

  # Download funding rate history:
  python -m services.market_data.streams.cli download funding \\
      --symbol BTCUSDT --start 2025-01-01 --end 2025-01-31

  # Show inventory of recorded data:
  python -m services.market_data.streams.cli status --data-dir ./data/recordings
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("coinscopeai.cli")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _parse_datetime(s: str) -> datetime:
    """Parse ISO datetime string, assume UTC if no timezone."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {s!r}")


def _parse_symbols(s: str) -> List[str]:
    return [sym.strip().upper() for sym in s.split(",") if sym.strip()]


def _parse_exchanges(s: str) -> List[str]:
    return [ex.strip().lower() for ex in s.split(",") if ex.strip()]


# ---------------------------------------------------------------------------
# record command
# ---------------------------------------------------------------------------

async def _cmd_record(args: argparse.Namespace) -> None:
    from .base import EventBus, Exchange
    from .recorder import StreamRecorder
    from .trades import TradeStream
    from .orderbook import OrderBookStream
    from .funding import FundingStream
    from .liquidation import LiquidationStream

    symbols = _parse_symbols(args.symbols)
    stream_names = [s.strip().lower() for s in args.streams.split(",")]
    if "all" in stream_names:
        stream_names = ["trades", "orderbook", "funding", "liquidation"]

    exchange_names = _parse_exchanges(args.exchanges) if args.exchanges else None
    if exchange_names:
        exchanges = [Exchange(ex) for ex in exchange_names]
    else:
        exchanges = list(Exchange)

    bus = EventBus()
    recorder = StreamRecorder(
        event_bus=bus,
        output_dir=args.output_dir,
        buffer_size=args.buffer_size,
        flush_interval=args.flush_interval,
    )

    streams = []
    if "trades" in stream_names:
        streams.append(TradeStream(symbols=symbols, exchanges=exchanges, event_bus=bus))
    if "orderbook" in stream_names:
        streams.append(OrderBookStream(symbols=symbols, exchanges=exchanges, event_bus=bus))
    if "funding" in stream_names:
        streams.append(FundingStream(symbols=symbols, exchanges=exchanges, event_bus=bus))
    if "liquidation" in stream_names:
        streams.append(LiquidationStream(symbols=symbols, exchanges=exchanges, event_bus=bus))

    logger.info(
        "Starting recorder: symbols=%s streams=%s exchanges=%s output=%s",
        symbols, stream_names, [e.value for e in exchanges], args.output_dir,
    )

    # Graceful shutdown on SIGINT/SIGTERM
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received — flushing and stopping...")
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Start recorder first, then streams
    await recorder.start()
    for stream in streams:
        await stream.start()

    logger.info("All streams running. Press Ctrl+C to stop.")
    await stop_event.wait()

    # Stop in reverse order
    for stream in reversed(streams):
        await stream.stop()
    await recorder.stop()
    logger.info("Recorder stopped cleanly.")


# ---------------------------------------------------------------------------
# replay command
# ---------------------------------------------------------------------------

async def _cmd_replay(args: argparse.Namespace) -> None:
    from .base import EventBus
    from .replay import ReplayEngine

    bus = EventBus()

    # Attach a simple print subscriber for demo purposes
    if args.verbose:
        from .base import EventType

        async def _print_event(event_type, data):
            logger.info("EVENT %s: %s", event_type.value, str(data)[:120])

        for et in EventType:
            bus.subscribe(et, _print_event)

    start_dt = _parse_datetime(args.start) if args.start else None
    end_dt = _parse_datetime(args.end) if args.end else None

    engine = ReplayEngine(
        data_dir=args.data_dir,
        event_bus=bus,
        speed=args.speed,
        start_time=start_dt,
        end_time=end_dt,
        loop_count=args.loop,
    )

    logger.info(
        "Starting replay: dir=%s speed=%.1fx start=%s end=%s",
        args.data_dir, args.speed, args.start, args.end,
    )

    stop_event = asyncio.Event()

    def _shutdown(signum, frame):
        logger.info("Replay interrupted.")
        asyncio.get_event_loop().call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    replay_task = asyncio.create_task(engine.run())
    stop_task = asyncio.create_task(stop_event.wait())

    done, pending = await asyncio.wait(
        [replay_task, stop_task], return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

    logger.info("Replay finished.")


# ---------------------------------------------------------------------------
# download command
# ---------------------------------------------------------------------------

async def _cmd_download(args: argparse.Namespace) -> None:
    from .downloader import HistoricalDownloader

    downloader = HistoricalDownloader(output_dir=args.output_dir)
    symbol = args.symbol.upper()
    start = _parse_date(args.start)
    end = _parse_date(args.end)

    logger.info(
        "Download: type=%s symbol=%s %s → %s output=%s",
        args.data_type, symbol, start, end, args.output_dir,
    )

    if args.data_type == "orderbook":
        market_type = getattr(args, "market_type", "linear")
        result = await downloader.download_orderbook_history(
            symbol=symbol,
            start=start,
            end=end,
            market_type=market_type,
            skip_existing=not args.force,
        )
        logger.info("Orderbook download complete: %s", result)

    elif args.data_type == "trades":
        sources = _parse_exchanges(args.source) if args.source else None
        result = await downloader.download_trades_history(
            symbol=symbol,
            start=start,
            end=end,
            sources=sources,
        )
        logger.info("Trades download complete: %s", result)

    elif args.data_type == "funding":
        sources = _parse_exchanges(args.source) if args.source else None
        result = await downloader.download_funding_history(
            symbol=symbol,
            start=start,
            end=end,
            sources=sources,
        )
        logger.info("Funding download complete: %s", result)

    else:
        logger.error("Unknown data type: %s", args.data_type)
        sys.exit(1)


# ---------------------------------------------------------------------------
# status command
# ---------------------------------------------------------------------------

def _cmd_status(args: argparse.Namespace) -> None:
    """Show inventory of recorded data files."""
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error("Data directory does not exist: %s", data_dir)
        return

    total_files = 0
    total_size = 0
    file_types: dict = {}

    for filepath in sorted(data_dir.rglob("*.jsonl.gz")):
        size = filepath.stat().st_size
        total_files += 1
        total_size += size
        rel = filepath.relative_to(data_dir)
        parts = rel.parts
        category = parts[0] if parts else "unknown"
        file_types.setdefault(category, {"files": 0, "size": 0})
        file_types[category]["files"] += 1
        file_types[category]["size"] += size

    print(f"\nData Inventory: {data_dir}")
    print(f"{'='*60}")
    print(f"Total files: {total_files}")
    print(f"Total size:  {total_size / 1024 / 1024:.1f} MB")
    print()

    if file_types:
        print(f"{'Category':<30} {'Files':>8} {'Size (MB)':>12}")
        print(f"{'-'*52}")
        for cat, info in sorted(file_types.items()):
            print(f"  {cat:<28} {info['files']:>8} {info['size']/1024/1024:>12.1f}")
    else:
        print("No recorded data found.")

    # Also check for uncompressed JSONL
    uncompressed = list(data_dir.rglob("*.jsonl"))
    if uncompressed:
        print(f"\nUncompressed JSONL files: {len(uncompressed)}")

    print()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coinscopeai-streams",
        description="CoinScopeAI Market Data Streams CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- record ----
    rec = subparsers.add_parser("record", help="Record live stream data")
    rec.add_argument(
        "--symbols", required=True,
        help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT",
    )
    rec.add_argument(
        "--streams", default="all",
        help="Comma-separated stream types: trades,orderbook,funding,liquidation (default: all)",
    )
    rec.add_argument(
        "--exchanges", default=None,
        help="Comma-separated exchanges: binance,bybit,okx,hyperliquid (default: all)",
    )
    rec.add_argument(
        "--output-dir", default="./data/recordings",
        help="Output directory for JSONL.gz recordings (default: ./data/recordings)",
    )
    rec.add_argument(
        "--buffer-size", type=int, default=1000,
        help="Flush buffer after this many events (default: 1000)",
    )
    rec.add_argument(
        "--flush-interval", type=float, default=5.0,
        help="Flush buffer every N seconds (default: 5.0)",
    )

    # ---- replay ----
    rep = subparsers.add_parser("replay", help="Replay recorded data through EventBus")
    rep.add_argument(
        "--data-dir", required=True,
        help="Directory containing JSONL.gz recordings",
    )
    rep.add_argument(
        "--start", default=None,
        help="Start time (ISO format: 2025-01-01T00:00:00)",
    )
    rep.add_argument(
        "--end", default=None,
        help="End time (ISO format: 2025-01-01T23:59:59)",
    )
    rep.add_argument(
        "--speed", type=float, default=1.0,
        help="Playback speed multiplier (default: 1.0, use 0 for max speed)",
    )
    rep.add_argument(
        "--loop", type=int, default=1,
        help="Number of replay loops (default: 1, use -1 for infinite)",
    )
    rep.add_argument(
        "--verbose", action="store_true",
        help="Print each event to stdout",
    )

    # ---- download ----
    dl = subparsers.add_parser("download", help="Download historical market data")
    dl_sub = dl.add_subparsers(dest="data_type", required=True)

    # download orderbook
    dl_ob = dl_sub.add_parser(
        "orderbook",
        help="Download order book history from Bybit history-data portal (500 levels, ~100ms)",
    )
    dl_ob.add_argument("--symbol", required=True, help="Symbol, e.g. BTCUSDT")
    dl_ob.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    dl_ob.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    dl_ob.add_argument(
        "--market-type", default="linear",
        choices=["linear", "inverse"],
        help="Market type: linear (USDT perps) or inverse (coin-margined) (default: linear)",
    )
    dl_ob.add_argument(
        "--output-dir", default="./data",
        help="Output base directory (default: ./data)",
    )
    dl_ob.add_argument(
        "--force", action="store_true",
        help="Re-download even if file already exists",
    )

    # download trades
    dl_tr = dl_sub.add_parser("trades", help="Download historical trades")
    dl_tr.add_argument("--symbol", required=True, help="Symbol, e.g. BTCUSDT")
    dl_tr.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    dl_tr.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    dl_tr.add_argument(
        "--source", default=None,
        help="Comma-separated sources: bybit_public,binance (default: both)",
    )
    dl_tr.add_argument("--output-dir", default="./data", help="Output base directory")
    dl_tr.add_argument("--force", action="store_true", help="Re-download existing files")

    # download funding
    dl_fu = dl_sub.add_parser("funding", help="Download historical funding rates")
    dl_fu.add_argument("--symbol", required=True, help="Symbol, e.g. BTCUSDT")
    dl_fu.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    dl_fu.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    dl_fu.add_argument(
        "--source", default=None,
        help="Comma-separated sources: bybit,binance (default: both)",
    )
    dl_fu.add_argument("--output-dir", default="./data", help="Output base directory")
    dl_fu.add_argument("--force", action="store_true", help="Re-download existing files")

    # ---- status ----
    st = subparsers.add_parser("status", help="Show recorded data inventory")
    st.add_argument(
        "--data-dir", default="./data/recordings",
        help="Directory to inspect (default: ./data/recordings)",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "record":
        asyncio.run(_cmd_record(args))
    elif args.command == "replay":
        asyncio.run(_cmd_replay(args))
    elif args.command == "download":
        asyncio.run(_cmd_download(args))
    elif args.command == "status":
        _cmd_status(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

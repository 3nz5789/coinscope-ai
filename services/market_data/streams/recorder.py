"""
CoinScopeAI Market Data — Recording Daemon
=============================================
Records all market data events to JSONL.gz files for offline analysis.

Features:
  - Subscribes to all EventBus topics (trades, orderbook, funding, liquidations)
  - Date-partitioned files: data/{data_type}/{symbol}/{YYYY-MM-DD}.jsonl.gz
  - Buffered writes with periodic flush (every 10 seconds or 10K events)
  - Graceful shutdown on SIGINT/SIGTERM (flush all buffers)
  - Automatic file rotation at midnight UTC
  - Compression with gzip for storage efficiency
  - Statistics tracking (events recorded, bytes written, file counts)
"""

import gzip
import json
import logging
import os
import signal
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..event_bus import Event, EventBus
from ..types import (
    FundingRate,
    Kline,
    Liquidation,
    OrderBookSnapshot,
    Trade,
)

logger = logging.getLogger("coinscopeai.market_data.recorder")


@dataclass
class RecorderConfig:
    """Configuration for the recording daemon."""
    data_dir: str = "data/recorded"
    flush_interval: float = 10.0        # Flush every 10 seconds
    flush_threshold: int = 10_000       # Or every 10K events
    compression_level: int = 6          # gzip level (1=fast, 9=best)
    record_trades: bool = True
    record_orderbook: bool = True
    record_funding: bool = True
    record_liquidations: bool = True
    record_klines: bool = True
    record_alpha: bool = True
    record_regime: bool = True


class RecordingDaemon:
    """
    24/7 market data recording daemon.
    Subscribes to EventBus and writes all events to compressed JSONL files.
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: Optional[RecorderConfig] = None,
    ):
        self._bus = event_bus
        self._config = config or RecorderConfig()
        self._running = False
        self._lock = threading.Lock()

        # Buffers: {file_path: [json_lines]}
        self._buffers: Dict[str, List[str]] = defaultdict(list)
        self._buffer_count = 0

        # Open file handles: {file_path: gzip.GzipFile}
        self._files: Dict[str, gzip.GzipFile] = {}

        # Stats
        self._stats = {
            "events_recorded": 0,
            "bytes_written": 0,
            "files_created": 0,
            "flushes": 0,
            "errors": 0,
            "start_time": 0.0,
            "events_by_type": defaultdict(int),
        }

        # Flush thread
        self._flush_thread: Optional[threading.Thread] = None

        # Create data directory
        os.makedirs(self._config.data_dir, exist_ok=True)

    def start(self):
        """Start the recording daemon."""
        if self._running:
            return

        self._running = True
        self._stats["start_time"] = time.time()

        # Subscribe to all event types
        if self._config.record_trades:
            self._bus.subscribe("recorder_trades", "trade.*.*", self._on_event)
        if self._config.record_orderbook:
            self._bus.subscribe("recorder_ob", "orderbook.*.*", self._on_event)
        if self._config.record_funding:
            self._bus.subscribe("recorder_funding", "funding.*.*", self._on_event)
        if self._config.record_liquidations:
            self._bus.subscribe("recorder_liq", "liquidation.*.*", self._on_event)
        if self._config.record_klines:
            self._bus.subscribe("recorder_klines", "kline.*.*.*", self._on_event)
        if self._config.record_alpha:
            self._bus.subscribe("recorder_alpha", "alpha.*.*", self._on_event)
        if self._config.record_regime:
            self._bus.subscribe("recorder_regime", "regime.*", self._on_event)

        # Start flush thread
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            daemon=True,
            name="recorder-flush",
        )
        self._flush_thread.start()

        logger.info("Recording daemon started — data_dir=%s", self._config.data_dir)

    def stop(self):
        """Stop the recording daemon and flush all buffers."""
        logger.info("Recording daemon stopping — flushing buffers...")
        self._running = False

        if self._flush_thread:
            self._flush_thread.join(timeout=30)

        # Final flush
        self._flush_all()

        # Close all file handles
        with self._lock:
            for path, fh in self._files.items():
                try:
                    fh.close()
                except Exception as e:
                    logger.error("Error closing %s: %s", path, e)
            self._files.clear()

        logger.info(
            "Recording daemon stopped — %d events recorded, %d bytes written",
            self._stats["events_recorded"],
            self._stats["bytes_written"],
        )

    def _on_event(self, event: Event):
        """Handle an incoming event — buffer it for writing."""
        try:
            # Determine file path from topic
            parts = event.topic.split(".")
            data_type = parts[0]  # trade, orderbook, funding, etc.

            # Extract symbol
            if len(parts) >= 2:
                symbol = parts[1]
            else:
                symbol = "unknown"

            # Get date string for partitioning
            ts = getattr(event.data, "timestamp", time.time())
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

            # Build file path
            file_path = os.path.join(
                self._config.data_dir,
                data_type,
                symbol,
                f"{date_str}.jsonl.gz",
            )

            # Serialize event data
            if hasattr(event.data, "__dataclass_fields__"):
                record = asdict(event.data)
            elif isinstance(event.data, dict):
                record = event.data
            else:
                record = {"data": str(event.data)}

            record["_topic"] = event.topic
            record["_source"] = event.source
            record["_recorded_at"] = time.time()

            json_line = json.dumps(record, default=str) + "\n"

            with self._lock:
                self._buffers[file_path].append(json_line)
                self._buffer_count += 1
                self._stats["events_by_type"][data_type] += 1

            # Flush if buffer is large
            if self._buffer_count >= self._config.flush_threshold:
                self._flush_all()

        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Recorder error: %s", e)

    def _flush_loop(self):
        """Periodic flush thread."""
        while self._running:
            time.sleep(self._config.flush_interval)
            if self._buffer_count > 0:
                self._flush_all()

    def _flush_all(self):
        """Flush all buffers to disk."""
        with self._lock:
            buffers_to_flush = dict(self._buffers)
            self._buffers = defaultdict(list)
            self._buffer_count = 0

        for file_path, lines in buffers_to_flush.items():
            if not lines:
                continue
            try:
                self._write_lines(file_path, lines)
                self._stats["events_recorded"] += len(lines)
                self._stats["flushes"] += 1
            except Exception as e:
                self._stats["errors"] += 1
                logger.error("Flush error for %s: %s", file_path, e)

    def _write_lines(self, file_path: str, lines: List[str]):
        """Write lines to a gzip-compressed JSONL file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Get or create file handle
        if file_path not in self._files:
            mode = "ab" if os.path.exists(file_path) else "wb"
            self._files[file_path] = gzip.open(
                file_path,
                mode,
                compresslevel=self._config.compression_level,
            )
            self._stats["files_created"] += 1

        fh = self._files[file_path]
        data = "".join(lines).encode("utf-8")
        fh.write(data)
        fh.flush()
        self._stats["bytes_written"] += len(data)

    def get_stats(self) -> Dict:
        """Get recording statistics."""
        uptime = time.time() - self._stats["start_time"] if self._stats["start_time"] else 0
        return {
            "running": self._running,
            "uptime_seconds": uptime,
            "events_recorded": self._stats["events_recorded"],
            "bytes_written": self._stats["bytes_written"],
            "bytes_written_mb": self._stats["bytes_written"] / (1024 * 1024),
            "files_created": self._stats["files_created"],
            "flushes": self._stats["flushes"],
            "errors": self._stats["errors"],
            "events_by_type": dict(self._stats["events_by_type"]),
            "buffer_pending": self._buffer_count,
            "events_per_second": (
                self._stats["events_recorded"] / uptime if uptime > 0 else 0
            ),
        }


# ── Standalone Daemon Runner ────────────────────────────────

def run_recorder_daemon(
    symbols: Optional[List[str]] = None,
    data_dir: str = "data/recorded",
    exchanges: Optional[List[str]] = None,
):
    """
    Run the recording daemon as a standalone process.
    Handles SIGINT/SIGTERM for graceful shutdown.
    """
    from .exchange_streams import StreamConfig, StreamManager

    symbols = symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    exchanges = exchanges or ["binance", "bybit", "okx", "deribit"]

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("Starting CoinScopeAI Recording Daemon")
    logger.info("Symbols: %s", symbols)
    logger.info("Exchanges: %s", exchanges)
    logger.info("Data directory: %s", data_dir)

    # Initialize components
    event_bus = EventBus()
    stream_config = StreamConfig(symbols=symbols)
    stream_manager = StreamManager(event_bus, stream_config)
    recorder_config = RecorderConfig(data_dir=data_dir)
    recorder = RecordingDaemon(event_bus, recorder_config)

    # Graceful shutdown
    shutdown_event = threading.Event()

    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — initiating graceful shutdown", sig_name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start
    recorder.start()
    stream_manager.start(exchanges)

    logger.info("Recording daemon running — press Ctrl+C to stop")

    # Stats reporting loop
    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=60)
            if not shutdown_event.is_set():
                stats = recorder.get_stats()
                stream_stats = stream_manager.get_stats()
                connected = sum(
                    1 for s in stream_stats.values() if s.get("connected")
                )
                logger.info(
                    "STATS | events=%d | %.1f MB | %.1f evt/s | %d/%d exchanges connected",
                    stats["events_recorded"],
                    stats["bytes_written_mb"],
                    stats["events_per_second"],
                    connected,
                    len(stream_stats),
                )
    except KeyboardInterrupt:
        pass

    # Shutdown
    logger.info("Shutting down...")
    stream_manager.stop()
    recorder.stop()
    logger.info("Recording daemon stopped cleanly")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CoinScopeAI Recording Daemon")
    parser.add_argument(
        "--symbols", nargs="+",
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
        help="Symbols to record",
    )
    parser.add_argument(
        "--data-dir", default="data/recorded",
        help="Directory to store recorded data",
    )
    parser.add_argument(
        "--exchanges", nargs="+",
        default=["binance", "bybit", "okx", "deribit"],
        help="Exchanges to connect to",
    )
    args = parser.parse_args()

    run_recorder_daemon(
        symbols=args.symbols,
        data_dir=args.data_dir,
        exchanges=args.exchanges,
    )

# Backwards-compatibility alias
StreamRecorder = RecordingDaemon

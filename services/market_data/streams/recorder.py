"""
Historical Data Recorder — saves all stream events to compressed JSONL files.

Features:
- Subscribes to all EventBus events and writes to JSONL.gz files
- Rotates files by time window (hourly by default)
- Graceful shutdown: flushes buffers on SIGINT/SIGTERM
- Organises output: data/<date>/<stream_type>/<exchange>_<symbol>_<hour>.jsonl.gz
"""

from __future__ import annotations

import asyncio
import gzip
import logging
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import orjson

from .base import (
    EventBus,
    EventType,
    FundingRate,
    Liquidation,
    OrderBookUpdate,
    StreamStatus,
    Trade,
    get_event_bus,
    now_ms,
)

logger = logging.getLogger("coinscopeai.streams.recorder")


class StreamRecorder:
    """
    Records all EventBus events to compressed JSONL files.

    Usage::

        recorder = StreamRecorder(output_dir="./data")
        await recorder.start()
        # ... streams are running and publishing events ...
        await recorder.stop()  # flushes and closes all files
    """

    def __init__(
        self,
        output_dir: str = "./data/recordings",
        event_bus: Optional[EventBus] = None,
        flush_interval: float = 5.0,
        rotate_interval: float = 3600.0,  # 1 hour
    ):
        self.output_dir = Path(output_dir)
        self.bus = event_bus or get_event_bus()
        self.flush_interval = flush_interval
        self.rotate_interval = rotate_interval
        self._writers: Dict[str, _GzipWriter] = {}
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None
        self._event_count = 0
        self._bytes_written = 0

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.output_dir.mkdir(parents=True, exist_ok=True)
        await self.bus.subscribe_all(self._on_event)
        self._flush_task = asyncio.create_task(self._periodic_flush())
        # Register signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except (NotImplementedError, RuntimeError):
                pass  # Windows or non-main thread
        logger.info("StreamRecorder started → %s", self.output_dir)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self._flush_all()
        await self._close_all()
        logger.info(
            "StreamRecorder stopped — %d events, %.2f MB written",
            self._event_count,
            self._bytes_written / (1024 * 1024),
        )

    async def _on_event(self, event_type: EventType, data: Any) -> None:
        """Callback for all EventBus events."""
        if not self._running:
            return
        try:
            record = self._serialize(event_type, data)
            if record is None:
                return
            writer = self._get_writer(event_type, data)
            writer.write(record)
            self._event_count += 1
        except Exception:
            logger.exception("Recorder write error")

    def _serialize(self, event_type: EventType, data: Any) -> Optional[bytes]:
        """Serialize event to JSON bytes with metadata wrapper."""
        if hasattr(data, "to_dict"):
            payload = data.to_dict()
        elif hasattr(data, "__dict__"):
            payload = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
        else:
            payload = data
        envelope = {
            "event_type": event_type.value,
            "timestamp_ms": now_ms(),
            "data": payload,
        }
        return orjson.dumps(envelope) + b"\n"

    def _get_writer(self, event_type: EventType, data: Any) -> "_GzipWriter":
        """Get or create a writer for this event type + exchange + symbol combo."""
        exchange = getattr(data, "exchange", "unknown")
        symbol = getattr(data, "symbol", "unknown")
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H")

        key = f"{event_type.value}/{exchange}/{symbol}/{date_str}/{hour_str}"
        if key not in self._writers:
            dir_path = self.output_dir / date_str / event_type.value
            dir_path.mkdir(parents=True, exist_ok=True)
            filename = f"{exchange}_{symbol}_{date_str}_{hour_str}.jsonl.gz"
            filepath = dir_path / filename
            self._writers[key] = _GzipWriter(filepath)
            logger.debug("Opened recorder file: %s", filepath)
        return self._writers[key]

    async def _periodic_flush(self) -> None:
        while self._running:
            await asyncio.sleep(self.flush_interval)
            await self._flush_all()

    async def _flush_all(self) -> None:
        for writer in self._writers.values():
            n = writer.flush()
            self._bytes_written += n

    async def _close_all(self) -> None:
        for writer in self._writers.values():
            n = writer.flush()
            self._bytes_written += n
            writer.close()
        self._writers.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "event_count": self._event_count,
            "bytes_written": self._bytes_written,
            "open_files": len(self._writers),
        }


class _GzipWriter:
    """Buffered gzip writer for JSONL data."""

    def __init__(self, path: Path, buffer_size: int = 64 * 1024):
        self._path = path
        self._buffer = bytearray()
        self._buffer_size = buffer_size
        self._file = gzip.open(str(path), "ab", compresslevel=6)
        self._total_bytes = 0

    def write(self, data: bytes) -> None:
        self._buffer.extend(data)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> int:
        if not self._buffer:
            return 0
        n = len(self._buffer)
        self._file.write(bytes(self._buffer))
        self._file.flush()
        self._buffer.clear()
        self._total_bytes += n
        return n

    def close(self) -> None:
        self.flush()
        self._file.close()

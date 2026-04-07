"""
Replay Engine — reads recorded JSONL.gz data and replays events through the
EventBus at configurable speed, so scanners and strategies cannot distinguish
between live and replayed data.

Features:
- Configurable playback speed: 1x, 10x, 100x, or max (no delay)
- Time-windowed playback: start_time / end_time filtering
- Emits events through the same EventBus interface as live streams
- Supports pause/resume
- Reconstructs proper data model objects from serialised records
"""

from __future__ import annotations

import asyncio
import gzip
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import orjson

from .base import (
    EventBus,
    EventType,
    FundingRate,
    Liquidation,
    OrderBookLevel,
    OrderBookUpdate,
    StreamStatus,
    Trade,
    get_event_bus,
    now_ms,
)

logger = logging.getLogger("coinscopeai.streams.replay")


class ReplayEngine:
    """
    Replays recorded market data through the EventBus.

    Usage::

        engine = ReplayEngine(
            data_dir="./data/recordings/2025-01-15",
            speed=10.0,
            start_time_ms=1705276800000,
        )
        await engine.start()
        await engine.wait()  # blocks until replay finishes
    """

    def __init__(
        self,
        data_dir: str,
        event_bus: Optional[EventBus] = None,
        speed: float = 1.0,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
    ):
        self.data_dir = Path(data_dir)
        self.bus = event_bus or get_event_bus()
        self.speed = speed  # 0 = max speed (no delay)
        self.start_time_ms = start_time_ms
        self.end_time_ms = end_time_ms
        self._running = False
        self._paused = False
        self._task: Optional[asyncio.Task] = None
        self._events_replayed = 0
        self._pause_event = asyncio.Event()
        self._pause_event.set()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._events_replayed = 0
        self._task = asyncio.create_task(self._replay_loop())
        logger.info(
            "ReplayEngine started — dir=%s speed=%.1fx window=[%s, %s]",
            self.data_dir, self.speed,
            self.start_time_ms, self.end_time_ms,
        )

    async def stop(self) -> None:
        self._running = False
        self._pause_event.set()  # unblock if paused
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ReplayEngine stopped — %d events replayed", self._events_replayed)

    async def wait(self) -> None:
        """Wait for replay to complete."""
        if self._task:
            await self._task

    def pause(self) -> None:
        self._paused = True
        self._pause_event.clear()
        logger.info("ReplayEngine paused")

    def resume(self) -> None:
        self._paused = False
        self._pause_event.set()
        logger.info("ReplayEngine resumed")

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "events_replayed": self._events_replayed,
            "running": self._running,
            "paused": self._paused,
            "speed": self.speed,
        }

    async def _replay_loop(self) -> None:
        """Main replay loop — reads all files, sorts events, replays with timing."""
        try:
            events = self._load_events()
            if not events:
                logger.warning("No events found in %s", self.data_dir)
                return

            logger.info("Loaded %d events for replay", len(events))

            # Sort by timestamp
            events.sort(key=lambda e: e[0])

            first_ts = events[0][0]
            replay_start = now_ms()

            for ts, event_type, data in events:
                if not self._running:
                    break

                # Wait if paused
                await self._pause_event.wait()

                # Time-window filtering
                if self.start_time_ms and ts < self.start_time_ms:
                    continue
                if self.end_time_ms and ts > self.end_time_ms:
                    break

                # Timing control
                if self.speed > 0:
                    elapsed_data = ts - first_ts
                    elapsed_real = now_ms() - replay_start
                    target_real = elapsed_data / self.speed
                    wait_ms = target_real - elapsed_real
                    if wait_ms > 0:
                        await asyncio.sleep(wait_ms / 1000.0)

                # Reconstruct and publish
                obj = self._deserialize(event_type, data)
                if obj is not None:
                    await self.bus.publish(event_type, obj)
                    self._events_replayed += 1

            logger.info("Replay complete — %d events", self._events_replayed)

        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Replay error")
        finally:
            self._running = False

    def _load_events(self) -> List[Tuple[int, EventType, dict]]:
        """Load and parse all JSONL.gz files from data_dir."""
        events: List[Tuple[int, EventType, dict]] = []
        files = sorted(self.data_dir.rglob("*.jsonl.gz"))
        if not files:
            # Also try uncompressed
            files = sorted(self.data_dir.rglob("*.jsonl"))

        for filepath in files:
            try:
                opener = gzip.open if filepath.suffix == ".gz" else open
                with opener(str(filepath), "rb") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = orjson.loads(line)
                            ts = record.get("timestamp_ms", 0)
                            et_str = record.get("event_type", "")
                            data = record.get("data", {})
                            try:
                                event_type = EventType(et_str)
                            except ValueError:
                                continue
                            events.append((ts, event_type, data))
                        except Exception:
                            continue
            except Exception as exc:
                logger.warning("Failed to read %s: %s", filepath, exc)

        return events

    @staticmethod
    def _deserialize(event_type: EventType, data: dict) -> Any:
        """Reconstruct data model objects from dict."""
        try:
            if event_type == EventType.TRADE:
                return Trade(
                    exchange=data.get("exchange", ""),
                    symbol=data.get("symbol", ""),
                    trade_id=data.get("trade_id", ""),
                    price=float(data.get("price", 0)),
                    quantity=float(data.get("quantity", 0)),
                    side=data.get("side", "buy"),
                    timestamp_ms=int(data.get("timestamp_ms", 0)),
                    received_ms=int(data.get("received_ms", 0)),
                )
            elif event_type in (EventType.ORDERBOOK_UPDATE, EventType.ORDERBOOK_SNAPSHOT):
                bids = [OrderBookLevel(price=float(b[0]), quantity=float(b[1])) for b in data.get("bids", [])]
                asks = [OrderBookLevel(price=float(a[0]), quantity=float(a[1])) for a in data.get("asks", [])]
                return OrderBookUpdate(
                    exchange=data.get("exchange", ""),
                    symbol=data.get("symbol", ""),
                    bids=bids,
                    asks=asks,
                    timestamp_ms=int(data.get("timestamp_ms", 0)),
                    received_ms=int(data.get("received_ms", 0)),
                    is_snapshot=data.get("is_snapshot", False),
                    sequence=data.get("sequence"),
                )
            elif event_type == EventType.FUNDING_RATE:
                return FundingRate(
                    exchange=data.get("exchange", ""),
                    symbol=data.get("symbol", ""),
                    funding_rate=float(data.get("funding_rate", 0)),
                    predicted_rate=float(data["predicted_rate"]) if data.get("predicted_rate") is not None else None,
                    funding_time_ms=int(data.get("funding_time_ms", 0)),
                    timestamp_ms=int(data.get("timestamp_ms", 0)),
                    received_ms=int(data.get("received_ms", 0)),
                    mark_price=float(data["mark_price"]) if data.get("mark_price") is not None else None,
                    index_price=float(data["index_price"]) if data.get("index_price") is not None else None,
                )
            elif event_type == EventType.LIQUIDATION:
                return Liquidation(
                    exchange=data.get("exchange", ""),
                    symbol=data.get("symbol", ""),
                    side=data.get("side", "buy"),
                    price=float(data.get("price", 0)),
                    quantity=float(data.get("quantity", 0)),
                    usd_value=float(data.get("usd_value", 0)),
                    timestamp_ms=int(data.get("timestamp_ms", 0)),
                    received_ms=int(data.get("received_ms", 0)),
                    is_derived=data.get("is_derived", False),
                )
            elif event_type == EventType.STREAM_STATUS:
                return StreamStatus(
                    exchange=data.get("exchange", ""),
                    stream_type=data.get("stream_type", ""),
                    symbol=data.get("symbol", ""),
                    connected=data.get("connected", False),
                    message=data.get("message", ""),
                    timestamp_ms=int(data.get("timestamp_ms", 0)),
                )
        except Exception:
            logger.debug("Failed to deserialize %s event", event_type.value)
        return None

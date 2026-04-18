"""
Funding Rate Ingestion Pipeline — WebSocket + REST
CoinScopeAI | Phase: Data Pipeline

Architecture (3 co-operating asyncio tasks):

  [WS Task]  wss://.../ws/!markPrice@arr
      |  parse markPriceUpdate frames
      v
  asyncio.Queue  ← also receives [REST Task] poll records
      |
  [Writer Task]  batch-dequeue → FundingRateStore.insert_batch()
      |
  [Alert Task]   FundingRateStore.get_extremes() → FundingRateAlerter

WebSocket stream: !markPrice@arr
  - Broadcasts mark price + funding rate for ALL USDT-M perps every 3 s.
  - Payload per symbol:
      {
        "e": "markPriceUpdate",  "E": <event_ts_ms>,
        "s": "BTCUSDT",
        "p": "<mark_price>",     "i": "<index_price>",
        "r": "<funding_rate>",   "T": <next_funding_time_ms>
      }

REST supplement: GET /fapi/v1/premiumIndex
  - Polled every REST_POLL_INTERVAL_S seconds as a fallback / cross-check.
  - Weight: 1 (single symbol) or 10 (all symbols — we use all-symbols).

⚠️  Binance WebSocket migration note (effective 2026-04-23):
    Public market streams will move to path /market/!markPrice@arr.
    The WS_STREAM_PATH env var already handles this — set it to
    /market on or after 2026-04-23; leave it at /ws until then.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Callable, List, Optional

import requests
import websockets
from websockets.exceptions import ConnectionClosed

from funding_rate_store import FundingRateRecord, FundingRateStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (read once at import time so the module is self-contained)
# ---------------------------------------------------------------------------

def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")

def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


class IngestionConfig:
    """
    Resolved at construction time from environment variables.

    Env vars (all optional — sensible defaults provided):
        TESTNET_MODE                 true | false  (default: true)
        BINANCE_WS_TESTNET_URL       wss://stream.binancefuture.com
        BINANCE_WS_MAINNET_URL       wss://fstream.binance.com
        WS_STREAM_PATH               /ws  (becomes /market after 2026-04-23)
        REST_TESTNET_URL             https://testnet.binancefuture.com
        REST_MAINNET_URL             https://fapi.binance.com
        REST_POLL_INTERVAL_S         60
        WRITER_BATCH_SIZE            50
        WRITER_FLUSH_INTERVAL_S      5
    """
    def __init__(self) -> None:
        self.is_testnet: bool = _env_bool("TESTNET_MODE", True)

        # WebSocket base URLs
        _ws_testnet = os.getenv(
            "BINANCE_WS_TESTNET_URL", "wss://stream.binancefuture.com"
        )
        _ws_mainnet = os.getenv(
            "BINANCE_WS_MAINNET_URL", "wss://fstream.binance.com"
        )
        # Stream path — change to /market on/after 2026-04-23
        _stream_path = os.getenv("WS_STREAM_PATH", "/ws")

        ws_base = _ws_testnet if self.is_testnet else _ws_mainnet
        self.ws_url: str = f"{ws_base.rstrip('/')}{_stream_path}/!markPrice@arr"

        # REST base URLs
        _rest_testnet = os.getenv(
            "REST_TESTNET_URL", "https://testnet.binancefuture.com"
        )
        _rest_mainnet = os.getenv(
            "REST_MAINNET_URL", "https://fapi.binance.com"
        )
        self.rest_base: str = _rest_testnet if self.is_testnet else _rest_mainnet

        # Tuning
        self.rest_poll_interval: int = int(
            _env_float("REST_POLL_INTERVAL_S", 60)
        )
        self.writer_batch_size: int = int(
            _env_float("WRITER_BATCH_SIZE", 50)
        )
        self.writer_flush_interval: float = _env_float(
            "WRITER_FLUSH_INTERVAL_S", 5.0
        )

    def describe(self) -> str:
        env_label = "TESTNET ⚠️" if self.is_testnet else "MAINNET 🔴"
        return (
            f"[IngestionConfig] env={env_label}\n"
            f"  WS  → {self.ws_url}\n"
            f"  REST → {self.rest_base}/fapi/v1/premiumIndex\n"
            f"  REST poll every {self.rest_poll_interval}s | "
            f"batch={self.writer_batch_size} flush_every={self.writer_flush_interval}s"
        )


# ---------------------------------------------------------------------------
# WebSocket consumer
# ---------------------------------------------------------------------------

class FundingRateWSConsumer:
    """
    Connects to Binance's !markPrice@arr stream and pushes parsed
    FundingRateRecord objects onto the shared asyncio.Queue.

    Reconnects automatically with exponential back-off on any failure.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        config: IngestionConfig,
    ) -> None:
        self.queue = queue
        self.cfg = config
        self._running = False
        self._ticks_received: int = 0
        self._last_tick_ts: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Main loop — never returns under normal operation.
        Reconnects with back-off on errors.
        """
        self._running = True
        backoff = 1  # seconds; doubles on failure, caps at 60

        while self._running:
            try:
                await self._connect_and_consume()
                backoff = 1  # reset on clean disconnect
            except asyncio.CancelledError:
                logger.info("[WSConsumer] Cancelled — shutting down.")
                break
            except Exception as exc:
                logger.error(
                    f"[WSConsumer] Error: {exc!r} — reconnecting in {backoff}s"
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

        self._running = False

    def stop(self) -> None:
        self._running = False

    @property
    def stats(self) -> dict:
        return {
            "ticks_received": self._ticks_received,
            "last_tick_age_s": round(time.time() - self._last_tick_ts, 1)
            if self._last_tick_ts else None,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _connect_and_consume(self) -> None:
        logger.info(f"[WSConsumer] Connecting → {self.cfg.ws_url}")
        async with websockets.connect(
            self.cfg.ws_url,
            ping_interval=20,    # send WS-level pings every 20s
            ping_timeout=10,     # close if no pong within 10s
            close_timeout=5,
            max_size=2**22,      # 4 MB — the all-symbols frame can be large
        ) as ws:
            logger.info("[WSConsumer] ✅ Connected")
            async for raw in ws:
                if not self._running:
                    break
                self._handle_raw(raw)

    def _handle_raw(self, raw: str) -> None:
        """
        Parse a single WebSocket message.

        The !markPrice@arr frame is a JSON array of markPriceUpdate objects.
        Each element has the structure described in the module docstring.
        """
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[WSConsumer] Non-JSON frame: {raw[:120]}")
            return

        # The stream sends an array; each element is one symbol's update
        if not isinstance(payload, list):
            # Might be a subscription confirmation or error frame
            logger.debug(f"[WSConsumer] Non-list frame: {payload}")
            return

        now_ms = int(time.time() * 1000)
        records: List[FundingRateRecord] = []

        for item in payload:
            rec = self._parse_item(item, now_ms)
            if rec is not None:
                records.append(rec)

        if records:
            # Non-blocking put — if queue is full, drop (backpressure protection)
            try:
                self.queue.put_nowait(records)
            except asyncio.QueueFull:
                logger.warning(
                    f"[WSConsumer] Queue full — dropped {len(records)} records"
                )
            self._ticks_received += len(records)
            self._last_tick_ts = time.time()

    @staticmethod
    def _parse_item(
        item: dict,
        now_ms: int,
    ) -> Optional[FundingRateRecord]:
        """
        Parse one markPriceUpdate dict into a FundingRateRecord.
        Returns None if the item is malformed or not a markPriceUpdate.
        """
        if item.get("e") != "markPriceUpdate":
            return None
        try:
            return FundingRateRecord(
                symbol=str(item["s"]).upper(),
                funding_rate=float(item.get("r", 0) or 0),
                mark_price=float(item.get("p", 0) or 0),
                index_price=float(item["i"]) if item.get("i") else None,
                next_funding_time=int(item.get("T", 0) or 0),
                ingested_at=now_ms,
                source="ws",
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.debug(f"[WSConsumer] Parse error: {exc!r} item={item}")
            return None


# ---------------------------------------------------------------------------
# REST poller (supplement / fallback)
# ---------------------------------------------------------------------------

class FundingRateRESTPoller:
    """
    Polls GET /fapi/v1/premiumIndex?symbol= (all-symbols variant) at a
    fixed interval and pushes records onto the shared queue.

    This supplements the WebSocket stream to ensure we never miss data
    during WS reconnections and to cross-check recorded values.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        config: IngestionConfig,
    ) -> None:
        self.queue = queue
        self.cfg = config
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "CoinScopeAI/1.0"
        self._poll_count: int = 0

    async def run(self) -> None:
        """Poll at `REST_POLL_INTERVAL_S` intervals until cancelled."""
        logger.info(
            f"[RESTPoller] Starting — polling every {self.cfg.rest_poll_interval}s"
        )
        while True:
            try:
                await asyncio.sleep(self.cfg.rest_poll_interval)
                records = await asyncio.get_event_loop().run_in_executor(
                    None, self._fetch_all
                )
                if records:
                    try:
                        self.queue.put_nowait(records)
                    except asyncio.QueueFull:
                        logger.warning(
                            f"[RESTPoller] Queue full — dropped REST batch "
                            f"({len(records)} records)"
                        )
                    self._poll_count += 1
                    logger.debug(
                        f"[RESTPoller] Poll #{self._poll_count}: "
                        f"{len(records)} symbols"
                    )
            except asyncio.CancelledError:
                logger.info("[RESTPoller] Cancelled.")
                break
            except Exception as exc:
                logger.error(f"[RESTPoller] Error: {exc!r}")

    def _fetch_all(self) -> List[FundingRateRecord]:
        """
        Synchronous REST fetch (runs in executor so it doesn't block the loop).
        Returns an empty list on error.
        Weight: 10 for all-symbols premiumIndex.
        """
        url = f"{self.cfg.rest_base}/fapi/v1/premiumIndex"
        now_ms = int(time.time() * 1000)
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(f"[RESTPoller] Fetch failed: {exc!r}")
            return []

        records: List[FundingRateRecord] = []
        for item in data:
            try:
                sym = str(item.get("symbol", "")).upper()
                if not sym.endswith("USDT"):
                    continue  # only USDT-M perps
                records.append(FundingRateRecord(
                    symbol=sym,
                    funding_rate=float(item.get("lastFundingRate", 0) or 0),
                    mark_price=float(item.get("markPrice", 0) or 0),
                    index_price=float(item.get("indexPrice", 0) or 0) or None,
                    next_funding_time=int(item.get("nextFundingTime", 0) or 0),
                    ingested_at=now_ms,
                    source="rest",
                ))
            except (ValueError, TypeError, KeyError) as exc:
                logger.debug(f"[RESTPoller] Skip item {item}: {exc!r}")
        return records


# ---------------------------------------------------------------------------
# Writer task (queue → DB)
# ---------------------------------------------------------------------------

class FundingRateWriter:
    """
    Drains the shared asyncio.Queue and flushes batches to the store.

    Accumulates records up to WRITER_BATCH_SIZE or WRITER_FLUSH_INTERVAL_S,
    whichever comes first.  This amortises SQLite write overhead while
    keeping latency low.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        store: FundingRateStore,
        config: IngestionConfig,
        on_new_record: Optional[Callable[[List[FundingRateRecord]], None]] = None,
    ) -> None:
        """
        Args:
            on_new_record: Optional callback fired with newly-inserted records.
                           Used by the alerter to react immediately to data.
        """
        self.queue = queue
        self.store = store
        self.cfg = config
        self.on_new_record = on_new_record
        self._total_written: int = 0
        self._total_dropped: int = 0

    async def run(self) -> None:
        """Drain the queue indefinitely."""
        buffer: List[FundingRateRecord] = []
        last_flush = time.monotonic()

        logger.info(
            f"[Writer] Starting — batch_size={self.cfg.writer_batch_size} "
            f"flush_interval={self.cfg.writer_flush_interval}s"
        )

        while True:
            try:
                # Wait for next batch from the queue, with a timeout so we
                # can flush even when traffic is low
                timeout = max(
                    0.0,
                    self.cfg.writer_flush_interval - (time.monotonic() - last_flush),
                )
                batch: List[FundingRateRecord] = await asyncio.wait_for(
                    self.queue.get(), timeout=timeout
                )
                buffer.extend(batch)
                self.queue.task_done()
            except asyncio.TimeoutError:
                pass  # flush timer expired — fall through to flush check
            except asyncio.CancelledError:
                # Flush whatever remains before exiting
                if buffer:
                    await self._flush(buffer)
                logger.info("[Writer] Cancelled.")
                break

            # Flush if buffer is large enough or flush timer has expired
            elapsed = time.monotonic() - last_flush
            if len(buffer) >= self.cfg.writer_batch_size or (
                buffer and elapsed >= self.cfg.writer_flush_interval
            ):
                written = await self._flush(buffer)
                buffer = []
                last_flush = time.monotonic()
                if written:
                    logger.info(
                        f"[Writer] Flushed {written} new rows "
                        f"(total={self._total_written} dup_dropped={self._total_dropped})"
                    )

    async def _flush(self, records: List[FundingRateRecord]) -> int:
        """Write batch to store in executor (SQLite is synchronous)."""
        written = await asyncio.get_event_loop().run_in_executor(
            None, self.store.insert_batch, records
        )
        dropped = len(records) - written
        self._total_written += written
        self._total_dropped += dropped

        # Notify alerter about newly written records
        if written > 0 and self.on_new_record:
            new_recs = records[:written]  # approximate — first N are new
            try:
                self.on_new_record(new_recs)
            except Exception as exc:
                logger.debug(f"[Writer] on_new_record callback error: {exc!r}")

        return written

    @property
    def stats(self) -> dict:
        return {
            "total_written": self._total_written,
            "total_dropped_dup": self._total_dropped,
        }


# ---------------------------------------------------------------------------
# Top-level pipeline assembler
# ---------------------------------------------------------------------------

class FundingRatePipeline:
    """
    Assembles and starts all three pipeline tasks:
        1. WS consumer   — streams !markPrice@arr into the queue
        2. REST poller   — polls /premiumIndex every N seconds
        3. Writer        — drains queue → SQLite via FundingRateStore

    Usage:
        pipeline = FundingRatePipeline(store, on_new_record=alerter.check)
        await pipeline.run()          # blocks until cancelled
    """

    def __init__(
        self,
        store: FundingRateStore,
        config: Optional[IngestionConfig] = None,
        on_new_record: Optional[Callable[[List[FundingRateRecord]], None]] = None,
    ) -> None:
        self.store = store
        self.cfg = config or IngestionConfig()
        self.on_new_record = on_new_record

        # Shared queue between producers (WS + REST) and the writer
        # Max size guards against runaway memory if the writer falls behind
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)

        self._ws = FundingRateWSConsumer(self._queue, self.cfg)
        self._rest = FundingRateRESTPoller(self._queue, self.cfg)
        self._writer = FundingRateWriter(
            self._queue, self.store, self.cfg,
            on_new_record=self.on_new_record,
        )

    async def run(self) -> None:
        logger.info(self.cfg.describe())
        tasks = [
            asyncio.create_task(self._ws.run(), name="ws-consumer"),
            asyncio.create_task(self._rest.run(), name="rest-poller"),
            asyncio.create_task(self._writer.run(), name="writer"),
        ]
        try:
            # Wait for any task to finish (normally they run forever)
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_EXCEPTION
            )
            for t in done:
                if t.exception():
                    logger.error(f"[Pipeline] Task {t.get_name()} raised: {t.exception()!r}")
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("[Pipeline] All tasks stopped.")

    @property
    def stats(self) -> dict:
        return {
            "ws": self._ws.stats,
            "writer": self._writer.stats,
            "queue_size": self._queue.qsize(),
            "store": self.store.get_stats(),
        }

"""
collector.py — Funding Rate Collector for CoinScopeAI.

Architecture:
  1. REST bootstrap: GET /fapi/v1/premiumIndex (all symbols) on startup and every 5 min
  2. WebSocket stream: !markPrice@arr@1s — real-time mark price + funding rate for all symbols
  3. asyncio.Queue: decouples ingestion (WebSocket) from storage writes

WebSocket message format (one item in the array):
  {
    "e": "markPriceUpdate",
    "E": 1562305380000,    # event time (ms)
    "s": "BTCUSDT",        # symbol
    "p": "11794.15",       # mark price
    "i": "11784.62",       # index price
    "P": "11784.25",       # estimated settle price
    "r": "0.00038167",     # funding rate
    "T": 1562306400000     # next funding time (ms)
  }

Rate limit notes:
  - WebSocket streams consume 0 REST weight — prefer over polling
  - REST bootstrap: /fapi/v1/premiumIndex (no symbol) costs weight=1, returns all symbols
  - We REST-poll only every 5 min as a safety net (catches missed WS events)
"""

import asyncio
import json
import logging
import time
from typing import Callable, List, Optional

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from .config import FundingRateConfig
from .storage import FundingRateDB, FundingRateRecord

log = logging.getLogger(__name__)


# ── Collector ─────────────────────────────────────────────────────────────────

class FundingRateCollector:
    """
    Collects real-time funding rates from Binance Futures.

    Runs two concurrent loops:
      - _ws_loop():   WebSocket stream consumer (primary, real-time)
      - _rest_loop(): REST polling fallback (backup, every 5 min)

    Both funnel records into self._queue.
    A separate _writer_loop() drains the queue into the DB.

    Callbacks:
      on_record:  called for every new/updated funding rate record
      on_extreme: called when a symbol's |rate| exceeds the warning threshold
    """

    # WS stream path: !markPrice@arr@1s = all symbols, 1-second updates
    WS_STREAM_PATH = "/ws/!markPrice@arr@1s"

    # Reconnection settings
    WS_BACKOFF_INITIAL = 1     # seconds
    WS_BACKOFF_MAX     = 60    # seconds
    WS_BACKOFF_FACTOR  = 2

    # Weight cost of the all-symbols REST endpoint
    REST_PREMIUM_INDEX_WEIGHT = 10  # conservative estimate

    def __init__(
        self,
        config: FundingRateConfig,
        db: FundingRateDB,
        on_record:  Optional[Callable[[FundingRateRecord], None]] = None,
        on_extreme: Optional[Callable[[FundingRateRecord], None]] = None,
        extreme_threshold: float = 0.001,  # 0.1% funding rate
    ):
        self.cfg              = config
        self.db               = db
        self.on_record        = on_record
        self.on_extreme       = on_extreme
        self.extreme_threshold = extreme_threshold

        # Internal state
        self._queue: asyncio.Queue[List[FundingRateRecord]] = asyncio.Queue(maxsize=1000)
        self._running = False
        self._last_rest_ts = 0.0     # epoch seconds of last REST bootstrap
        self._symbol_count = 0       # how many symbols we're tracking
        self._ws_errors = 0          # total WS reconnections (for monitoring)

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start all collector loops. Runs until stop() is called or the process exits.
        Call this with: await collector.start()
        """
        self._running = True
        log.info("[Collector] Starting — endpoint: %s", self.cfg.ws_url)

        # Run all loops concurrently
        await asyncio.gather(
            self._ws_loop(),
            self._rest_loop(),
            self._writer_loop(),
        )

    async def stop(self) -> None:
        """Signal all loops to stop gracefully."""
        self._running = False
        log.info("[Collector] Stop requested.")

    @property
    def symbol_count(self) -> int:
        return self._symbol_count

    @property
    def ws_reconnect_count(self) -> int:
        return self._ws_errors

    # ── WebSocket Loop ────────────────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """
        Persistent WebSocket connection with exponential backoff reconnection.

        Binance sends a ping every 3 min; websockets library auto-responds.
        If the connection drops without an error (silent disconnect after 10 min
        without pong), the library raises ConnectionClosed which we catch here.
        """
        backoff = self.WS_BACKOFF_INITIAL
        url = f"{self.cfg.ws_url}{self.WS_STREAM_PATH}"

        while self._running:
            try:
                log.info("[WS] Connecting to %s", url)
                async with websockets.connect(
                    url,
                    ping_interval=20,   # keep-alive ping every 20s
                    ping_timeout=10,    # error if no pong within 10s
                    close_timeout=5,
                ) as ws:
                    log.info("[WS] Connected ✓")
                    backoff = self.WS_BACKOFF_INITIAL  # reset on successful connect
                    await self._ws_receive_loop(ws)

            except ConnectionClosed as e:
                self._ws_errors += 1
                log.warning("[WS] Connection closed: %s — reconnecting in %ds", e, backoff)

            except WebSocketException as e:
                self._ws_errors += 1
                log.error("[WS] WebSocket error: %s — reconnecting in %ds", e, backoff)

            except Exception as e:
                self._ws_errors += 1
                log.error("[WS] Unexpected error: %s — reconnecting in %ds", e, backoff)

            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * self.WS_BACKOFF_FACTOR, self.WS_BACKOFF_MAX)

    async def _ws_receive_loop(self, ws) -> None:
        """Inner receive loop for a live WebSocket connection."""
        async for raw_msg in ws:
            if not self._running:
                break

            records = self._parse_ws_message(raw_msg)
            if records:
                # Non-blocking enqueue; if queue is full, drop (don't block the receiver)
                try:
                    self._queue.put_nowait(records)
                except asyncio.QueueFull:
                    log.warning("[WS] Queue full — dropping %d records", len(records))

    def _parse_ws_message(self, raw: str) -> List[FundingRateRecord]:
        """
        Parse a !markPrice@arr message into a list of FundingRateRecord.

        The message is a JSON array. Each element is a symbol's mark price update.
        We only care about elements that have a funding rate ("r" field).
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            log.debug("[WS] Non-JSON message: %r", raw[:200])
            return []

        if not isinstance(data, list):
            # Could be a subscription confirmation or other control message
            return []

        now_ms = int(time.time() * 1000)
        records = []

        for item in data:
            # "r" is the funding rate — only present for perpetual futures
            # Some items (e.g. delivery contracts) omit "r"
            r_str = item.get("r")
            if r_str is None or r_str == "":
                continue

            try:
                records.append(FundingRateRecord(
                    symbol            = item["s"],
                    funding_rate      = float(r_str),
                    next_funding_time = int(item.get("T", 0)),
                    mark_price        = float(item.get("p", 0)),
                    index_price       = float(item.get("i", 0)),
                    collected_at      = now_ms,
                ))
            except (KeyError, ValueError) as e:
                log.debug("[WS] Failed to parse item %r: %s", item, e)

        return records

    # ── REST Backup Loop ──────────────────────────────────────────────────────

    async def _rest_loop(self) -> None:
        """
        Polls /fapi/v1/premiumIndex every REST_BOOTSTRAP_INTERVAL seconds as a safety net.

        This catches any symbols whose WS updates might have been missed during
        a reconnect window. It also bootstraps the DB on startup before the
        WS connection is established.
        """
        from .config import REST_BOOTSTRAP_INTERVAL

        # Initial bootstrap: fetch immediately on startup
        await asyncio.sleep(2)  # brief delay to let WS connection start first

        while self._running:
            try:
                await self._fetch_rest_snapshot()
            except Exception as e:
                log.error("[REST] Snapshot failed: %s", e)

            await asyncio.sleep(REST_BOOTSTRAP_INTERVAL)

    async def _fetch_rest_snapshot(self) -> None:
        """
        GET /fapi/v1/premiumIndex (no symbol = all symbols).
        Returns array of all perpetual futures with current mark price + funding rate.
        Weight: 10 (conservative; actual varies by exchange info)
        """
        url = f"{self.cfg.rest_url}/fapi/v1/premiumIndex"
        headers = {"X-MBX-APIKEY": self.cfg.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:

                # Track rate limit from response header
                used_weight = resp.headers.get("X-MBX-USED-WEIGHT-1M", "?")
                log.debug("[REST] Used weight: %s/2400", used_weight)

                if resp.status == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    log.warning("[REST] Rate limited — backing off %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    return

                resp.raise_for_status()
                data = await resp.json()

        if not isinstance(data, list):
            log.error("[REST] Unexpected response shape: %r", str(data)[:200])
            return

        now_ms = int(time.time() * 1000)
        records = []

        for item in data:
            # Only include perpetuals (delivery contracts have empty fundingRate)
            r_str = item.get("lastFundingRate", "")
            if not r_str:
                continue
            try:
                records.append(FundingRateRecord(
                    symbol            = item["symbol"],
                    funding_rate      = float(r_str),
                    next_funding_time = int(item.get("nextFundingTime", 0)),
                    mark_price        = float(item.get("markPrice", 0)),
                    index_price       = float(item.get("indexPrice", 0)),
                    collected_at      = now_ms,
                ))
            except (KeyError, ValueError) as e:
                log.debug("[REST] Failed to parse item %r: %s", item, e)

        if records:
            await self._queue.put(records)
            log.info("[REST] Bootstrapped %d symbols (last funding rates)", len(records))
            self._last_rest_ts = time.time()

    # ── Writer Loop ───────────────────────────────────────────────────────────

    async def _writer_loop(self) -> None:
        """
        Drains the queue and writes records to the DB.

        Runs in the same event loop as the receiver, but yields control
        after each batch so the WS receive loop doesn't starve.

        Also triggers:
          - on_record callback for every record
          - on_extreme callback for records above the alert threshold
          - Periodic history snapshot (once per SNAPSHOT_SAVE_INTERVAL)
        """
        from .config import SNAPSHOT_SAVE_INTERVAL

        last_snapshot_ts = 0.0

        while self._running or not self._queue.empty():
            # Wait for up to 1 second for a batch; continue loop even if empty
            try:
                records = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No data — check if we should save a snapshot and loop
                now = time.time()
                if last_snapshot_ts == 0 or (now - last_snapshot_ts) >= SNAPSHOT_SAVE_INTERVAL:
                    await self._save_snapshot()
                    last_snapshot_ts = now
                continue

            # Write each record to live table and fire callbacks
            for rec in records:
                try:
                    self.db.upsert_live(rec)
                except Exception as e:
                    log.error("[Writer] DB write error for %s: %s", rec.symbol, e)
                    continue

                # Fire the general record callback
                if self.on_record:
                    try:
                        self.on_record(rec)
                    except Exception as e:
                        log.debug("[Writer] on_record callback error: %s", e)

                # Fire the extreme-rate callback
                if (self.on_extreme
                        and abs(rec.funding_rate) >= self.extreme_threshold):
                    try:
                        self.on_extreme(rec)
                    except Exception as e:
                        log.debug("[Writer] on_extreme callback error: %s", e)

            # Update symbol count from first large batch (REST bootstrap)
            if len(records) > 10:
                self._symbol_count = self.db.symbol_count()

            self._queue.task_done()

            # Check if it's time for a history snapshot
            now = time.time()
            if last_snapshot_ts == 0 or (now - last_snapshot_ts) >= SNAPSHOT_SAVE_INTERVAL:
                await self._save_snapshot()
                last_snapshot_ts = now

        log.info("[Writer] Loop exited.")

    async def _save_snapshot(self) -> None:
        """Write current live table into history (non-blocking via thread executor)."""
        loop = asyncio.get_running_loop()
        try:
            # DB writes are sync; run in default thread pool to avoid blocking the event loop
            all_records = await loop.run_in_executor(None, self.db.get_all_live)
            if all_records:
                await loop.run_in_executor(None, self.db.save_snapshot, all_records)
                log.info("[Writer] History snapshot saved: %d symbols", len(all_records))
        except Exception as e:
            log.error("[Writer] Snapshot error: %s", e)

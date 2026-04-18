"""
alert_queue.py — Priority-Based Async Alert Queue
==================================================
Serialises outgoing alerts through a priority queue so that high-severity
alerts (circuit breakers, errors) are sent before informational ones, and
so that bursts of signals don't overwhelm downstream channels.

Priority levels (lower number = higher priority)
-------------------------------------------------
  0 — CRITICAL   circuit breaker, system errors
  1 — HIGH        strong/very-strong trade signals
  2 — NORMAL      moderate/weak signals, status updates
  3 — LOW         daily summaries, info messages

Architecture
------------
* One asyncio.PriorityQueue backing the queue
* One background worker coroutine drains the queue and dispatches
* Worker calls both TelegramNotifier and WebhookDispatcher
* Max queue size configurable (default 200); excess items are dropped
  with a WARNING logged
* Graceful shutdown: flush remaining items or give up after DRAIN_TIMEOUT_S

Usage
-----
    queue = AlertQueue(notifier, dispatcher)
    await queue.start()

    await queue.enqueue_signal(signal, setup, priority=AlertPriority.HIGH)
    await queue.enqueue_status("Engine restarted")
    await queue.enqueue_error("API timeout", detail="...")

    await queue.stop()
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

from alerts.telegram_notifier import TelegramNotifier
from alerts.webhook_dispatcher import WebhookDispatcher
from signals.confluence_scorer import Signal
from signals.entry_exit_calculator import TradeSetup
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_QUEUE_SIZE  = 200
DRAIN_TIMEOUT_S = 10.0    # seconds to wait for queue drain on shutdown
WORKER_SLEEP_S  = 0.05    # polling interval when queue is empty


class AlertPriority(IntEnum):
    CRITICAL = 0
    HIGH     = 1
    NORMAL   = 2
    LOW      = 3


class AlertType(str):
    SIGNAL          = "signal"
    STATUS          = "status"
    ERROR           = "error"
    CIRCUIT_BREAKER = "circuit_breaker"
    DAILY_SUMMARY   = "daily_summary"
    STARTUP         = "startup"


# ---------------------------------------------------------------------------
# Alert item — placed on the queue
# ---------------------------------------------------------------------------

@dataclass(order=True)
class AlertItem:
    """
    A queued alert item.  Ordering is by (priority, sequence) so items with
    equal priority are dispatched FIFO.
    """
    priority: int
    sequence: int                        # monotonically increasing counter
    alert_type: str      = field(compare=False)
    payload: dict        = field(compare=False, default_factory=dict)
    # Rich objects are stored separately (not JSON-serialisable as-is)
    signal: Optional[Signal]     = field(compare=False, default=None)
    setup:  Optional[TradeSetup] = field(compare=False, default=None)


# ---------------------------------------------------------------------------
# Alert Queue
# ---------------------------------------------------------------------------

class AlertQueue:
    """
    Priority-driven async dispatch queue for all CoinScopeAI alerts.

    Parameters
    ----------
    notifier   : TelegramNotifier instance
    dispatcher : WebhookDispatcher instance (optional)
    max_size   : Maximum items in queue before drops occur
    """

    def __init__(
        self,
        notifier:   TelegramNotifier,
        dispatcher: Optional[WebhookDispatcher] = None,
        max_size:   int = MAX_QUEUE_SIZE,
    ) -> None:
        self._notifier   = notifier
        self._dispatcher = dispatcher
        self._queue: asyncio.PriorityQueue[AlertItem] = asyncio.PriorityQueue(maxsize=max_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._sequence = 0
        self._dropped  = 0
        self._dispatched = 0

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(
            self._worker(), name="alert_queue_worker"
        )
        logger.info("AlertQueue started (max_size=%d).", self._queue.maxsize)

    async def stop(self, drain: bool = True) -> None:
        """Stop the worker, optionally draining remaining items first."""
        self._running = False
        if drain and not self._queue.empty():
            logger.info(
                "AlertQueue draining %d remaining items…", self._queue.qsize()
            )
            try:
                await asyncio.wait_for(self._drain(), timeout=DRAIN_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.warning(
                    "AlertQueue drain timed out. %d items dropped.", self._queue.qsize()
                )
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info(
            "AlertQueue stopped. dispatched=%d dropped=%d",
            self._dispatched, self._dropped,
        )

    # ── Enqueue methods ──────────────────────────────────────────────────

    async def enqueue_signal(
        self,
        signal: Signal,
        setup:  TradeSetup,
        priority: AlertPriority = AlertPriority.NORMAL,
    ) -> bool:
        """Enqueue a trade signal alert."""
        item = AlertItem(
            priority   = int(priority),
            sequence   = self._next_seq(),
            alert_type = AlertType.SIGNAL,
            signal     = signal,
            setup      = setup,
        )
        return await self._enqueue(item)

    async def enqueue_status(
        self,
        message: str,
        emoji:   str = "ℹ️",
        priority: AlertPriority = AlertPriority.LOW,
    ) -> bool:
        item = AlertItem(
            priority   = int(priority),
            sequence   = self._next_seq(),
            alert_type = AlertType.STATUS,
            payload    = {"message": message, "emoji": emoji},
        )
        return await self._enqueue(item)

    async def enqueue_error(
        self,
        message: str,
        detail:  str = "",
        priority: AlertPriority = AlertPriority.HIGH,
    ) -> bool:
        item = AlertItem(
            priority   = int(priority),
            sequence   = self._next_seq(),
            alert_type = AlertType.ERROR,
            payload    = {"message": message, "detail": detail},
        )
        return await self._enqueue(item)

    async def enqueue_circuit_breaker(
        self,
        reason:         str,
        daily_loss_pct: float,
    ) -> bool:
        item = AlertItem(
            priority   = int(AlertPriority.CRITICAL),
            sequence   = self._next_seq(),
            alert_type = AlertType.CIRCUIT_BREAKER,
            payload    = {"reason": reason, "daily_loss_pct": daily_loss_pct},
        )
        return await self._enqueue(item)

    async def enqueue_startup(self) -> bool:
        item = AlertItem(
            priority   = int(AlertPriority.NORMAL),
            sequence   = self._next_seq(),
            alert_type = AlertType.STARTUP,
        )
        return await self._enqueue(item)

    async def enqueue_daily_summary(
        self,
        total_signals: int,
        actionable:    int,
        top_signals:   list[Signal],
    ) -> bool:
        item = AlertItem(
            priority   = int(AlertPriority.LOW),
            sequence   = self._next_seq(),
            alert_type = AlertType.DAILY_SUMMARY,
            payload    = {
                "total_signals": total_signals,
                "actionable":    actionable,
                "top_signals":   top_signals,
            },
        )
        return await self._enqueue(item)

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _enqueue(self, item: AlertItem) -> bool:
        if self._queue.full():
            self._dropped += 1
            logger.warning(
                "AlertQueue full (%d). Dropping %s alert (total dropped=%d).",
                self._queue.maxsize, item.alert_type, self._dropped,
            )
            return False
        await self._queue.put(item)
        return True

    async def _worker(self) -> None:
        """Background loop that drains and dispatches queued alerts."""
        while self._running:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                await asyncio.sleep(WORKER_SLEEP_S)
                continue

            try:
                await self._dispatch_item(item)
                self._dispatched += 1
            except Exception as exc:
                logger.error("AlertQueue dispatch error for %s: %s", item.alert_type, exc)
            finally:
                self._queue.task_done()

    async def _drain(self) -> None:
        """Drain remaining items without stopping (used during shutdown)."""
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                await self._dispatch_item(item)
                self._dispatched += 1
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
            except Exception as exc:
                logger.error("AlertQueue drain error: %s", exc)
                self._queue.task_done()

    async def _dispatch_item(self, item: AlertItem) -> None:
        """Route an alert item to the appropriate sender(s)."""
        t = item.alert_type

        if t == AlertType.SIGNAL and item.signal and item.setup:
            await self._notifier.send_signal(item.signal, item.setup)
            if self._dispatcher:
                await self._dispatcher.dispatch_signal(item.signal, item.setup)

        elif t == AlertType.STATUS:
            msg   = item.payload.get("message", "")
            emoji = item.payload.get("emoji", "ℹ️")
            await self._notifier.send_status(msg, emoji)
            if self._dispatcher:
                await self._dispatcher.dispatch_status(msg)

        elif t == AlertType.ERROR:
            msg    = item.payload.get("message", "")
            detail = item.payload.get("detail", "")
            await self._notifier.send_error(msg, detail)
            if self._dispatcher:
                await self._dispatcher.dispatch_error(msg, detail)

        elif t == AlertType.CIRCUIT_BREAKER:
            reason = item.payload.get("reason", "")
            pct    = item.payload.get("daily_loss_pct", 0.0)
            await self._notifier.send_circuit_breaker(reason, pct)
            if self._dispatcher:
                await self._dispatcher.dispatch_circuit_breaker(reason, pct)

        elif t == AlertType.STARTUP:
            await self._notifier.send_startup()
            if self._dispatcher:
                await self._dispatcher.dispatch_status("Engine started", level="info")

        elif t == AlertType.DAILY_SUMMARY:
            total   = item.payload.get("total_signals", 0)
            act     = item.payload.get("actionable", 0)
            top     = item.payload.get("top_signals", [])
            await self._notifier.send_daily_summary(total, act, top)
            if self._dispatcher:
                await self._dispatcher.dispatch_status(
                    f"Daily summary: {total} signals, {act} actionable", level="info"
                )

        else:
            logger.warning("Unknown alert type in queue: %s", t)

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence

    # ── Stats ────────────────────────────────────────────────────────────

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        return self._running

    def stats(self) -> dict:
        return {
            "running":    self._running,
            "queue_size": self.queue_size,
            "dispatched": self._dispatched,
            "dropped":    self._dropped,
        }

    def __repr__(self) -> str:
        return (
            f"<AlertQueue running={self._running} "
            f"size={self.queue_size} dispatched={self._dispatched}>"
        )

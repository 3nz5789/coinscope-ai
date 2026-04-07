"""
CoinScopeAI Market Data — EventBus
====================================
Thread-safe publish/subscribe event bus for real-time market data.

All market data flows through the EventBus:
  Streams → EventBus → [Alpha Generators, Regime Enricher, Recorder, Paper Trading Engine]

Design:
  - Topic-based pub/sub (e.g., "trade.BTCUSDT.binance", "funding.BTCUSDT.*")
  - Wildcard subscriptions supported (*, **)
  - Async-safe: events dispatched in subscriber threads, never block publishers
  - Backpressure: bounded queues per subscriber with configurable overflow policy
  - Metrics: track event counts, latency, dropped events
"""

import fnmatch
import logging
import queue
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("coinscopeai.market_data.event_bus")


class OverflowPolicy(Enum):
    """What to do when a subscriber's queue is full."""
    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    BLOCK = "block"


@dataclass
class Event:
    """Base event that flows through the EventBus."""
    topic: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    source: str = ""

    def __repr__(self):
        return f"Event(topic={self.topic}, source={self.source}, ts={self.timestamp:.3f})"


@dataclass
class Subscription:
    """A subscriber's registration."""
    subscriber_id: str
    pattern: str                # Topic pattern (supports * wildcards)
    callback: Callable[[Event], None]
    queue_size: int = 10_000
    overflow: OverflowPolicy = OverflowPolicy.DROP_OLDEST
    _queue: queue.Queue = field(default=None, repr=False)
    _thread: threading.Thread = field(default=None, repr=False)
    _active: bool = field(default=False, repr=False)

    def __post_init__(self):
        self._queue = queue.Queue(maxsize=self.queue_size)


class EventBusMetrics:
    """Thread-safe metrics for the EventBus."""

    def __init__(self):
        self._lock = threading.Lock()
        self.events_published = 0
        self.events_delivered = 0
        self.events_dropped = 0
        self.events_by_topic: Dict[str, int] = defaultdict(int)
        self._latencies: List[float] = []
        self._max_latency_samples = 1000

    def record_publish(self, topic: str):
        with self._lock:
            self.events_published += 1
            self.events_by_topic[topic] += 1

    def record_delivery(self, latency: float):
        with self._lock:
            self.events_delivered += 1
            self._latencies.append(latency)
            if len(self._latencies) > self._max_latency_samples:
                self._latencies = self._latencies[-self._max_latency_samples:]

    def record_drop(self):
        with self._lock:
            self.events_dropped += 1

    def get_stats(self) -> Dict:
        with self._lock:
            avg_latency = (
                sum(self._latencies) / len(self._latencies)
                if self._latencies else 0.0
            )
            p99_latency = (
                sorted(self._latencies)[int(len(self._latencies) * 0.99)]
                if len(self._latencies) > 10 else 0.0
            )
            return {
                "events_published": self.events_published,
                "events_delivered": self.events_delivered,
                "events_dropped": self.events_dropped,
                "drop_rate": (
                    self.events_dropped / max(self.events_published, 1)
                ),
                "avg_latency_ms": avg_latency * 1000,
                "p99_latency_ms": p99_latency * 1000,
                "topics": dict(self.events_by_topic),
                "subscriber_count": 0,  # filled by EventBus
            }


class EventBus:
    """
    Thread-safe publish/subscribe event bus.

    Usage:
        bus = EventBus()
        bus.start()

        # Subscribe to all BTC trades
        bus.subscribe("alpha_gen", "trade.BTCUSDT.*", my_callback)

        # Publish an event
        bus.publish(Event(topic="trade.BTCUSDT.binance", data={...}))

        bus.stop()
    """

    def __init__(self):
        self._subscriptions: Dict[str, Subscription] = {}
        self._lock = threading.Lock()
        self._running = False
        self.metrics = EventBusMetrics()

    def start(self):
        """Start all subscriber dispatch threads."""
        self._running = True
        with self._lock:
            for sub in self._subscriptions.values():
                self._start_subscriber(sub)
        logger.info("EventBus started with %d subscribers", len(self._subscriptions))

    def stop(self):
        """Stop all subscriber dispatch threads."""
        self._running = False
        with self._lock:
            for sub in self._subscriptions.values():
                sub._active = False
                # Send poison pill
                try:
                    sub._queue.put_nowait(None)
                except queue.Full:
                    pass
            for sub in self._subscriptions.values():
                if sub._thread and sub._thread.is_alive():
                    sub._thread.join(timeout=5)
        logger.info("EventBus stopped")

    def subscribe(
        self,
        subscriber_id: str,
        pattern: str,
        callback: Callable[[Event], None],
        queue_size: int = 10_000,
        overflow: OverflowPolicy = OverflowPolicy.DROP_OLDEST,
    ) -> str:
        """
        Subscribe to events matching a topic pattern.

        Args:
            subscriber_id: Unique identifier for this subscriber
            pattern: Topic pattern (e.g., "trade.BTCUSDT.*", "funding.*.*")
            callback: Function called for each matching event
            queue_size: Max events buffered for this subscriber
            overflow: What to do when queue is full

        Returns:
            The subscriber_id
        """
        sub = Subscription(
            subscriber_id=subscriber_id,
            pattern=pattern,
            callback=callback,
            queue_size=queue_size,
            overflow=overflow,
        )

        with self._lock:
            self._subscriptions[subscriber_id] = sub
            if self._running:
                self._start_subscriber(sub)

        logger.info("Subscribed: %s → %s", subscriber_id, pattern)
        return subscriber_id

    def unsubscribe(self, subscriber_id: str):
        """Remove a subscription."""
        with self._lock:
            sub = self._subscriptions.pop(subscriber_id, None)
            if sub:
                sub._active = False
                try:
                    sub._queue.put_nowait(None)
                except queue.Full:
                    pass
        logger.info("Unsubscribed: %s", subscriber_id)

    def publish(self, event: Event):
        """
        Publish an event to all matching subscribers.
        Non-blocking — events are queued for async delivery.
        """
        self.metrics.record_publish(event.topic)

        with self._lock:
            subscribers = list(self._subscriptions.values())

        for sub in subscribers:
            if not sub._active:
                continue
            if not self._matches(event.topic, sub.pattern):
                continue

            try:
                sub._queue.put_nowait(event)
            except queue.Full:
                if sub.overflow == OverflowPolicy.DROP_OLDEST:
                    try:
                        sub._queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        sub._queue.put_nowait(event)
                    except queue.Full:
                        self.metrics.record_drop()
                elif sub.overflow == OverflowPolicy.DROP_NEWEST:
                    self.metrics.record_drop()
                elif sub.overflow == OverflowPolicy.BLOCK:
                    sub._queue.put(event, timeout=1.0)

    def get_stats(self) -> Dict:
        """Get EventBus statistics."""
        stats = self.metrics.get_stats()
        with self._lock:
            stats["subscriber_count"] = len(self._subscriptions)
            stats["subscribers"] = {
                sid: {
                    "pattern": sub.pattern,
                    "queue_depth": sub._queue.qsize(),
                    "active": sub._active,
                }
                for sid, sub in self._subscriptions.items()
            }
        return stats

    def _start_subscriber(self, sub: Subscription):
        """Start a subscriber's dispatch thread."""
        sub._active = True
        sub._thread = threading.Thread(
            target=self._dispatch_loop,
            args=(sub,),
            daemon=True,
            name=f"eventbus-{sub.subscriber_id}",
        )
        sub._thread.start()

    def _dispatch_loop(self, sub: Subscription):
        """Dispatch events to a subscriber's callback."""
        while sub._active:
            try:
                event = sub._queue.get(timeout=1.0)
                if event is None:  # Poison pill
                    break
                start = time.time()
                sub.callback(event)
                latency = time.time() - start
                self.metrics.record_delivery(latency)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(
                    "Subscriber %s callback error: %s", sub.subscriber_id, e
                )

    @staticmethod
    def _matches(topic: str, pattern: str) -> bool:
        """Check if a topic matches a subscription pattern."""
        # Exact match
        if topic == pattern:
            return True
        # Wildcard match using fnmatch
        return fnmatch.fnmatch(topic, pattern)

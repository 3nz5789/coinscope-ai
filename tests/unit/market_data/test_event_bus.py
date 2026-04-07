"""
Unit tests for the CoinScopeAI EventBus.
Tests: pub/sub, topic matching, wildcard patterns, stats, error handling.
"""

import threading
import time
import pytest

from services.market_data.event_bus import Event, EventBus


class TestEvent:
    """Tests for the Event dataclass."""

    def test_event_creation(self):
        e = Event(topic="trade.BTCUSDT.binance", data={"price": 50000}, source="test")
        assert e.topic == "trade.BTCUSDT.binance"
        assert e.data["price"] == 50000
        assert e.source == "test"
        assert e.timestamp > 0

    def test_event_default_timestamp(self):
        e = Event(topic="test", data={})
        assert isinstance(e.timestamp, float)
        assert e.timestamp > 0


class TestEventBus:
    """Tests for the EventBus pub/sub system."""

    def setup_method(self):
        self.bus = EventBus()

    def teardown_method(self):
        try:
            self.bus.stop()
        except Exception:
            pass

    def _make_event(self, topic, data=None, source="test"):
        return Event(topic=topic, data=data or {}, source=source)

    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish flow."""
        received = []

        def handler(event):
            received.append(event)

        self.bus.subscribe("test_sub", "trade.BTCUSDT.binance", handler)
        self.bus.start()

        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 50000}))
        time.sleep(0.3)

        assert len(received) == 1
        assert received[0].data["price"] == 50000

    def test_wildcard_subscribe(self):
        """Test wildcard pattern matching."""
        received = []

        def handler(event):
            received.append(event)

        self.bus.subscribe("test_wild", "trade.*.*", handler)
        self.bus.start()

        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 50000}))
        self.bus.publish(self._make_event("trade.ETHUSDT.bybit", {"price": 3000}))
        self.bus.publish(self._make_event("orderbook.BTCUSDT.binance", {"bids": []}))
        time.sleep(0.4)

        # Should receive 2 trade events, not the orderbook
        assert len(received) == 2

    def test_multiple_subscribers(self):
        """Test multiple subscribers on the same topic."""
        received_a = []
        received_b = []

        self.bus.subscribe("sub_a", "trade.*.*", lambda e: received_a.append(e))
        self.bus.subscribe("sub_b", "trade.*.*", lambda e: received_b.append(e))
        self.bus.start()

        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 50000}))
        time.sleep(0.3)

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_unsubscribe(self):
        """Test unsubscribing from a topic."""
        received = []

        self.bus.subscribe("test_unsub", "trade.*.*", lambda e: received.append(e))
        self.bus.start()

        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 50000}))
        time.sleep(0.3)
        assert len(received) == 1

        self.bus.unsubscribe("test_unsub")
        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 51000}))
        time.sleep(0.3)
        assert len(received) == 1  # No new events

    def test_stats(self):
        """Test EventBus statistics."""
        self.bus.subscribe("test_stats", "trade.*.*", lambda e: None)
        self.bus.start()

        for i in range(5):
            self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"i": i}))
        time.sleep(0.4)

        stats = self.bus.get_stats()
        assert stats["events_published"] >= 5
        assert stats["subscriber_count"] >= 1

    def test_handler_error_isolation(self):
        """Test that a failing handler doesn't crash the bus."""
        good_received = []

        def bad_handler(event):
            raise ValueError("intentional error")

        def good_handler(event):
            good_received.append(event)

        self.bus.subscribe("bad", "trade.*.*", bad_handler)
        self.bus.subscribe("good", "trade.*.*", good_handler)
        self.bus.start()

        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 50000}))
        time.sleep(0.4)

        # Good handler should still receive the event
        assert len(good_received) == 1

    def test_exact_topic_match(self):
        """Test exact topic matching (no wildcards)."""
        received = []

        self.bus.subscribe("exact", "trade.BTCUSDT.binance", lambda e: received.append(e))
        self.bus.start()

        self.bus.publish(self._make_event("trade.BTCUSDT.binance", {"price": 50000}))
        self.bus.publish(self._make_event("trade.ETHUSDT.binance", {"price": 3000}))
        time.sleep(0.3)

        assert len(received) == 1
        assert received[0].data["price"] == 50000

    def test_start_stop(self):
        """Test starting and stopping the bus."""
        self.bus.start()
        assert self.bus._running is True

        self.bus.stop()
        assert self.bus._running is False

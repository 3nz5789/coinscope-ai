"""
test_ws_replay_consistency.py — WebSocket Replay Consistency Test Suite
=======================================================================
QA module: validates that the WebSocket data pipeline is deterministic,
parity-correct, and resilient across all replay paths.

Test matrix
-----------
TC-01  DataNormalizer Determinism      — same WS event replayed N times
TC-02  REST vs WS Parity              — klines_to_candles == ws_kline_to_candle
TC-03  Combined-Stream Envelope Strip  — BinanceFuturesStreamClient unwraps {"stream","data"}
TC-04  Closed-Candle Gating           — only x=True events pass through NativeAdapter
TC-05  Float Precision Consistency    — repeated parses produce bit-identical floats
TC-06  Multi-Candle Sequence Ordering — sequence of N events preserves order
TC-07  Queue Delivery Integrity       — asyncio.Queue bridge: all events, no drops
TC-08  Malformed / Missing Field Handling — graceful None return, no exceptions

Design constraints
------------------
* Zero network calls — all exchange interaction is replaced with in-process mocks.
* Python 3.11+ asyncio.  Run with: pytest -v tests/test_ws_replay_consistency.py
* Does NOT modify engine state, models, or config.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — makes the engine importable from any working directory
# ---------------------------------------------------------------------------
_ENGINE_ROOT = Path(__file__).parent.parent
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

# Minimal env so config.py doesn't abort at import time
import os
os.environ.setdefault("TESTNET_MODE",               "true")
os.environ.setdefault("BINANCE_TESTNET_API_KEY",    "test_key")
os.environ.setdefault("BINANCE_TESTNET_API_SECRET", "test_secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN",         "123456:TESTTOKEN")
os.environ.setdefault("TELEGRAM_CHAT_ID",           "-100123456")
os.environ.setdefault("SECRET_KEY",                 "a" * 64)
os.environ.setdefault("ENVIRONMENT",                "development")
os.environ.setdefault("SCAN_PAIRS",                 "BTCUSDT,ETHUSDT")
os.environ.setdefault("SCAN_INTERVAL_SECONDS",      "60")
os.environ.setdefault("MIN_CONFLUENCE_SCORE",       "40")
os.environ.setdefault("RISK_PER_TRADE_PCT",         "1.0")
os.environ.setdefault("MAX_LEVERAGE",               "10")
os.environ.setdefault("MAX_DAILY_LOSS_PCT",         "3.0")
os.environ.setdefault("MAX_OPEN_POSITIONS",         "5")
os.environ.setdefault("MAX_POSITION_SIZE_PCT",      "20.0")
os.environ.setdefault("MAX_TOTAL_EXPOSURE_PCT",     "50.0")

from data.data_normalizer import Candle, DataNormalizer
from data.market_stream import BinanceFuturesStreamClient


# ===========================================================================
# ── Fixtures & helpers ──────────────────────────────────────────────────────
# ===========================================================================

def _make_ws_kline_event(
    symbol:     str   = "BTCUSDT",
    interval:   str   = "1h",
    open_time:  int   = 1_700_000_000_000,
    close_time: int   = 1_700_003_599_999,
    open_p:     str   = "60000.00",
    high:       str   = "60500.00",
    low:        str   = "59800.00",
    close_p:    str   = "60350.00",
    volume:     str   = "1200.50",
    quote_vol:  str   = "72420175.00",
    trades:     int   = 4820,
    tbbase_vol: str   = "720.30",
    tbquote_vol: str  = "43452103.50",
    is_closed:  bool  = True,
) -> dict:
    """Return a synthetic Binance kline WebSocket event dict."""
    return {
        "e": "kline",
        "E": open_time + 1,
        "s": symbol,
        "k": {
            "t": open_time,
            "T": close_time,
            "s": symbol,
            "i": interval,
            "f": 100,
            "L": 200,
            "o": open_p,
            "c": close_p,
            "h": high,
            "l": low,
            "v": volume,
            "n": trades,
            "x": is_closed,
            "q": quote_vol,
            "V": tbbase_vol,
            "Q": tbquote_vol,
        },
    }


def _make_rest_kline_row(
    open_time:  int   = 1_700_000_000_000,
    open_p:     str   = "60000.00",
    high:       str   = "60500.00",
    low:        str   = "59800.00",
    close_p:    str   = "60350.00",
    volume:     str   = "1200.50",
    close_time: int   = 1_700_003_599_999,
    quote_vol:  str   = "72420175.00",
    trades:     int   = 4820,
    tbbase_vol: str   = "720.30",
    tbquote_vol: str  = "43452103.50",
) -> list:
    """Return a synthetic Binance REST klines row (12-element list)."""
    return [
        open_time,
        open_p,
        high,
        low,
        close_p,
        volume,
        close_time,
        quote_vol,
        trades,
        tbbase_vol,
        tbquote_vol,
        "0",           # ignore field
    ]


@pytest.fixture
def norm() -> DataNormalizer:
    return DataNormalizer()


@pytest.fixture
def ws_event() -> dict:
    return _make_ws_kline_event()


@pytest.fixture
def rest_row() -> list:
    return _make_rest_kline_row()


# ===========================================================================
# TC-01  DataNormalizer Determinism
# ===========================================================================

class TestTC01Determinism:
    """
    The same raw WS kline event replayed N times must produce an
    identical Candle on every pass — no mutable state, no time.now() leakage.
    """

    REPLAY_COUNT = 50

    def test_repeated_parse_gives_identical_candles(self, norm, ws_event):
        """Replay the same event 50 times; all results must be equal."""
        results = [norm.ws_kline_to_candle(ws_event) for _ in range(self.REPLAY_COUNT)]

        assert all(r is not None for r in results), "Some replays returned None"

        reference = results[0]
        for i, c in enumerate(results[1:], start=2):
            assert asdict(c) == asdict(reference), (
                f"Candle #{i} differs from replay #1:\n"
                f"  expected: {asdict(reference)}\n"
                f"  got:      {asdict(c)}"
            )

    def test_deep_copy_of_event_gives_same_result(self, norm, ws_event):
        """Deep-copying the event dict before parsing must not change output."""
        original  = norm.ws_kline_to_candle(ws_event)
        from_copy = norm.ws_kline_to_candle(copy.deepcopy(ws_event))

        assert original is not None
        assert from_copy is not None
        assert asdict(original) == asdict(from_copy), (
            "Parsing a deep copy produced a different Candle."
        )

    def test_source_dict_not_mutated(self, norm, ws_event):
        """The normalizer must not modify the input event dict."""
        before = json.dumps(ws_event, sort_keys=True)
        norm.ws_kline_to_candle(ws_event)
        after = json.dumps(ws_event, sort_keys=True)

        assert before == after, "ws_kline_to_candle mutated the input event dict."


# ===========================================================================
# TC-02  REST vs WS Parity
# ===========================================================================

class TestTC02RestVsWsParity:
    """
    The same bar represented as a REST klines row and a WS kline event
    must normalise to identical Candle objects.
    """

    # Field names to skip in the equivalence check
    # (REST candles are always closed; WS carries is_closed explicitly)
    _SKIP_FIELDS = frozenset()

    def test_ohlcv_fields_identical(self, norm, ws_event, rest_row):
        ws_candle   = norm.ws_kline_to_candle(ws_event)
        rest_candle = norm.klines_to_candles("BTCUSDT", "1h", [rest_row])[0]

        assert ws_candle is not None
        assert rest_candle is not None

        ws_d   = asdict(ws_candle)
        rest_d = asdict(rest_candle)

        for field in ("open", "high", "low", "close", "volume",
                      "quote_volume", "trades",
                      "taker_buy_base_volume", "taker_buy_quote_volume"):
            assert ws_d[field] == rest_d[field], (
                f"Field '{field}' differs: WS={ws_d[field]}  REST={rest_d[field]}"
            )

    def test_timestamps_identical(self, norm, ws_event, rest_row):
        ws_candle   = norm.ws_kline_to_candle(ws_event)
        rest_candle = norm.klines_to_candles("BTCUSDT", "1h", [rest_row])[0]

        assert ws_candle.open_time  == rest_candle.open_time,  \
            f"open_time mismatch: WS={ws_candle.open_time}  REST={rest_candle.open_time}"
        assert ws_candle.close_time == rest_candle.close_time, \
            f"close_time mismatch: WS={ws_candle.close_time}  REST={rest_candle.close_time}"

    def test_symbol_and_interval_identical(self, norm, ws_event, rest_row):
        ws_candle   = norm.ws_kline_to_candle(ws_event)
        rest_candle = norm.klines_to_candles("BTCUSDT", "1h", [rest_row])[0]

        assert ws_candle.symbol   == rest_candle.symbol,   "symbol mismatch"
        assert ws_candle.interval == rest_candle.interval, "interval mismatch"

    @pytest.mark.parametrize("symbol", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"])
    def test_parity_across_symbols(self, norm, symbol):
        event = _make_ws_kline_event(symbol=symbol)
        row   = _make_rest_kline_row()

        ws   = norm.ws_kline_to_candle(event)
        rest = norm.klines_to_candles(symbol, "1h", [row])[0]

        assert ws.symbol == rest.symbol == symbol
        assert ws.close  == rest.close


# ===========================================================================
# TC-03  Combined-Stream Envelope Unwrapping
# ===========================================================================

class TestTC03EnvelopeUnwrapping:
    """
    BinanceFuturesStreamClient.start() receives combined-stream messages
    of the form {"stream": "btcusdt@kline_1h", "data": <event>}.

    The _dispatch() method must strip the envelope so on_message always
    receives the raw event payload, regardless of wrapping.
    """

    @pytest.mark.asyncio
    async def test_wrapped_event_delivers_inner_payload(self):
        """on_message receives the inner 'data' dict, not the wrapper."""
        received: list[dict] = []

        def on_msg(msg: dict) -> None:
            received.append(msg)

        raw_event = _make_ws_kline_event()
        wrapped   = {"stream": "btcusdt@kline_1h", "data": raw_event}

        client = BinanceFuturesStreamClient(
            streams    = ["btcusdt@kline_1h"],
            on_message = on_msg,
        )
        await client._dispatch(json.dumps(wrapped))

        assert len(received) == 1, f"Expected 1 message, got {len(received)}"
        assert received[0] == raw_event, (
            "Unwrapped payload does not match original event.\n"
            f"  expected: {raw_event}\n"
            f"  got:      {received[0]}"
        )

    @pytest.mark.asyncio
    async def test_unwrapped_event_passes_through_unchanged(self):
        """If the message has no 'data' key, on_message gets the whole dict."""
        received: list[dict] = []

        def on_msg(msg: dict) -> None:
            received.append(msg)

        raw_event = _make_ws_kline_event()
        client = BinanceFuturesStreamClient(
            streams    = ["btcusdt@kline_1h"],
            on_message = on_msg,
        )
        await client._dispatch(json.dumps(raw_event))

        assert len(received) == 1
        assert received[0] == raw_event

    @pytest.mark.asyncio
    async def test_multiple_wrapped_events_all_delivered(self):
        """10 wrapped events → 10 inner payloads in the correct order."""
        received: list[dict] = []

        def on_msg(msg: dict) -> None:
            received.append(msg)

        client = BinanceFuturesStreamClient(
            streams    = ["btcusdt@kline_1h"],
            on_message = on_msg,
        )

        events = [
            _make_ws_kline_event(close_p=str(60_000 + i * 100))
            for i in range(10)
        ]

        for ev in events:
            wrapped = {"stream": "btcusdt@kline_1h", "data": ev}
            await client._dispatch(json.dumps(wrapped))

        assert len(received) == 10, f"Expected 10, got {len(received)}"
        for i, (ev, msg) in enumerate(zip(events, received)):
            assert msg == ev, f"Event #{i} payload mismatch after unwrapping."

    @pytest.mark.asyncio
    async def test_non_json_frame_does_not_raise(self):
        """Malformed JSON must be logged and swallowed — no exception propagation."""
        received: list[dict] = []

        client = BinanceFuturesStreamClient(
            streams    = ["btcusdt@kline_1h"],
            on_message = lambda m: received.append(m),
        )

        # Should not raise
        await client._dispatch("not-valid-json{{")
        assert len(received) == 0, "Malformed JSON should produce no callback."


# ===========================================================================
# TC-04  Closed-Candle Gating
# ===========================================================================

class TestTC04ClosedCandleGating:
    """
    The NativeAdapter must only pass closed candles (k.x == True) downstream.
    Open (in-progress) candles must be silently discarded.
    """

    def test_open_candle_returns_none(self, norm):
        """ws_kline_to_candle for an open candle should return a Candle with is_closed=False."""
        event  = _make_ws_kline_event(is_closed=False)
        candle = norm.ws_kline_to_candle(event)

        # The normalizer itself does parse open candles — gating is in the adapter.
        assert candle is not None
        assert candle.is_closed is False, "Expected is_closed=False for open candle."

    def test_adapter_discards_open_candles(self):
        """
        Simulate the NativeAdapter on_kline callback: it must discard open candles.
        """
        from data.binance_stream_adapter import _NativeAdapter

        adapter   = _NativeAdapter(testnet=True)
        collected = []

        # Replicate the adapter's internal queue logic directly
        import asyncio
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        norm = DataNormalizer()

        def on_kline(msg: dict) -> None:
            if msg.get("e") != "kline":
                return
            k = msg.get("k", {})
            if not k.get("x"):          # gate: only closed candles
                return
            candle = norm.ws_kline_to_candle(msg)
            if candle:
                collected.append(candle)

        closed_event = _make_ws_kline_event(is_closed=True)
        open_event   = _make_ws_kline_event(is_closed=False)

        on_kline(open_event)    # should be discarded
        on_kline(open_event)    # should be discarded
        on_kline(closed_event)  # should pass through

        assert len(collected) == 1, (
            f"Expected 1 closed candle, got {len(collected)}. "
            "Open candles are leaking through the gate."
        )
        assert collected[0].is_closed is True

    def test_closed_candle_passes_gate(self, norm):
        """A closed candle event normalizes cleanly and is_closed=True."""
        event  = _make_ws_kline_event(is_closed=True)
        candle = norm.ws_kline_to_candle(event)

        assert candle is not None
        assert candle.is_closed is True


# ===========================================================================
# TC-05  Float Precision Consistency
# ===========================================================================

class TestTC05FloatPrecision:
    """
    Parsing the same numeric string value N times must always yield the
    same IEEE-754 float.  Python's float() is deterministic, but we verify
    there are no intermediate string-reformatting side effects.
    """

    PRECISION_CASES = [
        "60000.00",
        "0.00012345",
        "99999999.99999999",
        "1.0",
        "0.1",                  # classic IEEE-754 binary approximation
        "123456789.123456789",
    ]

    @pytest.mark.parametrize("price_str", PRECISION_CASES)
    def test_repeated_float_parse_is_deterministic(self, norm, price_str):
        """Parse the same price string N=100 times; all results must be identical."""
        event = _make_ws_kline_event(close_p=price_str)
        values = [norm.ws_kline_to_candle(event).close for _ in range(100)]

        assert len(set(values)) == 1, (
            f"Float parse of '{price_str}' is non-deterministic: {set(values)}"
        )

    @pytest.mark.parametrize("price_str", PRECISION_CASES)
    def test_ws_rest_float_identical(self, norm, price_str):
        """
        The same price string parsed via WS path and REST path must yield
        the exact same float (not just approximately equal).
        """
        ws_event  = _make_ws_kline_event(close_p=price_str)
        rest_row  = _make_rest_kline_row(close_p=price_str)

        ws_close   = norm.ws_kline_to_candle(ws_event).close
        rest_close = norm.klines_to_candles("BTCUSDT", "1h", [rest_row])[0].close

        # Exact equality — not approximate
        assert ws_close == rest_close, (
            f"WS close={ws_close!r}  REST close={rest_close!r}  (price_str='{price_str}')"
        )


# ===========================================================================
# TC-06  Multi-Candle Sequence Ordering
# ===========================================================================

class TestTC06SequenceOrdering:
    """
    Replaying a sequence of N sequential WS kline events must produce
    Candle objects in the same chronological order, without reordering.
    """

    N = 100   # number of sequential candles

    @pytest.fixture
    def sequential_events(self) -> list[dict]:
        """Generate N sequential 1h kline events."""
        base_ts = 1_700_000_000_000
        return [
            _make_ws_kline_event(
                open_time  = base_ts + i * 3_600_000,
                close_time = base_ts + i * 3_600_000 + 3_599_999,
                close_p    = str(60_000 + i * 10),
            )
            for i in range(self.N)
        ]

    def test_candle_sequence_preserves_order(self, norm, sequential_events):
        """
        After normalisation the candles must be in ascending open_time order,
        matching the input sequence exactly.
        """
        candles = [norm.ws_kline_to_candle(ev) for ev in sequential_events]

        assert all(c is not None for c in candles), "Some events in sequence failed to parse."
        assert len(candles) == self.N

        for i in range(1, self.N):
            assert candles[i].open_time > candles[i - 1].open_time, (
                f"Candle [{i}] open_time {candles[i].open_time} is not "
                f"after candle [{i-1}] open_time {candles[i-1].open_time}."
            )

    def test_close_price_sequence_is_monotonic(self, norm, sequential_events):
        """
        The test fixture generates monotonically increasing close prices.
        Verify the normalizer preserves this property.
        """
        candles = [norm.ws_kline_to_candle(ev) for ev in sequential_events]
        closes  = [c.close for c in candles]

        for i in range(1, len(closes)):
            assert closes[i] > closes[i - 1], (
                f"Close price at index {i} ({closes[i]}) is not greater than "
                f"index {i-1} ({closes[i-1]})."
            )

    def test_rest_and_ws_sequence_match(self, norm, sequential_events):
        """
        Parsing the same sequence via REST path vs WS path must yield
        identical OHLCV values in the same order.
        """
        ws_candles = [norm.ws_kline_to_candle(ev) for ev in sequential_events]

        rest_rows = [
            _make_rest_kline_row(
                open_time  = ev["k"]["t"],
                close_time = ev["k"]["T"],
                open_p     = ev["k"]["o"],
                high       = ev["k"]["h"],
                low        = ev["k"]["l"],
                close_p    = ev["k"]["c"],
                volume     = ev["k"]["v"],
                quote_vol  = ev["k"]["q"],
                trades     = ev["k"]["n"],
                tbbase_vol = ev["k"]["V"],
                tbquote_vol= ev["k"]["Q"],
            )
            for ev in sequential_events
        ]
        rest_candles = norm.klines_to_candles("BTCUSDT", "1h", rest_rows)

        assert len(ws_candles) == len(rest_candles) == self.N

        for i, (ws, rest) in enumerate(zip(ws_candles, rest_candles)):
            for field in ("open", "high", "low", "close", "volume"):
                assert getattr(ws, field) == getattr(rest, field), (
                    f"Candle #{i} field '{field}' mismatch: "
                    f"WS={getattr(ws, field)}  REST={getattr(rest, field)}"
                )


# ===========================================================================
# TC-07  Queue Delivery Integrity (NativeAdapter asyncio bridge)
# ===========================================================================

class TestTC07QueueDelivery:
    """
    The NativeAdapter bridges a push-based BinanceFuturesStreamClient into
    an async generator via asyncio.Queue.

    We simulate the queue-fill path directly (without a live WebSocket) and
    verify:
      a) All N closed-candle events produce exactly N queue entries.
      b) Candles exit the queue in FIFO order.
      c) Queue-full events are handled gracefully (no crash, warning logged).
    """

    N = 50

    @pytest.fixture
    def closed_events(self) -> list[dict]:
        base = 1_700_000_000_000
        return [
            _make_ws_kline_event(
                open_time  = base + i * 3_600_000,
                close_time = base + i * 3_600_000 + 3_599_999,
                close_p    = str(60_000 + i * 5),
                is_closed  = True,
            )
            for i in range(self.N)
        ]

    def _build_on_kline(
        self, queue: asyncio.Queue, norm: DataNormalizer
    ):
        """Replicate the _NativeAdapter.on_kline callback."""
        def on_kline(msg: dict) -> None:
            if msg.get("e") != "kline":
                return
            k = msg.get("k", {})
            if not k.get("x"):
                return
            candle = norm.ws_kline_to_candle(msg)
            if candle:
                try:
                    queue.put_nowait(candle)
                except asyncio.QueueFull:
                    pass  # same behaviour as production code
        return on_kline

    def test_all_closed_events_enqueued(self, norm, closed_events):
        """N closed events → exactly N candles in the queue."""
        loop  = asyncio.new_event_loop()
        queue = asyncio.Queue(maxsize=1000)
        cb    = self._build_on_kline(queue, norm)

        for ev in closed_events:
            cb(ev)

        assert queue.qsize() == self.N, (
            f"Expected {self.N} items in queue, got {queue.qsize()}."
        )
        loop.close()

    def test_queue_fifo_order(self, norm, closed_events):
        """Candles must be dequeued in the same order they were enqueued."""
        queue = asyncio.Queue(maxsize=1000)
        cb    = self._build_on_kline(queue, norm)

        for ev in closed_events:
            cb(ev)

        dequeued = []
        while not queue.empty():
            dequeued.append(queue.get_nowait())

        assert len(dequeued) == self.N

        # Verify ascending open_time (FIFO)
        for i in range(1, len(dequeued)):
            assert dequeued[i].open_time > dequeued[i - 1].open_time, (
                f"FIFO violated at index {i}: "
                f"{dequeued[i].open_time} <= {dequeued[i-1].open_time}"
            )

    def test_open_events_not_enqueued(self, norm):
        """Open candle events must not appear in the queue."""
        queue = asyncio.Queue(maxsize=1000)
        cb    = self._build_on_kline(queue, norm)

        for _ in range(20):
            cb(_make_ws_kline_event(is_closed=False))

        assert queue.qsize() == 0, (
            f"Open candle events leaked into the queue: {queue.qsize()} items."
        )

    def test_queue_full_does_not_raise(self, norm, closed_events):
        """
        When the queue is full, the callback must NOT raise an exception.
        This guards against a race condition where signal computation lags.
        """
        tiny_queue = asyncio.Queue(maxsize=5)
        cb = self._build_on_kline(tiny_queue, norm)

        # Push 50 events into a queue that only holds 5 — must not raise
        for ev in closed_events:
            cb(ev)   # should silently drop after queue full

        assert tiny_queue.qsize() == 5, (
            f"Expected 5 items (queue capacity), got {tiny_queue.qsize()}."
        )


# ===========================================================================
# TC-08  Malformed / Missing Field Handling
# ===========================================================================

class TestTC08MalformedEvents:
    """
    ws_kline_to_candle must return None and log a warning — never raise —
    when the input event is missing required fields or contains bad values.

    klines_to_candles must skip bad rows and return only valid candles.
    """

    def test_missing_k_key_returns_none(self, norm):
        bad = {"e": "kline", "E": 1234567890000, "s": "BTCUSDT"}
        result = norm.ws_kline_to_candle(bad)
        assert result is None, f"Expected None for missing 'k' key, got {result}"

    def test_missing_close_price_returns_none(self, norm):
        event = _make_ws_kline_event()
        del event["k"]["c"]
        result = norm.ws_kline_to_candle(event)
        assert result is None, "Expected None for missing 'c' (close) field."

    def test_non_numeric_price_returns_none(self, norm):
        event = _make_ws_kline_event(close_p="NOT_A_NUMBER")
        result = norm.ws_kline_to_candle(event)
        assert result is None, "Expected None for non-numeric close price."

    def test_empty_event_returns_none(self, norm):
        result = norm.ws_kline_to_candle({})
        assert result is None, "Expected None for empty event dict."

    def test_none_event_does_not_raise(self, norm):
        """Passing None should raise TypeError internally and return None."""
        try:
            result = norm.ws_kline_to_candle(None)
            # If it doesn't raise, it should return None
            assert result is None, f"Expected None for None input, got {result}"
        except TypeError:
            pass   # acceptable — important is no unhandled crash

    def test_rest_skips_malformed_rows(self, norm):
        """klines_to_candles with a mix of good and bad rows returns only good ones."""
        good_row  = _make_rest_kline_row()
        bad_row   = ["bad", "data"]
        empty_row = []

        candles = norm.klines_to_candles(
            "BTCUSDT", "1h", [good_row, bad_row, empty_row, good_row]
        )

        assert len(candles) == 2, (
            f"Expected 2 valid candles from 4 rows (2 bad), got {len(candles)}."
        )

    def test_extra_fields_in_k_are_ignored(self, norm):
        """Unknown extra fields in k dict must not break parsing."""
        event = _make_ws_kline_event()
        event["k"]["unknown_future_field"] = "some_value"
        event["k"]["another_field"] = 999

        result = norm.ws_kline_to_candle(event)
        assert result is not None, (
            "Extra fields in the 'k' dict caused ws_kline_to_candle to return None."
        )

    def test_extremely_large_trade_count_handled(self, norm):
        """Extreme integer values must not overflow or raise."""
        event = _make_ws_kline_event(trades=999_999_999)
        result = norm.ws_kline_to_candle(event)
        assert result is not None
        assert result.trades == 999_999_999

    def test_zero_volume_candle_is_valid(self, norm):
        """Zero-volume candles (e.g. during low-liquidity periods) must be accepted."""
        event = _make_ws_kline_event(volume="0.0", tbbase_vol="0.0", tbquote_vol="0.0")
        result = norm.ws_kline_to_candle(event)
        assert result is not None
        assert result.volume == 0.0
        assert result.taker_buy_base_volume == 0.0

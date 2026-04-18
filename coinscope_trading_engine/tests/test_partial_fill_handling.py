# tests/test_partial_fill_handling.py
"""
[QA] EXECUTION — Partial Fill Handling
=======================================
Validates correct behaviour of the OrderManager and OrderRecord across all
partial-fill lifecycle scenarios:

  SCENARIOS COVERED
  -----------------
  PF-01  OrderRecord recognises PARTIALLY_FILLED as open, non-terminal
  PF-02  update_from_exchange transitions PENDING → PARTIALLY_FILLED
  PF-03  filled_qty and avg_fill_price update on partial fill exchange response
  PF-04  Multiple sequential partial fill updates accumulate correctly
  PF-05  cumulative_quote (notional) tracked correctly on each update
  PF-06  Order history records every PARTIAL_FILL transition with timestamp
  PF-07  poll_until_terminal: PARTIAL_FILL → FILLED completes correctly
  PF-08  poll_until_terminal: PARTIAL_FILL → stale → CANCELLED
  PF-09  poll_until_terminal: on_fill callback fires ONLY on final FILLED, not partial
  PF-10  cancel_and_replace accepted on PARTIAL_FILL order
  PF-11  cancel_order accepted on PARTIAL_FILL order
  PF-12  summary() does NOT count PARTIAL_FILL as "filled"
  PF-13  place_order returns PARTIALLY_FILLED immediately (rare exchange edge case)
  PF-14  PARTIAL_FILL order: is_open=True, is_terminal=False
  PF-15  Retry loop does NOT re-submit a PARTIALLY_FILLED order
"""

from __future__ import annotations

import asyncio
import sys
import os
import types

# ---------------------------------------------------------------------------
# Stub heavy optional dependencies before the engine modules are imported.
# This allows the execution/order_manager unit tests to run in CI without
# requiring the full ML/data-science stack (numpy, pandas, redis, ccxt, etc.)
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "pandas",
    "ccxt", "ccxt.async_support",
    "sklearn", "sklearn.ensemble", "sklearn.preprocessing",
    "ta", "ta.momentum", "ta.trend", "ta.volatility", "ta.volume",
    "scipy", "scipy.stats",
]
for _mod in _STUB_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution.order_manager import (
    OrderManager,
    OrderRecord,
    OrderState,
    PollConfig,
    RetryConfig,
    TERMINAL_STATES,
)
from data.binance_rest import BinanceRESTError


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

def fast_retry() -> RetryConfig:
    return RetryConfig(max_attempts=3, base_delay_s=0.001, max_delay_s=0.01, jitter_s=0.0, timeout_s=5.0)


def fast_poll(stale_after_s: float = 60.0) -> PollConfig:
    return PollConfig(interval_s=0.001, max_wait_s=5.0, stale_after_s=stale_after_s)


def make_rest(
    place_return=None,
    place_side_effect=None,
    get_side_effect=None,
    get_return=None,
    cancel_return=None,
    is_throttled: bool = False,
) -> MagicMock:
    rest = MagicMock()
    type(rest).is_throttled = PropertyMock(return_value=is_throttled)

    default_place = {"orderId": 1, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}
    if place_side_effect:
        rest.place_order = AsyncMock(side_effect=place_side_effect)
    else:
        rest.place_order = AsyncMock(return_value=place_return or default_place)

    if get_side_effect:
        rest.get_order = AsyncMock(side_effect=get_side_effect)
    else:
        rest.get_order = AsyncMock(return_value=get_return or {
            "orderId": 1, "status": "FILLED",
            "executedQty": "0.001", "avgPrice": "68500", "cumQuote": "68.5",
        })

    rest.cancel_order = AsyncMock(return_value=cancel_return or {"orderId": 1, "status": "CANCELED"})
    return rest


def make_record(state: OrderState = OrderState.PENDING, **kwargs) -> OrderRecord:
    defaults = dict(
        symbol="BTCUSDT", side="BUY", order_type="LIMIT",
        quantity="0.002", price="68500", stop_price=None,
        time_in_force="GTC", position_side="BOTH",
        reduce_only=False, client_order_id="CSCOPE_TEST_PF", stp_mode=None,
    )
    defaults.update(kwargs)
    rec = OrderRecord(**defaults)
    if state != OrderState.PENDING:
        rec.state = state
    return rec


# Exchange response helpers
def partial_fill_response(filled_qty: str, avg_price: str, cum_quote: str, order_id: int = 1) -> dict:
    return {
        "orderId": order_id,
        "status": "PARTIALLY_FILLED",
        "executedQty": filled_qty,
        "avgPrice": avg_price,
        "cumQuote": cum_quote,
    }


def filled_response(filled_qty: str = "0.002", avg_price: str = "68500", cum_quote: str = "137.00", order_id: int = 1) -> dict:
    return {
        "orderId": order_id,
        "status": "FILLED",
        "executedQty": filled_qty,
        "avgPrice": avg_price,
        "cumQuote": cum_quote,
    }


def open_response(order_id: int = 1) -> dict:
    return {"orderId": order_id, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}


# ---------------------------------------------------------------------------
# PF-01  OrderRecord: PARTIAL_FILL is open, non-terminal
# ---------------------------------------------------------------------------

class TestPF01_StateProperties:

    def test_partial_fill_is_not_terminal(self):
        rec = make_record()
        rec.transition(OrderState.PARTIAL_FILL, note="pf-01")
        assert rec.is_terminal is False

    def test_partial_fill_is_open(self):
        rec = make_record()
        rec.transition(OrderState.PARTIAL_FILL, note="pf-01")
        assert rec.is_open is True

    def test_partial_fill_not_in_terminal_states_set(self):
        assert OrderState.PARTIAL_FILL not in TERMINAL_STATES

    def test_filled_is_terminal_and_not_open(self):
        """Contrast check: FILLED is terminal, not open."""
        rec = make_record()
        rec.transition(OrderState.FILLED)
        assert rec.is_terminal is True
        assert rec.is_open is False


# ---------------------------------------------------------------------------
# PF-02  update_from_exchange transitions to PARTIAL_FILL
# ---------------------------------------------------------------------------

class TestPF02_UpdateFromExchangeTransition:

    def test_pending_to_partial_fill(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        assert rec.state == OrderState.PARTIAL_FILL

    def test_open_to_partial_fill(self):
        rec = make_record()
        rec.transition(OrderState.OPEN)
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        assert rec.state == OrderState.PARTIAL_FILL

    def test_transition_is_recorded_in_history(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        states_in_history = [h[1] for h in rec.history]
        assert "PARTIALLY_FILLED" in states_in_history


# ---------------------------------------------------------------------------
# PF-03  filled_qty and avg_fill_price on partial fill
# ---------------------------------------------------------------------------

class TestPF03_FillMetrics:

    def test_filled_qty_updates(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        assert rec.filled_qty == pytest.approx(0.001, rel=1e-6)

    def test_avg_fill_price_updates(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        assert rec.avg_fill_price == pytest.approx(68490.00, rel=1e-6)

    def test_zero_fill_on_open_response(self):
        rec = make_record()
        rec.update_from_exchange(open_response())
        assert rec.filled_qty == 0.0
        assert rec.avg_fill_price == 0.0


# ---------------------------------------------------------------------------
# PF-04  Multiple sequential partial fill updates
# ---------------------------------------------------------------------------

class TestPF04_SequentialPartialFills:

    def test_qty_increases_with_each_fill(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        assert rec.filled_qty == pytest.approx(0.001)

        rec.update_from_exchange(partial_fill_response("0.0015", "68492.00", "102.74"))
        assert rec.filled_qty == pytest.approx(0.0015)

        rec.update_from_exchange(filled_response("0.002", "68495.00", "136.99"))
        assert rec.filled_qty == pytest.approx(0.002)
        assert rec.state == OrderState.FILLED

    def test_state_stays_partial_fill_between_updates(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.0005", "68480", "34.24"))
        assert rec.state == OrderState.PARTIAL_FILL
        rec.update_from_exchange(partial_fill_response("0.001", "68485", "68.49"))
        assert rec.state == OrderState.PARTIAL_FILL

    def test_avg_price_reflects_last_exchange_report(self):
        """avg_fill_price should track the exchange-reported VWAP, not our calculation."""
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        rec.update_from_exchange(partial_fill_response("0.0015", "68492.00", "102.74"))
        assert rec.avg_fill_price == pytest.approx(68492.00, rel=1e-5)


# ---------------------------------------------------------------------------
# PF-05  cumulative_quote (notional) tracked correctly
# ---------------------------------------------------------------------------

class TestPF05_CumulativeQuote:

    def test_cumulative_quote_updates_on_partial_fill(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        assert rec.cumulative_quote == pytest.approx(68.49, rel=1e-4)

    def test_cumulative_quote_updates_on_final_fill(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490.00", "68.49"))
        rec.update_from_exchange(filled_response("0.002", "68495.00", "136.99"))
        assert rec.cumulative_quote == pytest.approx(136.99, rel=1e-4)


# ---------------------------------------------------------------------------
# PF-06  History records every transition with timestamp
# ---------------------------------------------------------------------------

class TestPF06_AuditHistory:

    def test_history_entry_has_three_fields(self):
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490", "68.49"))
        assert len(rec.history) >= 1
        entry = rec.history[-1]
        assert len(entry) == 3    # (timestamp, state, note)

    def test_history_captures_full_lifecycle(self):
        rec = make_record()
        rec.transition(OrderState.SUBMITTED, note="attempt=1")
        rec.update_from_exchange(open_response())
        rec.update_from_exchange(partial_fill_response("0.001", "68490", "68.49"))
        rec.update_from_exchange(filled_response("0.002", "68495", "136.99"))

        state_sequence = [h[1] for h in rec.history]
        assert "SUBMITTED" in state_sequence
        assert "NEW" in state_sequence
        assert "PARTIALLY_FILLED" in state_sequence
        assert "FILLED" in state_sequence

    def test_no_duplicate_entry_if_state_unchanged(self):
        """Calling update_from_exchange with same status must not add duplicate history entry."""
        rec = make_record()
        rec.update_from_exchange(partial_fill_response("0.001", "68490", "68.49"))
        count_after_first = len(rec.history)
        rec.update_from_exchange(partial_fill_response("0.001", "68490", "68.49"))   # same status
        # The state is already PARTIALLY_FILLED — update_from_exchange only transitions when status CHANGES
        assert len(rec.history) == count_after_first


# ---------------------------------------------------------------------------
# PF-07  poll_until_terminal: PARTIAL_FILL → FILLED
# ---------------------------------------------------------------------------

class TestPF07_PollPartialToFilled:

    @pytest.mark.asyncio
    async def test_polls_through_partial_to_filled(self):
        place_resp = open_response()
        poll_responses = [
            open_response(),
            partial_fill_response("0.001", "68490", "68.49"),
            partial_fill_response("0.0015", "68492", "102.74"),
            filled_response("0.002", "68495", "136.99"),
        ]

        rest = make_rest(place_return=place_resp, get_side_effect=poll_responses)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")
        assert rec.state == OrderState.OPEN

        final = await mgr.poll_until_terminal(rec, poll_cfg=fast_poll())
        assert final.state == OrderState.FILLED
        assert final.filled_qty == pytest.approx(0.002)
        assert rest.get_order.call_count == 4

    @pytest.mark.asyncio
    async def test_final_fill_metrics_are_correct_after_poll(self):
        place_resp = open_response()
        poll_responses = [
            partial_fill_response("0.001", "68490", "68.49"),
            filled_response("0.002", "68495.50", "136.99"),
        ]

        rest = make_rest(place_return=place_resp, get_side_effect=poll_responses)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")
        final = await mgr.poll_until_terminal(rec, poll_cfg=fast_poll())

        assert final.avg_fill_price == pytest.approx(68495.50, rel=1e-4)
        assert final.cumulative_quote == pytest.approx(136.99, rel=1e-4)


# ---------------------------------------------------------------------------
# PF-08  poll_until_terminal: PARTIAL_FILL → stale → CANCELLED
# ---------------------------------------------------------------------------

class TestPF08_StalePartialFill:

    @pytest.mark.asyncio
    async def test_stale_partial_fill_is_cancelled(self):
        place_resp = open_response()
        # Never fully fills — stays partial forever
        partial = partial_fill_response("0.001", "68490", "68.49")

        rest = make_rest(place_return=place_resp, get_side_effect=[partial] * 20)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")
        rec.transition(OrderState.PARTIAL_FILL)   # force to PARTIAL_FILL for poll

        # stale_after_s=0 → considered stale immediately
        final = await mgr.poll_until_terminal(rec, poll_cfg=fast_poll(stale_after_s=0.0))
        assert final.state == OrderState.CANCELLED
        rest.cancel_order.assert_called()

    @pytest.mark.asyncio
    async def test_partial_fill_qty_preserved_after_cancel(self):
        """Filled quantity must survive even after the order is cancelled."""
        rec = make_record(state=OrderState.PARTIAL_FILL)
        rec.filled_qty = 0.001
        rec.avg_fill_price = 68490.00
        rec.cumulative_quote = 68.49

        rest = make_rest()
        rest.cancel_order = AsyncMock(return_value={"orderId": 1, "status": "CANCELED"})
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        await mgr._cancel_order(rec)

        assert rec.state == OrderState.CANCELLED
        # Partial fill metrics must be intact
        assert rec.filled_qty == pytest.approx(0.001)
        assert rec.avg_fill_price == pytest.approx(68490.00)
        assert rec.cumulative_quote == pytest.approx(68.49)


# ---------------------------------------------------------------------------
# PF-09  on_fill callback fires ONLY on FILLED, not on PARTIAL_FILL
# ---------------------------------------------------------------------------

class TestPF09_OnFillCallback:

    @pytest.mark.asyncio
    async def test_on_fill_not_fired_on_partial_fill(self):
        place_resp = open_response()
        poll_responses = [
            partial_fill_response("0.001", "68490", "68.49"),
            partial_fill_response("0.0015", "68492", "102.74"),
            filled_response("0.002", "68495", "136.99"),
        ]

        fill_events = []

        async def on_fill(rec):
            fill_events.append(rec.state)

        rest = make_rest(place_return=place_resp, get_side_effect=poll_responses)
        mgr = OrderManager(rest, retry_cfg=fast_retry(), on_fill=on_fill)

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")
        await mgr.poll_until_terminal(rec, poll_cfg=fast_poll())

        # on_fill must be called exactly once — on final FILLED
        assert len(fill_events) == 1
        assert fill_events[0] == OrderState.FILLED

    @pytest.mark.asyncio
    async def test_on_fill_fires_when_place_order_returns_partial(self):
        """
        Edge case: place_order itself returns PARTIALLY_FILLED.
        on_fill should NOT fire here — only on final FILLED.
        """
        partial_place = {
            "orderId": 5,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.001",
            "avgPrice": "68490",
            "cumQuote": "68.49",
        }

        fill_events = []

        async def on_fill(rec):
            fill_events.append(rec.state)

        rest = make_rest(place_return=partial_place)
        mgr = OrderManager(rest, retry_cfg=fast_retry(), on_fill=on_fill)
        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")

        # After submit alone (no poll), on_fill must NOT have fired
        assert len(fill_events) == 0
        assert rec.state == OrderState.PARTIAL_FILL


# ---------------------------------------------------------------------------
# PF-10  cancel_and_replace on PARTIAL_FILL order
# ---------------------------------------------------------------------------

class TestPF10_CancelAndReplacePartialFill:

    @pytest.mark.asyncio
    async def test_cancel_and_replace_accepted_on_partial_fill(self):
        open_resp = open_response()
        new_order_resp = {"orderId": 200, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}

        rest = make_rest(
            place_side_effect=[open_resp, new_order_resp],
            cancel_return={"orderId": 1, "status": "CANCELED"},
        )
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")
        # Simulate partial fill received
        rec.transition(OrderState.PARTIAL_FILL, note="pf-10 test")
        rec.filled_qty = 0.001

        new_rec = await mgr.cancel_and_replace(rec, new_price="68200.00")

        assert new_rec.price == "68200.00"
        assert new_rec.exchange_order_id == 200
        assert new_rec.client_order_id != rec.client_order_id
        rest.cancel_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_and_replace_preserves_symbol_and_side(self):
        open_resp = open_response()
        new_order_resp = {"orderId": 201, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}

        rest = make_rest(place_side_effect=[open_resp, new_order_resp])
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("ETHUSDT", "SELL", "LIMIT", "1.5", price="3200")
        rec.transition(OrderState.PARTIAL_FILL)

        new_rec = await mgr.cancel_and_replace(rec, new_price="3190.00")

        assert new_rec.symbol == "ETHUSDT"
        assert new_rec.side == "SELL"
        assert new_rec.quantity == "1.5"


# ---------------------------------------------------------------------------
# PF-11  cancel_order accepted on PARTIAL_FILL
# ---------------------------------------------------------------------------

class TestPF11_CancelPartialFill:

    @pytest.mark.asyncio
    async def test_cancel_accepted_on_partial_fill_state(self):
        rest = make_rest()
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = make_record(state=OrderState.PARTIAL_FILL)
        rec.exchange_order_id = 42

        await mgr._cancel_order(rec)

        assert rec.state == OrderState.CANCELLED
        rest.cancel_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_on_filled_is_noop(self):
        """Cancelling a FILLED order must be a no-op (already terminal)."""
        rest = make_rest()
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = make_record(state=OrderState.FILLED)
        rec.exchange_order_id = 43

        await mgr._cancel_order(rec)

        # cancel_order should NOT be called — already terminal
        rest.cancel_order.assert_not_called()
        assert rec.state == OrderState.FILLED


# ---------------------------------------------------------------------------
# PF-12  summary() does NOT count PARTIAL_FILL as "filled"
# ---------------------------------------------------------------------------

class TestPF12_SummaryStats:

    @pytest.mark.asyncio
    async def test_partial_fill_not_counted_as_filled_in_summary(self):
        open_resp = open_response()
        rest = make_rest(place_return=open_resp)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.001", price="68500")
        # Force to PARTIAL_FILL
        rec.state = OrderState.PARTIAL_FILL
        rec.filled_qty = 0.0005

        s = mgr.summary()
        assert s["filled"] == 0          # not counted as fully filled
        assert s["open"] == 1            # still open
        assert s["total_submitted"] == 1

    @pytest.mark.asyncio
    async def test_summary_counts_correctly_after_full_fill(self):
        filled_resp = {
            "orderId": 10, "status": "FILLED",
            "executedQty": "0.001", "avgPrice": "68500", "cumQuote": "68.5",
        }
        rest = make_rest(place_return=filled_resp)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        await mgr.submit_order("BTCUSDT", "BUY", "MARKET", "0.001")

        s = mgr.summary()
        assert s["filled"] == 1
        assert s["open"] == 0
        assert s["fill_rate"] == 1.0


# ---------------------------------------------------------------------------
# PF-13  place_order returns PARTIALLY_FILLED immediately (exchange edge case)
# ---------------------------------------------------------------------------

class TestPF13_ImmediatePartialFill:

    @pytest.mark.asyncio
    async def test_immediate_partial_fill_from_exchange(self):
        """
        Some exchanges return PARTIALLY_FILLED on the order ACK itself.
        OrderManager must handle this gracefully — record is in PARTIAL_FILL,
        not ERROR, and metrics are populated.
        """
        partial_ack = {
            "orderId": 77,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.001",
            "avgPrice": "68490.00",
            "cumQuote": "68.49",
        }
        rest = make_rest(place_return=partial_ack)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")

        assert rec.state == OrderState.PARTIAL_FILL
        assert rec.exchange_order_id == 77
        assert rec.filled_qty == pytest.approx(0.001)
        assert rec.avg_fill_price == pytest.approx(68490.00)
        assert rec.is_open is True
        assert rec.is_terminal is False

    @pytest.mark.asyncio
    async def test_immediate_partial_fill_does_not_trigger_retry(self):
        """
        PARTIAL_FILL on submit ACK must NOT be treated as an error and retried.
        """
        partial_ack = {
            "orderId": 78,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.001",
            "avgPrice": "68490.00",
            "cumQuote": "68.49",
        }
        rest = make_rest(place_return=partial_ack)
        mgr = OrderManager(rest, retry_cfg=fast_retry())

        await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")
        # place_order should be called exactly once — no retry on partial fill
        assert rest.place_order.call_count == 1


# ---------------------------------------------------------------------------
# PF-14  is_open / is_terminal flags through full lifecycle
# ---------------------------------------------------------------------------

class TestPF14_LifecycleFlags:

    @pytest.mark.parametrize("state, expected_open, expected_terminal", [
        (OrderState.PENDING,       False, False),
        (OrderState.SUBMITTED,     False, False),
        (OrderState.OPEN,          True,  False),
        (OrderState.PARTIAL_FILL,  True,  False),   # KEY assertion
        (OrderState.FILLED,        False, True),
        (OrderState.CANCELLED,     False, True),
        (OrderState.REJECTED,      False, True),
        (OrderState.EXPIRED,       False, True),
        (OrderState.ERROR,         False, True),
    ])
    def test_flags_per_state(self, state, expected_open, expected_terminal):
        rec = make_record()
        rec.state = state
        assert rec.is_open is expected_open, f"is_open wrong for {state}"
        assert rec.is_terminal is expected_terminal, f"is_terminal wrong for {state}"


# ---------------------------------------------------------------------------
# PF-15  Retry loop does NOT re-submit a PARTIALLY_FILLED order
# ---------------------------------------------------------------------------

class TestPF15_NoRetryOnPartialFill:

    @pytest.mark.asyncio
    async def test_place_order_called_once_when_partial_ack(self):
        """
        Receiving PARTIALLY_FILLED on the first submit attempt is a success,
        NOT an error.  The retry loop must stop after the first call.
        """
        partial_ack = {
            "orderId": 99,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.001",
            "avgPrice": "68490.00",
            "cumQuote": "68.49",
        }
        rest = make_rest(place_return=partial_ack)
        mgr = OrderManager(rest, retry_cfg=RetryConfig(max_attempts=4, base_delay_s=0.001, jitter_s=0.0))

        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.002", price="68500")

        assert rest.place_order.call_count == 1
        assert rec.attempt == 1
        assert rec.state == OrderState.PARTIAL_FILL

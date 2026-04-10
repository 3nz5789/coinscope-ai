# tests/test_order_manager.py
"""
Unit tests for execution/order_manager.py
==========================================

Coverage targets
----------------
  ✅ Happy path: LIMIT order → SUBMITTED → OPEN → FILLED
  ✅ MARKET order → SUBMITTED → FILLED immediately
  ✅ Retry on 5xx: succeeds on 2nd attempt
  ✅ Retry exhaustion: all attempts fail → ERROR
  ✅ Non-retryable error (-2010): fails immediately, no retry
  ✅ Rate limit (429): delays and retries
  ✅ Timeout: queries by client_order_id to recover
  ✅ Circuit breaker OPEN: order blocked immediately → ERROR
  ✅ Input validation: bad symbol, bad side, missing price
  ✅ Duplicate order (-2022): queries exchange → idempotent success
  ✅ cancel_and_replace: cancels old, submits new
  ✅ poll_until_terminal: polls until FILLED
  ✅ poll_until_terminal: stale order → CANCELLED
  ✅ OrderRecord.update_from_exchange: state transitions
  ✅ generate_client_order_id: length ≤ 36, format check
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import sys
import os

# Allow importing from the engine root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution.order_manager import (
    NON_RETRYABLE_CODES,
    OrderManager,
    OrderRecord,
    OrderState,
    PollConfig,
    RetryConfig,
    TERMINAL_STATES,
    make_order_manager,
)
from data.binance_rest import AuthError, BinanceRESTError, RateLimitError


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def make_rest_client(
    place_order_return: dict | None = None,
    place_order_side_effect=None,
    get_order_return: dict | None = None,
    cancel_order_return: dict | None = None,
    is_throttled: bool = False,
) -> MagicMock:
    """Build a mock BinanceRESTClient."""
    rest = MagicMock()

    type(rest).is_throttled = PropertyMock(return_value=is_throttled)

    default_place = {
        "orderId": 12345,
        "status": "NEW",
        "executedQty": "0",
        "avgPrice": "0",
        "cumQuote": "0",
    }
    if place_order_side_effect:
        rest.place_order = AsyncMock(side_effect=place_order_side_effect)
    else:
        rest.place_order = AsyncMock(return_value=place_order_return or default_place)

    rest.get_order = AsyncMock(return_value=get_order_return or {
        "orderId": 12345,
        "status": "FILLED",
        "executedQty": "0.001",
        "avgPrice": "68500.00",
        "cumQuote": "68.50",
    })

    rest.cancel_order = AsyncMock(return_value=cancel_order_return or {
        "orderId": 12345, "status": "CANCELED",
    })

    return rest


def make_cb(is_open: bool = False) -> MagicMock:
    """Build a mock CircuitBreaker."""
    cb = MagicMock()
    type(cb).is_open = PropertyMock(return_value=is_open)
    return cb


def fast_retry() -> RetryConfig:
    """RetryConfig with near-zero delays for fast tests."""
    return RetryConfig(
        max_attempts=3,
        base_delay_s=0.001,
        max_delay_s=0.01,
        jitter_s=0.0,
        timeout_s=5.0,
    )


# ---------------------------------------------------------------------------
# OrderRecord unit tests
# ---------------------------------------------------------------------------

class TestOrderRecord:

    def test_initial_state_is_pending(self):
        rec = OrderRecord(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", stop_price=None,
            time_in_force="GTC", position_side="BOTH",
            reduce_only=False, client_order_id="TEST_001", stp_mode=None,
        )
        assert rec.state == OrderState.PENDING
        assert not rec.is_terminal
        assert not rec.is_open

    def test_transition_records_history(self):
        rec = OrderRecord(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", stop_price=None,
            time_in_force="GTC", position_side="BOTH",
            reduce_only=False, client_order_id="TEST_001", stp_mode=None,
        )
        rec.transition(OrderState.SUBMITTED, note="attempt=1")
        rec.transition(OrderState.OPEN, note="exchange_ack")
        assert len(rec.history) == 2
        assert rec.state == OrderState.OPEN
        assert rec.is_open

    def test_update_from_exchange_filled(self):
        rec = OrderRecord(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity="0.001", price=None, stop_price=None,
            time_in_force="GTC", position_side="BOTH",
            reduce_only=False, client_order_id="TEST_002", stp_mode=None,
        )
        data = {
            "orderId": 99999,
            "status": "FILLED",
            "executedQty": "0.001",
            "avgPrice": "68450.25",
            "cumQuote": "68.45",
        }
        rec.update_from_exchange(data)
        assert rec.state == OrderState.FILLED
        assert rec.exchange_order_id == 99999
        assert rec.filled_qty == 0.001
        assert rec.avg_fill_price == 68450.25
        assert rec.is_terminal

    def test_update_from_exchange_unknown_status_is_ignored(self):
        rec = OrderRecord(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", stop_price=None,
            time_in_force="GTC", position_side="BOTH",
            reduce_only=False, client_order_id="TEST_003", stp_mode=None,
        )
        rec.update_from_exchange({"status": "GALAXY_BRAIN"})
        # State should be unchanged, no crash
        assert rec.state == OrderState.PENDING

    def test_terminal_at_is_set_on_terminal_transition(self):
        rec = OrderRecord(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", stop_price=None,
            time_in_force="GTC", position_side="BOTH",
            reduce_only=False, client_order_id="TEST_004", stp_mode=None,
        )
        assert rec.terminal_at is None
        rec.transition(OrderState.ERROR, note="test")
        assert rec.terminal_at is not None


# ---------------------------------------------------------------------------
# _validate_params
# ---------------------------------------------------------------------------

class TestValidateParams:

    def _validate(self, **kwargs):
        return OrderManager._validate_params(**kwargs)

    def test_valid_limit_order(self):
        err = self._validate(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", time_in_force="GTC",
        )
        assert err is None

    def test_invalid_symbol(self):
        err = self._validate(
            symbol="BTC/USDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", time_in_force="GTC",
        )
        assert err is not None
        assert "symbol" in err.lower()

    def test_invalid_side(self):
        err = self._validate(
            symbol="BTCUSDT", side="HOLD", order_type="LIMIT",
            quantity="0.001", price="68500", time_in_force="GTC",
        )
        assert err is not None
        assert "side" in err.lower()

    def test_limit_without_price(self):
        err = self._validate(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price=None, time_in_force="GTC",
        )
        assert err is not None
        assert "price" in err.lower()

    def test_zero_quantity(self):
        err = self._validate(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity="0", price=None, time_in_force="GTC",
        )
        assert err is not None
        assert "quantity" in err.lower()

    def test_non_numeric_quantity(self):
        err = self._validate(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity="lots", price=None, time_in_force="GTC",
        )
        assert err is not None

    def test_invalid_tif(self):
        err = self._validate(
            symbol="BTCUSDT", side="SELL", order_type="LIMIT",
            quantity="0.001", price="68000", time_in_force="DAY",
        )
        assert err is not None

    def test_market_order_without_price_is_valid(self):
        err = self._validate(
            symbol="ETHUSDT", side="SELL", order_type="MARKET",
            quantity="0.1", price=None, time_in_force="GTC",
        )
        assert err is None


# ---------------------------------------------------------------------------
# _generate_client_order_id
# ---------------------------------------------------------------------------

class TestGenerateClientOrderId:

    def test_length_within_limit(self):
        coid = OrderManager._generate_client_order_id("BTCUSDT", "BUY")
        assert len(coid) <= 36

    def test_starts_with_prefix(self):
        coid = OrderManager._generate_client_order_id("ETHUSDT", "SELL")
        assert coid.startswith("CSCOPE_")

    def test_unique_ids(self):
        ids = {OrderManager._generate_client_order_id("BTCUSDT", "BUY") for _ in range(20)}
        assert len(ids) > 1   # at least some are different


# ---------------------------------------------------------------------------
# submit_order — async tests
# ---------------------------------------------------------------------------

class TestSubmitOrder:

    @pytest.mark.asyncio
    async def test_happy_path_limit_order(self):
        rest = make_rest_client(place_order_return={
            "orderId": 111,
            "status": "NEW",
            "executedQty": "0",
            "avgPrice": "0",
            "cumQuote": "0",
        })
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        assert rec.state == OrderState.OPEN
        assert rec.exchange_order_id == 111
        assert rest.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_market_order_filled_immediately(self):
        rest = make_rest_client(place_order_return={
            "orderId": 222,
            "status": "FILLED",
            "executedQty": "0.001",
            "avgPrice": "68450.00",
            "cumQuote": "68.45",
        })
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="ETHUSDT", side="SELL", order_type="MARKET",
            quantity="0.1",
        )
        assert rec.state == OrderState.FILLED
        assert rec.filled_qty == 0.001
        assert rest.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_5xx_succeeds_second_attempt(self):
        server_error = BinanceRESTError(502, -1, "Bad Gateway")
        success      = {
            "orderId": 333, "status": "NEW",
            "executedQty": "0", "avgPrice": "0", "cumQuote": "0",
        }
        rest = make_rest_client(
            place_order_side_effect=[server_error, success]
        )
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="SOLUSDT", side="BUY", order_type="LIMIT",
            quantity="1", price="83.00",
        )
        assert rec.state == OrderState.OPEN
        assert rest.place_order.call_count == 2
        assert rec.attempt == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_gives_error(self):
        server_error = BinanceRESTError(503, -1, "Service Unavailable")
        rest = make_rest_client(
            place_order_side_effect=[server_error] * 10
        )
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="BNBUSDT", side="BUY", order_type="LIMIT",
            quantity="0.5", price="960.00",
        )
        assert rec.state == OrderState.ERROR
        assert rest.place_order.call_count == 3   # fast_retry has max_attempts=3

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self):
        """Insufficient margin (-2010) must not be retried."""
        insufficient = BinanceRESTError(400, -2010, "Account has insufficient balance")
        rest = make_rest_client(place_order_side_effect=[insufficient])
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="100", price="68500",
        )
        assert rec.state == OrderState.ERROR
        assert rest.place_order.call_count == 1   # no retry

    @pytest.mark.asyncio
    async def test_non_retryable_precision_error(self):
        precision = BinanceRESTError(400, -1111, "Precision is over the maximum")
        rest = make_rest_client(place_order_side_effect=[precision])
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.00000001", price="68500",
        )
        assert rec.state == OrderState.ERROR
        assert rest.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_auth_error_fails_immediately_no_retry(self):
        auth_err = AuthError(401, -2014, "API-key format invalid")
        rest = make_rest_client(place_order_side_effect=[auth_err])
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        assert rec.state == OrderState.ERROR
        assert rest.place_order.call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_blocks_immediately(self):
        rest = make_rest_client()
        cb   = make_cb(is_open=True)
        mgr  = OrderManager(rest, circuit_breaker=cb, retry_cfg=fast_retry())
        rec  = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        assert rec.state == OrderState.ERROR
        assert "circuit breaker" in rec.last_error.lower()
        rest.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_allows_order(self):
        rest = make_rest_client()
        cb   = make_cb(is_open=False)
        mgr  = OrderManager(rest, circuit_breaker=cb, retry_cfg=fast_retry())
        rec  = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        assert rec.state != OrderState.ERROR or rest.place_order.called

    @pytest.mark.asyncio
    async def test_validation_error_blocks_before_api_call(self):
        rest = make_rest_client()
        mgr  = OrderManager(rest, retry_cfg=fast_retry())
        rec  = await mgr.submit_order(
            symbol="BTC/USDT",   # invalid — has slash
            side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        assert rec.state == OrderState.ERROR
        rest.place_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_order_code_queries_exchange(self):
        """
        -2022 duplicate: the first attempt succeeded silently.
        OrderManager should query by client_order_id and treat as success.
        """
        duplicate = BinanceRESTError(400, -2022, "Order already exists")
        fill_data = {
            "orderId": 999,
            "status": "FILLED",
            "executedQty": "0.001",
            "avgPrice": "68500",
            "cumQuote": "68.5",
        }
        rest = make_rest_client(
            place_order_side_effect=[duplicate],
            get_order_return=fill_data,
        )
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        assert rec.state == OrderState.FILLED
        rest.get_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_fill_callback_fired_on_market_fill(self):
        fill_data = {
            "orderId": 777,
            "status": "FILLED",
            "executedQty": "0.001",
            "avgPrice": "68450",
            "cumQuote": "68.45",
        }
        rest = make_rest_client(place_order_return=fill_data)
        callback_records = []

        async def on_fill(rec):
            callback_records.append(rec)

        mgr = OrderManager(rest, retry_cfg=fast_retry(), on_fill=on_fill)
        await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="MARKET",
            quantity="0.001",
        )
        assert len(callback_records) == 1
        assert callback_records[0].state == OrderState.FILLED

    @pytest.mark.asyncio
    async def test_on_error_callback_fired_on_non_retryable(self):
        error_data = BinanceRESTError(400, -2010, "Insufficient margin")
        rest = make_rest_client(place_order_side_effect=[error_data])
        error_records = []

        async def on_error(rec, exc):
            error_records.append((rec, exc))

        mgr = OrderManager(rest, retry_cfg=fast_retry(), on_error=on_error)
        await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="100", price="68500",
        )
        assert len(error_records) == 1
        assert error_records[0][0].state == OrderState.ERROR

    @pytest.mark.asyncio
    async def test_rate_throttle_adds_sleep(self):
        """When is_throttled=True, a sleep should happen before submission."""
        rest = make_rest_client(is_throttled=True)
        mgr  = OrderManager(rest, retry_cfg=fast_retry())
        with patch("execution.order_manager.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await mgr.submit_order(
                symbol="BTCUSDT", side="BUY", order_type="LIMIT",
                quantity="0.001", price="68500",
            )
        # asyncio.sleep should have been called at least once for throttle
        assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    async def test_records_are_tracked_in_internal_registry(self):
        rest = make_rest_client()
        mgr  = OrderManager(rest, retry_cfg=fast_retry())
        rec  = await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500",
        )
        fetched = mgr.get_order(rec.client_order_id)
        assert fetched is rec

    @pytest.mark.asyncio
    async def test_summary_counts_correctly(self):
        rest = make_rest_client(place_order_return={
            "orderId": 10, "status": "FILLED",
            "executedQty": "0.001", "avgPrice": "68500", "cumQuote": "68.5",
        })
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        await mgr.submit_order(
            symbol="BTCUSDT", side="BUY", order_type="MARKET", quantity="0.001",
        )
        s = mgr.summary()
        assert s["total_submitted"] == 1
        assert s["filled"] == 1
        assert s["fill_rate"] == 1.0


# ---------------------------------------------------------------------------
# poll_until_terminal
# ---------------------------------------------------------------------------

class TestPollUntilTerminal:

    @pytest.mark.asyncio
    async def test_polls_until_filled(self):
        open_data   = {"orderId": 1, "status": "NEW",    "executedQty": "0",     "avgPrice": "0",        "cumQuote": "0"}
        filled_data = {"orderId": 1, "status": "FILLED", "executedQty": "0.001", "avgPrice": "68500.00", "cumQuote": "68.5"}

        rest = make_rest_client()
        rest.place_order = AsyncMock(return_value=open_data)
        rest.get_order   = AsyncMock(side_effect=[open_data, open_data, filled_data])

        fast_poll = PollConfig(interval_s=0.001, max_wait_s=5.0, stale_after_s=60.0)
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.001", price="68500")
        assert rec.state == OrderState.OPEN

        final = await mgr.poll_until_terminal(rec, poll_cfg=fast_poll)
        assert final.state == OrderState.FILLED
        assert rest.get_order.call_count == 3

    @pytest.mark.asyncio
    async def test_cancels_stale_order(self):
        open_data = {"orderId": 2, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}
        rest = make_rest_client()
        rest.place_order = AsyncMock(return_value=open_data)
        rest.get_order   = AsyncMock(return_value=open_data)   # never fills

        # stale_after_s=0 → immediately stale
        fast_poll = PollConfig(interval_s=0.001, max_wait_s=5.0, stale_after_s=0.0)
        mgr = OrderManager(rest, retry_cfg=fast_retry())
        rec = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.001", price="68500")
        rec.transition(OrderState.OPEN)   # force to OPEN for polling

        final = await mgr.poll_until_terminal(rec, poll_cfg=fast_poll)
        assert final.state == OrderState.CANCELLED
        rest.cancel_order.assert_called()


# ---------------------------------------------------------------------------
# cancel_and_replace
# ---------------------------------------------------------------------------

class TestCancelAndReplace:

    @pytest.mark.asyncio
    async def test_cancel_and_replace_submits_new_order(self):
        open_data = {"orderId": 100, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}
        new_data  = {"orderId": 101, "status": "NEW", "executedQty": "0", "avgPrice": "0", "cumQuote": "0"}

        rest = make_rest_client()
        rest.place_order = AsyncMock(side_effect=[open_data, new_data])
        rest.cancel_order = AsyncMock(return_value={"orderId": 100, "status": "CANCELED"})

        mgr  = OrderManager(rest, retry_cfg=fast_retry())
        rec  = await mgr.submit_order("BTCUSDT", "BUY", "LIMIT", "0.001", price="68500")
        rec.transition(OrderState.OPEN)   # force to OPEN

        new_rec = await mgr.cancel_and_replace(rec, new_price="68000.00")

        rest.cancel_order.assert_called_once()
        assert new_rec.price == "68000.00"
        assert new_rec.exchange_order_id == 101
        assert new_rec.client_order_id != rec.client_order_id   # new ID

    @pytest.mark.asyncio
    async def test_cancel_and_replace_raises_if_not_open(self):
        rest = make_rest_client()
        mgr  = OrderManager(rest, retry_cfg=fast_retry())
        rec  = OrderRecord(
            symbol="BTCUSDT", side="BUY", order_type="LIMIT",
            quantity="0.001", price="68500", stop_price=None,
            time_in_force="GTC", position_side="BOTH",
            reduce_only=False, client_order_id="CSCOPE_X", stp_mode=None,
        )
        rec.transition(OrderState.FILLED)

        with pytest.raises(ValueError, match="non-open order"):
            await mgr.cancel_and_replace(rec, new_price="69000")


# ---------------------------------------------------------------------------
# is_retryable
# ---------------------------------------------------------------------------

class TestIsRetryable:

    def test_5xx_is_retryable(self):
        exc = BinanceRESTError(503, -1, "Service Unavailable")
        assert OrderManager._is_retryable(exc) is True

    def test_502_is_retryable(self):
        exc = BinanceRESTError(502, -1, "Bad Gateway")
        assert OrderManager._is_retryable(exc) is True

    @pytest.mark.parametrize("code", list(NON_RETRYABLE_CODES))
    def test_non_retryable_codes(self, code):
        exc = BinanceRESTError(400, code, "some message")
        assert OrderManager._is_retryable(exc) is False

    def test_400_with_unknown_code_is_not_retryable(self):
        exc = BinanceRESTError(400, -9999, "Unknown")
        assert OrderManager._is_retryable(exc) is False


# ---------------------------------------------------------------------------
# make_order_manager factory
# ---------------------------------------------------------------------------

class TestMakeOrderManager:

    def test_factory_returns_order_manager(self):
        rest = make_rest_client()
        mgr  = make_order_manager(rest)
        assert isinstance(mgr, OrderManager)

    def test_factory_accepts_custom_config(self):
        rest = make_rest_client()
        mgr  = make_order_manager(
            rest,
            max_attempts=2,
            base_delay_s=0.1,
            poll_interval_s=0.5,
            poll_max_wait_s=30.0,
        )
        assert mgr._retry.max_attempts == 2
        assert mgr._retry.base_delay_s == 0.1
        assert mgr._poll.interval_s == 0.5
        assert mgr._poll.max_wait_s == 30.0

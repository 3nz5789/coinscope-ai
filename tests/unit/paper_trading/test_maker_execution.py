"""
Unit tests for CoinScopeAI Paper Trading — MakerExecutor.

Test coverage
─────────────
- Happy path: limit order fills on first attempt
- Happy path: limit order fills on retry (after first timeout)
- Market fallback: limit order never fills, falls back to MARKET
- Safety-gate rejection is surfaced correctly
- Exchange error on orderbook fetch is handled
- Order already FILLED immediately on submission (crossed spread)
- Slippage savings calculation is correct
- Price nudge logic (BUY/SELL) moves correctly toward market
- stats() aggregation across multiple executions
"""

import time
import pytest
from unittest.mock import MagicMock

from services.paper_trading.exchange_client import ExchangeError
from services.paper_trading.maker_execution import (
    ExecutionStrategy,
    MakerExecutor,
)
from services.paper_trading.order_manager import (
    ManagedOrder,
    OrderManager,
    OrderStatus,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _order(
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    price=50_000.0,
    quantity=0.01,
    status=OrderStatus.SUBMITTED,
    avg_fill_price=0.0,
    filled_qty=0.0,
    exchange_order_id=99999,
    rejection_reason="",
):
    return ManagedOrder(
        internal_id="CSA-test001",
        symbol=symbol, side=side, order_type=order_type,
        quantity=quantity, price=price, leverage=3,
        status=status, exchange_order_id=exchange_order_id,
        avg_fill_price=avg_fill_price, filled_qty=filled_qty,
        rejection_reason=rejection_reason,
        created_at=time.time(), submitted_at=time.time(),
    )


def _filled(**kw):
    kw.setdefault("status", OrderStatus.FILLED)
    kw.setdefault("avg_fill_price", 50_000.0)
    kw.setdefault("filled_qty", 0.01)
    return _order(**kw)


def _book(bid=49_995.0, ask=50_005.0):
    return {"bids": [[str(bid), "1.0"]], "asks": [[str(ask), "1.0"]]}


def _raw(status="FILLED", avg=49_995.0, qty=0.01):
    return {"status": status, "avgPrice": str(avg), "executedQty": str(qty)}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_exchange():
    ex = MagicMock()
    ex.get_orderbook.return_value = _book()
    ex.get_ticker_price.return_value = 50_000.0
    ex.get_order.return_value = _raw()
    ex.cancel_order.return_value = {}
    return ex


@pytest.fixture
def mock_mgr():
    return MagicMock(spec=OrderManager)


@pytest.fixture
def exe(mock_mgr, mock_exchange):
    return MakerExecutor(
        order_manager=mock_mgr,
        exchange=mock_exchange,
        fill_timeout_s=1,
        poll_interval_s=0.05,
        max_retries=2,
        price_adjust_pct=0.0005,
    )


@pytest.fixture
def retry_exe(mock_mgr, mock_exchange):
    """Executor with near-zero fill timeout so one 'NEW' response triggers a retry."""
    return MakerExecutor(
        order_manager=mock_mgr,
        exchange=mock_exchange,
        fill_timeout_s=0.001,   # expires after one 0.05s poll
        poll_interval_s=0.05,
        max_retries=2,
        price_adjust_pct=0.0005,
    )


# ── Happy paths ────────────────────────────────────────────────────────────────

def test_fills_first_attempt(exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.return_value = (True, _order())
    mock_exchange.get_order.return_value = _raw("FILLED", 49_995.0)

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is True
    assert r.strategy == ExecutionStrategy.MAKER_FIRST_TRY
    assert r.retries == 0
    assert r.final_fill_price == pytest.approx(49_995.0)


def test_buy_placed_at_best_bid(exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.return_value = (True, _order())
    mock_exchange.get_order.return_value = _raw("FILLED")

    exe.execute("BTCUSDT", "BUY", 0.01)

    _, kw = mock_mgr.submit_order.call_args
    assert kw["price"] == pytest.approx(49_995.0)
    assert kw["order_type"] == "LIMIT"


def test_sell_placed_at_best_ask(exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.return_value = (True, _order(side="SELL"))
    mock_exchange.get_order.return_value = _raw("FILLED", 50_005.0)

    exe.execute("BTCUSDT", "SELL", 0.01)

    _, kw = mock_mgr.submit_order.call_args
    assert kw["price"] == pytest.approx(50_005.0)


def test_already_filled_on_submission_skips_poll(exe, mock_mgr, mock_exchange):
    """Crossed-spread limit — exchange returns FILLED immediately."""
    mock_mgr.submit_order.return_value = (True, _filled(avg_fill_price=50_002.0))

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is True
    assert r.final_fill_price == pytest.approx(50_002.0)
    mock_exchange.get_order.assert_not_called()


def test_slippage_saved_positive_for_buy_below_mid(exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.return_value = (True, _order())
    mock_exchange.get_order.return_value = _raw("FILLED", 49_995.0)

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.slippage_saved_bps > 0


def test_fill_latency_recorded(exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.return_value = (True, _order())
    mock_exchange.get_order.return_value = _raw("FILLED")

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.fill_latency_ms >= 0


# ── Retry after timeout ────────────────────────────────────────────────────────

def test_retry_fills_second_attempt(retry_exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.side_effect = [
        (True, _order()),   # attempt 0 → times out
        (True, _order()),   # attempt 1 → fills
    ]
    mock_exchange.get_order.side_effect = [
        _raw("NEW"),              # attempt 0 poll — still open (then timeout)
        _raw("FILLED", 49_997.0), # attempt 1 poll — filled
    ]

    r = retry_exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is True
    assert r.strategy == ExecutionStrategy.MAKER_RETRY
    assert r.retries == 1


def test_buy_retry_price_nudged_up(retry_exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.side_effect = [
        (True, _order()),
        (True, _order()),
    ]
    mock_exchange.get_order.side_effect = [
        _raw("NEW"),
        _raw("FILLED"),
    ]

    retry_exe.execute("BTCUSDT", "BUY", 0.01)

    p0 = mock_mgr.submit_order.call_args_list[0][1]["price"]
    p1 = mock_mgr.submit_order.call_args_list[1][1]["price"]
    assert p1 > p0, "Retry BUY price should move toward ask"


def test_sell_retry_price_nudged_down(retry_exe, mock_mgr, mock_exchange):
    mock_mgr.submit_order.side_effect = [
        (True, _order(side="SELL")),
        (True, _order(side="SELL")),
    ]
    mock_exchange.get_order.side_effect = [
        _raw("NEW"),
        _raw("FILLED"),
    ]

    retry_exe.execute("BTCUSDT", "SELL", 0.01)

    p0 = mock_mgr.submit_order.call_args_list[0][1]["price"]
    p1 = mock_mgr.submit_order.call_args_list[1][1]["price"]
    assert p1 < p0, "Retry SELL price should move toward bid"


# ── Market fallback ────────────────────────────────────────────────────────────

def test_market_fallback_after_max_retries(exe, mock_mgr, mock_exchange):
    unfilled_side_effects = [(True, _order())] * (exe.max_retries + 1)
    market_fill = (True, _filled(order_type="MARKET", avg_fill_price=50_010.0))
    mock_mgr.submit_order.side_effect = unfilled_side_effects + [market_fill]
    mock_exchange.get_order.return_value = _raw("NEW")

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is True
    assert r.strategy == ExecutionStrategy.MARKET_FALLBACK
    last_call = mock_mgr.submit_order.call_args_list[-1]
    assert last_call[1]["order_type"] == "MARKET"


def test_market_fallback_slippage_zero(exe, mock_mgr, mock_exchange):
    unfilled_side_effects = [(True, _order())] * (exe.max_retries + 1)
    mock_mgr.submit_order.side_effect = (
        unfilled_side_effects + [(True, _filled(order_type="MARKET"))]
    )
    mock_exchange.get_order.return_value = _raw("NEW")

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.slippage_saved_bps == pytest.approx(0.0)


# ── Rejection / errors ────────────────────────────────────────────────────────

def test_safety_gate_rejection(exe, mock_mgr):
    rejected = _order(
        status=OrderStatus.REJECTED_SAFETY,
        rejection_reason="position_limit: too many open",
    )
    mock_mgr.submit_order.return_value = (False, rejected)

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is False
    assert r.strategy == ExecutionStrategy.REJECTED
    assert "position_limit" in r.error_message


def test_exchange_error_on_orderbook(exe, mock_mgr, mock_exchange):
    mock_exchange.get_orderbook.side_effect = ExchangeError("timeout")

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is False
    assert r.strategy == ExecutionStrategy.FAILED
    mock_mgr.submit_order.assert_not_called()


def test_empty_orderbook(exe, mock_mgr, mock_exchange):
    mock_exchange.get_orderbook.return_value = {"bids": [], "asks": []}

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is False
    assert r.strategy == ExecutionStrategy.FAILED


def test_order_cancelled_by_exchange_during_poll_falls_back(exe, mock_mgr, mock_exchange):
    unfilled_side_effects = [(True, _order())] * (exe.max_retries + 1)
    mock_mgr.submit_order.side_effect = (
        unfilled_side_effects + [(True, _filled(order_type="MARKET"))]
    )
    mock_exchange.get_order.return_value = _raw("CANCELED")

    r = exe.execute("BTCUSDT", "BUY", 0.01)

    assert r.success is True  # should eventually market-fill


# ── Price nudge bounds ─────────────────────────────────────────────────────────

def test_buy_nudge_never_exceeds_ask(exe):
    bid, ask = 49_995.0, 50_005.0
    price = bid
    for attempt in range(1, 6):
        price = exe._nudge_toward_market(price, "BUY", bid, ask, attempt)
        assert price <= ask


def test_sell_nudge_never_goes_below_bid(exe):
    bid, ask = 49_995.0, 50_005.0
    price = ask
    for attempt in range(1, 6):
        price = exe._nudge_toward_market(price, "SELL", bid, ask, attempt)
        assert price >= bid


# ── Stats aggregation ─────────────────────────────────────────────────────────

def test_stats_maker_fills(exe, mock_mgr, mock_exchange):
    # Use side_effect so each execute() gets a fresh (unmodified) ManagedOrder
    mock_mgr.submit_order.side_effect = [
        (True, _order()),
        (True, _order()),
    ]
    mock_exchange.get_order.return_value = _raw("FILLED", 49_995.0)

    exe.execute("BTCUSDT", "BUY", 0.01)
    exe.execute("BTCUSDT", "BUY", 0.01)

    s = exe.stats
    assert s["total_orders"] == 2
    assert s["maker_fills"] == 2
    assert s["market_fallbacks"] == 0
    assert s["maker_fill_rate_pct"] == pytest.approx(100.0)


def test_stats_market_fallbacks(exe, mock_mgr, mock_exchange):
    side_eff = [(True, _order())] * (exe.max_retries + 1) + [(True, _filled(order_type="MARKET"))]
    mock_mgr.submit_order.side_effect = side_eff
    mock_exchange.get_order.return_value = _raw("NEW")

    exe.execute("BTCUSDT", "BUY", 0.01)

    s = exe.stats
    assert s["market_fallbacks"] == 1
    assert s["maker_fills"] == 0

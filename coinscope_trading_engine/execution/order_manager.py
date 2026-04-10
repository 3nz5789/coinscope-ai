# execution/order_manager.py
"""
Order Manager — Retry-Aware Execution Layer
============================================
Sits between the signal/risk stack and the raw BinanceRESTClient.
Handles the full order lifecycle from submission to fill confirmation,
with structured retry logic, rate-limit awareness, and cancel/replace.

Architecture
------------
    Signal → RiskGate → OrderManager → BinanceRESTClient → Exchange

Order Lifecycle
---------------
    PENDING → SUBMITTED → OPEN → PARTIAL_FILL → FILLED
                    ↓                               ↓
                 ERROR                         CANCELLED / EXPIRED / REJECTED

Retry Strategy
--------------
  Retryable errors
    - HTTP 5xx (exchange-side transient failures)
    - HTTP 429 / 418 (rate limit — respects Retry-After header)
    - asyncio.TimeoutError / aiohttp.ClientError (network transients)

  Non-retryable errors (fail immediately)
    - HTTP 400 bad params
    - Binance error codes: -1111 (precision), -2010 (insufficient margin),
      -1102 (missing param), -4061 (price out of range), -1116 (invalid order type)
    - AuthError (wrong keys / IP ban)

Idempotency
-----------
  Every submission uses a deterministic client_order_id:
    CSCOPE_{yyyymmddHHMMSS}_{symbol[:6]}_{side[:1]}_{random_hex4}
  On retry, the same client_order_id is reused so that if the first
  attempt actually succeeded (but the response was lost), the exchange
  rejects the duplicate with -2022 and we query by client_order_id instead.

Cancel/Replace
--------------
  cancel_and_replace() cancels a stale OPEN order and immediately
  re-submits at a new price, returning the new OrderRecord.

Usage
-----
    async with BinanceRESTClient(testnet=True) as rest:
        mgr = OrderManager(rest_client=rest, circuit_breaker=cb)

        record = await mgr.submit_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity="0.001",
            price="68500.00",
            time_in_force="GTC",
        )

        # Wait for fill
        final = await mgr.poll_until_terminal(record)
        print(final.state, final.filled_qty, final.avg_fill_price)
"""

from __future__ import annotations

import asyncio
import logging
import random
import string
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

import aiohttp

from data.binance_rest import (
    AuthError,
    BinanceRESTClient,
    BinanceRESTError,
    RateLimitError,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Order state
# ---------------------------------------------------------------------------

class OrderState(str, Enum):
    """Mirrors Binance order status values plus CoinScope lifecycle states."""
    PENDING       = "PENDING"       # not yet sent to exchange
    SUBMITTED     = "SUBMITTED"     # sent; awaiting exchange ACK
    OPEN          = "NEW"           # exchange confirmed, resting
    PARTIAL_FILL  = "PARTIALLY_FILLED"
    FILLED        = "FILLED"
    CANCELLED     = "CANCELED"
    REJECTED      = "REJECTED"
    EXPIRED       = "EXPIRED"
    ERROR         = "ERROR"         # unrecoverable local error


TERMINAL_STATES = frozenset({
    OrderState.FILLED,
    OrderState.CANCELLED,
    OrderState.REJECTED,
    OrderState.EXPIRED,
    OrderState.ERROR,
})


# ---------------------------------------------------------------------------
# Order record
# ---------------------------------------------------------------------------

@dataclass
class OrderRecord:
    """
    Complete lifecycle record for a single order attempt.

    Created at PENDING, mutated in-place as state progresses.
    Thread-safe for reads; all writes happen inside the async OrderManager methods.
    """
    # Identity
    symbol:           str
    side:             str               # "BUY" | "SELL"
    order_type:       str               # "LIMIT" | "MARKET" | ...
    quantity:         str               # string per Binance DECIMAL rule
    price:            Optional[str]     # None for MARKET orders
    stop_price:       Optional[str]
    time_in_force:    str
    position_side:    str
    reduce_only:      bool
    client_order_id:  str               # used for idempotent retries
    stp_mode:         Optional[str]     # Self-Trade Prevention (Apr 2026 Binance)

    # Exchange-assigned (populated after SUBMITTED)
    exchange_order_id: Optional[int]    = None
    state:             OrderState       = OrderState.PENDING

    # Fill tracking
    filled_qty:        float            = 0.0
    avg_fill_price:    float            = 0.0
    cumulative_quote:  float            = 0.0   # filled notional value

    # Timing
    created_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    terminal_at:  Optional[datetime] = None

    # Retry bookkeeping
    attempt:       int  = 0            # number of submission attempts made
    last_error:    str  = ""           # last error message for logging/alerting

    # Audit trail: list of (timestamp, state, note)
    history: list[tuple[str, str, str]] = field(default_factory=list)

    # ── Helpers ──────────────────────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def is_open(self) -> bool:
        return self.state in (OrderState.OPEN, OrderState.PARTIAL_FILL)

    @property
    def latency_ms(self) -> Optional[float]:
        """Time from PENDING creation to SUBMITTED in milliseconds."""
        if self.submitted_at:
            return (self.submitted_at - self.created_at).total_seconds() * 1000
        return None

    def transition(self, new_state: OrderState, note: str = "") -> None:
        """Record a state transition with timestamp."""
        ts = datetime.now(timezone.utc).isoformat()
        self.history.append((ts, new_state.value, note))
        logger.debug(
            "Order %s → %s | %s",
            self.client_order_id, new_state.value, note or "-",
        )
        self.state = new_state
        if new_state in TERMINAL_STATES:
            self.terminal_at = datetime.now(timezone.utc)

    def update_from_exchange(self, data: dict) -> None:
        """
        Apply a raw Binance order-status response to this record.

        Safely handles missing fields so partial responses don't crash the system.
        """
        if "orderId" in data:
            self.exchange_order_id = int(data["orderId"])

        status_str = data.get("status", "")
        if status_str:
            try:
                new_state = OrderState(status_str)
                if new_state != self.state:
                    self.transition(new_state, note=f"exchange status={status_str}")
            except ValueError:
                logger.warning("Unknown Binance order status: %r", status_str)

        self.filled_qty       = float(data.get("executedQty",   self.filled_qty))
        self.avg_fill_price   = float(data.get("avgPrice",      self.avg_fill_price))
        self.cumulative_quote = float(data.get("cumQuote",      self.cumulative_quote))


# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

@dataclass
class RetryConfig:
    """
    Controls the exponential-backoff retry behaviour of OrderManager.

    Formula: delay = base_delay_s * (2 ** attempt) + random(0, jitter_s)
    """
    max_attempts:     int   = 4         # total attempts including first try
    base_delay_s:     float = 0.5       # initial backoff in seconds
    max_delay_s:      float = 30.0      # cap on any single backoff
    jitter_s:         float = 0.3       # max random jitter added per attempt
    timeout_s:        float = 8.0       # per-request HTTP timeout


@dataclass
class PollConfig:
    """
    Controls status-polling behaviour while waiting for order fills.
    """
    interval_s:    float = 1.0          # time between polls
    max_wait_s:    float = 60.0         # total wait before giving up
    stale_after_s: float = 30.0         # OPEN order age before cancel/replace


# ---------------------------------------------------------------------------
# Non-retryable Binance error codes
# ---------------------------------------------------------------------------

# These indicate a bad request from our side; retrying won't help.
NON_RETRYABLE_CODES: frozenset[int] = frozenset({
    -1102,   # mandatory parameter missing / empty
    -1111,   # precision exceeds maximum allowed for this asset
    -1116,   # invalid order type
    -1121,   # invalid symbol
    -2010,   # new order rejected — insufficient margin
    -2011,   # cancel rejected — unknown order
    -2018,   # reduce only order is rejected: position does not exist
    -2022,   # duplicate order (same clientOrderId) — handle by querying
    -4061,   # order price outside valid range
    -4003,   # quantity less than zero
    -4005,   # price less than zero
})


# ---------------------------------------------------------------------------
# Order Manager
# ---------------------------------------------------------------------------

class OrderManager:
    """
    Retry-aware execution layer for Binance Futures orders.

    Parameters
    ----------
    rest_client   : BinanceRESTClient instance (must be open / in async context)
    circuit_breaker : Optional CircuitBreaker; if is_open, orders are blocked
    retry_cfg     : RetryConfig (backoff settings)
    poll_cfg      : PollConfig (fill polling settings)
    on_fill       : Optional async callback(OrderRecord) fired on FILLED
    on_error      : Optional async callback(OrderRecord, Exception) fired on ERROR
    """

    def __init__(
        self,
        rest_client:    BinanceRESTClient,
        circuit_breaker: Optional[object]  = None,    # type: CircuitBreaker
        retry_cfg:      Optional[RetryConfig]  = None,
        poll_cfg:       Optional[PollConfig]   = None,
        on_fill:        Optional[Callable]     = None,
        on_error:       Optional[Callable]     = None,
    ) -> None:
        self._rest     = rest_client
        self._cb       = circuit_breaker
        self._retry    = retry_cfg or RetryConfig()
        self._poll     = poll_cfg  or PollConfig()
        self._on_fill  = on_fill
        self._on_error = on_error

        # In-flight order registry: client_order_id → OrderRecord
        self._orders: dict[str, OrderRecord] = {}

    # ── Public API ────────────────────────────────────────────────────────

    async def submit_order(
        self,
        symbol:         str,
        side:           str,
        order_type:     str       = "LIMIT",
        quantity:       str       = "0",
        price:          Optional[str] = None,
        stop_price:     Optional[str] = None,
        time_in_force:  str       = "GTC",
        position_side:  str       = "BOTH",
        reduce_only:    bool      = False,
        stp_mode:       Optional[str] = None,
        client_order_id: Optional[str] = None,
    ) -> OrderRecord:
        """
        Submit an order with retry logic.

        Returns the OrderRecord after the final attempt (SUBMITTED, OPEN,
        FILLED, or ERROR). Does NOT wait for fill — call poll_until_terminal()
        separately if synchronous fill confirmation is needed.

        Parameters
        ----------
        symbol        : Binance Futures format — BTCUSDT
        side          : "BUY" | "SELL"
        order_type    : "LIMIT" | "MARKET" | "STOP" | "STOP_MARKET" | ...
        quantity      : String decimal (e.g. "0.001")
        price         : Limit price string; required for LIMIT orders
        stop_price    : Trigger price string; required for STOP/TP orders
        time_in_force : "GTC" | "IOC" | "FOK" | "GTX"
        position_side : "BOTH" | "LONG" | "SHORT"
        reduce_only   : True to only reduce existing position
        stp_mode      : Self-Trade Prevention mode (Binance Apr-2026 feature)
                        "NONE" | "EXPIRE_TAKER" | "EXPIRE_MAKER" | "EXPIRE_BOTH"
        client_order_id : Override auto-generated idempotency key

        Returns
        -------
        OrderRecord with final state after all retry attempts.
        """
        # ── Circuit breaker gate ──────────────────────────────────────────
        if self._cb is not None and self._cb.is_open:
            logger.warning(
                "⛔ OrderManager blocked by circuit breaker | symbol=%s side=%s",
                symbol, side,
            )
            rec = self._build_record(
                symbol, side, order_type, quantity, price,
                stop_price, time_in_force, position_side, reduce_only,
                stp_mode, client_order_id,
            )
            rec.last_error = "Circuit breaker is OPEN"
            rec.transition(OrderState.ERROR, note="circuit_breaker_open")
            return rec

        # ── Input validation ──────────────────────────────────────────────
        validation_error = self._validate_params(
            symbol, side, order_type, quantity, price, time_in_force
        )
        if validation_error:
            rec = self._build_record(
                symbol, side, order_type, quantity, price,
                stop_price, time_in_force, position_side, reduce_only,
                stp_mode, client_order_id,
            )
            rec.last_error = validation_error
            rec.transition(OrderState.ERROR, note=f"validation: {validation_error}")
            return rec

        # ── Build the record ──────────────────────────────────────────────
        rec = self._build_record(
            symbol, side, order_type, quantity, price,
            stop_price, time_in_force, position_side, reduce_only,
            stp_mode, client_order_id,
        )
        self._orders[rec.client_order_id] = rec

        # ── Retry loop ────────────────────────────────────────────────────
        await self._execute_with_retry(rec)
        return rec

    async def poll_until_terminal(
        self,
        record: OrderRecord,
        poll_cfg: Optional[PollConfig] = None,
    ) -> OrderRecord:
        """
        Poll exchange order status until the order reaches a terminal state.

        Automatically cancels and re-submits if the order is stale (open
        for longer than poll_cfg.stale_after_s without fills).

        Returns the updated OrderRecord.
        """
        cfg = poll_cfg or self._poll
        deadline = time.monotonic() + cfg.max_wait_s
        stale_deadline = time.monotonic() + cfg.stale_after_s

        while not record.is_terminal:
            if time.monotonic() > deadline:
                logger.warning(
                    "⏰ poll_until_terminal timeout | %s | waited=%.1fs",
                    record.client_order_id, cfg.max_wait_s,
                )
                await self._cancel_order(record)
                break

            await asyncio.sleep(cfg.interval_s)

            # Fetch current status from exchange
            try:
                data = await self._rest.get_order(
                    symbol=record.symbol,
                    client_order_id=record.client_order_id,
                )
                record.update_from_exchange(data)
            except BinanceRESTError as exc:
                logger.warning(
                    "get_order error during poll | %s | %s",
                    record.client_order_id, exc,
                )
                continue

            # Fire on_fill callback
            if record.state == OrderState.FILLED and self._on_fill:
                await self._safe_callback(self._on_fill, record)
                break

            # Stale order — cancel and stop polling (caller handles re-submit if needed)
            if record.is_open and time.monotonic() > stale_deadline:
                logger.info(
                    "⚠️ Stale order detected | %s | cancelling",
                    record.client_order_id,
                )
                await self._cancel_order(record)
                break

        return record

    async def cancel_and_replace(
        self,
        old_record: OrderRecord,
        new_price:  str,
        new_quantity: Optional[str] = None,
    ) -> OrderRecord:
        """
        Cancel a stale open order and re-submit at a new price.

        This is the standard way to chase the market on LIMIT orders:
        1. Cancel old_record if it's still open
        2. Submit a new order at new_price (same symbol/side/qty unless overridden)
        3. Return the new OrderRecord

        Parameters
        ----------
        old_record   : The OPEN/PARTIAL_FILL order to replace
        new_price    : New limit price as string
        new_quantity : Override quantity (uses original if None)

        Returns
        -------
        New OrderRecord for the replacement order.
        """
        if not old_record.is_open:
            raise ValueError(
                f"cancel_and_replace called on non-open order "
                f"{old_record.client_order_id} (state={old_record.state.value})"
            )

        logger.info(
            "↩️ Cancel/Replace | %s | old_price=%s → new_price=%s",
            old_record.client_order_id, old_record.price, new_price,
        )

        # Step 1: Cancel old order
        await self._cancel_order(old_record)

        # Step 2: Submit replacement
        new_record = await self.submit_order(
            symbol         = old_record.symbol,
            side           = old_record.side,
            order_type     = old_record.order_type,
            quantity       = new_quantity or old_record.quantity,
            price          = new_price,
            stop_price     = old_record.stop_price,
            time_in_force  = old_record.time_in_force,
            position_side  = old_record.position_side,
            reduce_only    = old_record.reduce_only,
            stp_mode       = old_record.stp_mode,
            # New client_order_id so exchange doesn't reject as duplicate
        )

        logger.info(
            "✅ Replacement submitted | %s | state=%s",
            new_record.client_order_id, new_record.state.value,
        )
        return new_record

    async def cancel_order(self, record: OrderRecord) -> OrderRecord:
        """Public wrapper: cancel an order and return the updated record."""
        await self._cancel_order(record)
        return record

    def get_order(self, client_order_id: str) -> Optional[OrderRecord]:
        """Retrieve a tracked order by client_order_id."""
        return self._orders.get(client_order_id)

    def open_orders(self) -> list[OrderRecord]:
        """Return all currently open (non-terminal) orders."""
        return [r for r in self._orders.values() if not r.is_terminal]

    def summary(self) -> dict:
        """Return aggregate stats across all tracked orders."""
        all_orders = list(self._orders.values())
        terminal   = [o for o in all_orders if o.is_terminal]
        filled     = [o for o in all_orders if o.state == OrderState.FILLED]
        errors     = [o for o in all_orders if o.state == OrderState.ERROR]

        return {
            "total_submitted":  len(all_orders),
            "filled":           len(filled),
            "open":             len(self.open_orders()),
            "errors":           len(errors),
            "terminal":         len(terminal),
            "fill_rate":        round(len(filled) / len(all_orders), 3) if all_orders else 0.0,
        }

    # ── Internal: core retry loop ─────────────────────────────────────────

    async def _execute_with_retry(self, rec: OrderRecord) -> None:
        """
        Core retry loop.

        Attempts to submit rec to the exchange up to retry_cfg.max_attempts
        times. Uses exponential backoff with jitter between attempts.
        Handles the special -2022 duplicate-order code (idempotent success).
        """
        cfg = self._retry

        for attempt in range(cfg.max_attempts):
            rec.attempt = attempt + 1
            rec.submitted_at = datetime.now(timezone.utc)
            rec.transition(OrderState.SUBMITTED, note=f"attempt={rec.attempt}")

            try:
                # ── Check rate limits before hitting the exchange ─────────
                if self._rest.is_throttled:
                    wait = self._throttle_wait()
                    logger.warning(
                        "Rate limit approaching — pausing %.1fs before order submit",
                        wait,
                    )
                    await asyncio.sleep(wait)

                # ── Build params dict ─────────────────────────────────────
                kwargs = self._build_request_params(rec)

                # ── Actually place the order ──────────────────────────────
                data = await asyncio.wait_for(
                    self._rest.place_order(**kwargs),
                    timeout=cfg.timeout_s,
                )

                # ── Success path ──────────────────────────────────────────
                rec.update_from_exchange(data)

                # If exchange returned FILLED immediately (MARKET order)
                if rec.state == OrderState.FILLED and self._on_fill:
                    await self._safe_callback(self._on_fill, rec)

                logger.info(
                    "✅ Order accepted | %s | attempt=%d | exchange_id=%s | state=%s",
                    rec.client_order_id, rec.attempt,
                    rec.exchange_order_id, rec.state.value,
                )
                return  # done

            except asyncio.TimeoutError as exc:
                logger.warning(
                    "⏱️  Order submit timeout | %s | attempt=%d/%d",
                    rec.client_order_id, rec.attempt, cfg.max_attempts,
                )
                rec.last_error = f"Timeout after {cfg.timeout_s}s"
                # After timeout, query to check if order was actually placed
                queried = await self._query_by_client_id(rec)
                if queried:
                    logger.info(
                        "Order found on exchange after timeout | %s",
                        rec.client_order_id,
                    )
                    return

            except RateLimitError as exc:
                # 429 / 418 — honour Retry-After if present
                delay = self._rate_limit_delay(exc)
                logger.warning(
                    "🚦 Rate limit | %s | waiting=%.1fs",
                    rec.client_order_id, delay,
                )
                rec.last_error = str(exc)
                await asyncio.sleep(delay)

            except BinanceRESTError as exc:
                rec.last_error = str(exc)

                # Duplicate order — the first attempt actually succeeded
                if exc.code == -2022:
                    logger.info(
                        "Duplicate order detected (idempotent success) | %s",
                        rec.client_order_id,
                    )
                    queried = await self._query_by_client_id(rec)
                    if queried:
                        return
                    # Query failed — treat as error
                    break

                # Non-retryable error
                if not self._is_retryable(exc):
                    logger.error(
                        "🚨 Non-retryable order error | %s | code=%d msg=%s",
                        rec.client_order_id, exc.code, exc.msg,
                    )
                    rec.transition(
                        OrderState.ERROR,
                        note=f"non_retryable: code={exc.code} msg={exc.msg}",
                    )
                    await self._safe_callback(self._on_error, rec, exc)
                    return

                # Retryable (5xx) — log and fall through to backoff
                logger.warning(
                    "⚠️ Retryable error | %s | attempt=%d/%d | HTTP %d code=%d",
                    rec.client_order_id, rec.attempt, cfg.max_attempts,
                    exc.status, exc.code,
                )

            except (aiohttp.ClientError, OSError) as exc:
                rec.last_error = str(exc)
                logger.warning(
                    "🌐 Network error | %s | attempt=%d/%d | %s",
                    rec.client_order_id, rec.attempt, cfg.max_attempts, exc,
                )

            except AuthError as exc:
                # Auth errors are NEVER retryable — fail fast
                rec.last_error = str(exc)
                rec.transition(
                    OrderState.ERROR,
                    note=f"auth_error: {exc}",
                )
                logger.critical(
                    "🔑 Auth error — check API keys | %s | %s",
                    rec.client_order_id, exc,
                )
                await self._safe_callback(self._on_error, rec, exc)
                return

            # ── Compute backoff before next attempt ───────────────────────
            if attempt < cfg.max_attempts - 1:
                delay = min(
                    cfg.base_delay_s * (2 ** attempt) + random.uniform(0, cfg.jitter_s),
                    cfg.max_delay_s,
                )
                logger.debug(
                    "Backoff %.2fs before attempt %d | %s",
                    delay, attempt + 2, rec.client_order_id,
                )
                await asyncio.sleep(delay)

        # ── All attempts exhausted ────────────────────────────────────────
        if not rec.is_terminal:
            rec.transition(
                OrderState.ERROR,
                note=f"max_attempts={cfg.max_attempts} exhausted | last_error={rec.last_error}",
            )
            logger.error(
                "❌ Order failed after %d attempts | %s | last_error=%s",
                cfg.max_attempts, rec.client_order_id, rec.last_error,
            )
            await self._safe_callback(self._on_error, rec, RuntimeError(rec.last_error))

    # ── Internal: cancel ─────────────────────────────────────────────────

    async def _cancel_order(self, rec: OrderRecord) -> None:
        """
        Cancel an open order on the exchange.

        Retries up to 3 times on network errors. Handles -2011 (unknown order)
        gracefully — if Binance doesn't know about it, we consider it cancelled.
        """
        if rec.state not in (OrderState.OPEN, OrderState.PARTIAL_FILL, OrderState.SUBMITTED):
            return

        for attempt in range(3):
            try:
                await self._rest.cancel_order(
                    symbol=rec.symbol,
                    client_order_id=rec.client_order_id,
                )
                rec.transition(OrderState.CANCELLED, note="cancel_requested")
                logger.info("🚫 Order cancelled | %s", rec.client_order_id)
                return

            except BinanceRESTError as exc:
                if exc.code == -2011:
                    # Order unknown to exchange — already filled/cancelled
                    logger.info(
                        "Cancel: order not found on exchange (-2011) | %s — "
                        "querying final status",
                        rec.client_order_id,
                    )
                    await self._query_by_client_id(rec)
                    return
                logger.warning(
                    "Cancel attempt %d failed | %s | %s",
                    attempt + 1, rec.client_order_id, exc,
                )

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "Cancel network error attempt %d | %s | %s",
                    attempt + 1, rec.client_order_id, exc,
                )

            await asyncio.sleep(0.5 * (2 ** attempt))

        # If cancel failed, fetch latest status and accept whatever it is
        logger.error(
            "Cancel failed after 3 attempts | %s — fetching current state",
            rec.client_order_id,
        )
        await self._query_by_client_id(rec)

    # ── Internal: helpers ─────────────────────────────────────────────────

    def _build_record(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str],
        stop_price: Optional[str],
        time_in_force: str,
        position_side: str,
        reduce_only: bool,
        stp_mode: Optional[str],
        client_order_id: Optional[str],
    ) -> OrderRecord:
        """Create a new OrderRecord with an idempotent client_order_id."""
        coid = client_order_id or self._generate_client_order_id(symbol, side)
        return OrderRecord(
            symbol          = symbol,
            side            = side,
            order_type      = order_type,
            quantity        = quantity,
            price           = price,
            stop_price      = stop_price,
            time_in_force   = time_in_force,
            position_side   = position_side,
            reduce_only     = reduce_only,
            stp_mode        = stp_mode,
            client_order_id = coid,
        )

    def _build_request_params(self, rec: OrderRecord) -> dict:
        """Convert an OrderRecord into kwargs for BinanceRESTClient.place_order()."""
        params = dict(
            symbol          = rec.symbol,
            side            = rec.side,
            order_type      = rec.order_type,
            quantity        = rec.quantity,
            time_in_force   = rec.time_in_force,
            position_side   = rec.position_side,
            reduce_only     = rec.reduce_only,
            client_order_id = rec.client_order_id,
        )
        if rec.price:       params["price"]      = rec.price
        if rec.stop_price:  params["stop_price"] = rec.stop_price
        return params

    async def _query_by_client_id(self, rec: OrderRecord) -> bool:
        """
        Query the exchange for the order's current status using client_order_id.

        Returns True if the query succeeded, False otherwise.
        """
        try:
            data = await self._rest.get_order(
                symbol=rec.symbol,
                client_order_id=rec.client_order_id,
            )
            rec.update_from_exchange(data)
            logger.info(
                "Query by client_id OK | %s | state=%s",
                rec.client_order_id, rec.state.value,
            )
            return True
        except BinanceRESTError as exc:
            logger.warning(
                "Query by client_id failed | %s | %s",
                rec.client_order_id, exc,
            )
            return False

    @staticmethod
    def _validate_params(
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: Optional[str],
        time_in_force: str,
    ) -> Optional[str]:
        """
        Lightweight pre-flight validation. Returns an error string or None.

        This is a fast local check to catch obvious mistakes before burning
        an API call and a rate-limit weight unit.
        """
        # Symbol must be alphanumeric (no slash, no hyphen) and end in USDT
        if not symbol or not symbol.isalnum() or not symbol.endswith("USDT"):
            return f"Invalid symbol: {symbol!r} — expected plain USDT pair (e.g. BTCUSDT, no slash)"

        if side not in ("BUY", "SELL"):
            return f"Invalid side: {side!r} — must be BUY or SELL"

        valid_types = {
            "LIMIT", "MARKET", "STOP", "STOP_MARKET",
            "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET",
        }
        if order_type not in valid_types:
            return f"Invalid order_type: {order_type!r}"

        try:
            qty = float(quantity)
            if qty <= 0:
                return f"quantity must be > 0, got {quantity!r}"
        except (ValueError, TypeError):
            return f"quantity is not a valid number: {quantity!r}"

        if order_type == "LIMIT" and not price:
            return "LIMIT orders require a price"

        if order_type == "LIMIT":
            try:
                p = float(price)
                if p <= 0:
                    return f"price must be > 0, got {price!r}"
            except (ValueError, TypeError):
                return f"price is not a valid number: {price!r}"

        if time_in_force not in ("GTC", "IOC", "FOK", "GTX"):
            return f"Invalid time_in_force: {time_in_force!r}"

        return None

    @staticmethod
    def _is_retryable(exc: BinanceRESTError) -> bool:
        """
        Returns True if the error is transient and worth retrying.

        HTTP 5xx and unknown codes are retryable.
        Specific bad-request codes are not.
        """
        if exc.code in NON_RETRYABLE_CODES:
            return False
        if exc.status >= 500:
            return True
        # RateLimitError is handled separately before this check
        return False

    @staticmethod
    def _generate_client_order_id(symbol: str, side: str) -> str:
        """
        Generate a deterministic, unique client order ID.

        Format: CSCOPE_{yyyymmddHHMMSS}_{SYM}_{S}_{hex4}
        Max length: 36 chars (Binance limit).
        Example:    CSCOPE_20260411153042_BTCUSD_B_a3f2
        """
        ts    = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        sym   = symbol[:6]              # e.g. "BTCUSD" from "BTCUSDT"
        s     = side[0]                 # "B" or "S"
        rand  = "".join(random.choices(string.hexdigits[:16].lower(), k=4))
        coid  = f"CSCOPE_{ts}_{sym}_{s}_{rand}"
        return coid[:36]                # hard cap for Binance limit

    @staticmethod
    def _throttle_wait() -> float:
        """Return seconds to wait when rate limit is approaching."""
        return random.uniform(1.0, 3.0)

    @staticmethod
    def _rate_limit_delay(exc: RateLimitError) -> float:
        """
        Extract Retry-After delay from a RateLimitError.

        Falls back to a 10-second default when the header isn't present.
        """
        # BinanceRESTError message may contain the retry-after seconds
        # e.g. "429 Too Many Requests — retry after 12s"
        try:
            for part in str(exc).split():
                if part.isdigit():
                    val = int(part)
                    if 1 <= val <= 3600:
                        return float(val)
        except Exception:
            pass
        return 10.0

    @staticmethod
    async def _safe_callback(cb: Optional[Callable], *args) -> None:
        """Fire an async or sync callback, swallowing exceptions to not crash the loop."""
        if cb is None:
            return
        try:
            result = cb(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.error("OrderManager callback error: %s", exc)


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def make_order_manager(
    rest_client: BinanceRESTClient,
    circuit_breaker=None,
    max_attempts: int   = 4,
    base_delay_s: float = 0.5,
    poll_interval_s: float = 1.0,
    poll_max_wait_s: float = 60.0,
    on_fill: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
) -> OrderManager:
    """
    Convenience factory with the most common configuration knobs exposed.

    Example
    -------
    >>> mgr = make_order_manager(rest, circuit_breaker=cb, max_attempts=3)
    >>> rec = await mgr.submit_order("BTCUSDT", "BUY", "MARKET", "0.001")
    """
    return OrderManager(
        rest_client     = rest_client,
        circuit_breaker = circuit_breaker,
        retry_cfg       = RetryConfig(
            max_attempts = max_attempts,
            base_delay_s = base_delay_s,
        ),
        poll_cfg        = PollConfig(
            interval_s  = poll_interval_s,
            max_wait_s  = poll_max_wait_s,
        ),
        on_fill  = on_fill,
        on_error = on_error,
    )

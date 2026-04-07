"""
CoinScopeAI Paper Trading — Order Manager & Position Tracker
================================================================
Manages the full order lifecycle: validation → submission → tracking → fill.
Tracks all open positions with real-time P&L and margin usage.
Every order is logged BEFORE submission to the exchange.
"""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import TradingConfig
from .exchange_client import BinanceFuturesTestnetClient, OrderResult, ExchangeError
from .safety import KillSwitch, OrderRequest, RejectionReason, SafetyGate

logger = logging.getLogger("coinscopeai.paper_trading.orders")


class OrderStatus(Enum):
    PENDING_VALIDATION = "pending_validation"
    REJECTED_SAFETY = "rejected_safety"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass
class ManagedOrder:
    """An order tracked through its full lifecycle."""
    internal_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float
    leverage: int
    stop_loss: float = 0.0
    take_profit: float = 0.0
    reduce_only: bool = False
    signal_confidence: float = 0.0
    signal_edge: float = 0.0

    # Lifecycle
    status: OrderStatus = OrderStatus.PENDING_VALIDATION
    exchange_order_id: int = 0
    exchange_client_order_id: str = ""
    avg_fill_price: float = 0.0
    filled_qty: float = 0.0
    rejection_reason: str = ""

    # Timestamps
    created_at: float = 0.0
    submitted_at: float = 0.0
    filled_at: float = 0.0
    cancelled_at: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "internal_id": self.internal_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reduce_only": self.reduce_only,
            "signal_confidence": self.signal_confidence,
            "signal_edge": self.signal_edge,
            "status": self.status.value,
            "exchange_order_id": self.exchange_order_id,
            "avg_fill_price": self.avg_fill_price,
            "filled_qty": self.filled_qty,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
        }


@dataclass
class TrackedPosition:
    """An open position being tracked."""
    symbol: str
    side: str           # LONG or SHORT
    entry_price: float
    quantity: float
    leverage: int
    stop_loss: float
    take_profit: float
    unrealized_pnl: float = 0.0
    margin_used: float = 0.0
    opened_at: float = 0.0
    order_id: str = ""  # Internal order ID that opened this position

    @property
    def notional_value(self) -> float:
        return self.quantity * self.entry_price

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return self.unrealized_pnl / (self.notional_value / self.leverage)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "leverage": self.leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "unrealized_pnl": self.unrealized_pnl,
            "pnl_pct": self.pnl_pct,
            "margin_used": self.margin_used,
            "opened_at": self.opened_at,
            "order_id": self.order_id,
        }


class OrderManager:
    """
    Manages the full order lifecycle with safety gate integration.

    Flow: Signal → OrderRequest → SafetyGate → Exchange → Track → Fill/Cancel
    Every step is logged. No order reaches the exchange without passing safety.
    """

    def __init__(
        self,
        exchange: BinanceFuturesTestnetClient,
        safety: SafetyGate,
        config: TradingConfig,
    ):
        self._exchange = exchange
        self._safety = safety
        self._config = config
        self._lock = threading.Lock()

        # Order tracking
        self._orders: Dict[str, ManagedOrder] = {}
        self._positions: Dict[str, TrackedPosition] = {}

        # Trade journal
        self._trade_journal: List[Dict] = []

        # Callbacks
        self._on_fill: Optional[Callable[[ManagedOrder], None]] = None
        self._on_rejection: Optional[Callable[[ManagedOrder], None]] = None
        self._on_position_close: Optional[Callable[[Dict], None]] = None

    def on_fill(self, callback: Callable[[ManagedOrder], None]):
        self._on_fill = callback

    def on_rejection(self, callback: Callable[[ManagedOrder], None]):
        self._on_rejection = callback

    def on_position_close(self, callback: Callable[[Dict], None]):
        self._on_position_close = callback

    @property
    def positions(self) -> Dict[str, TrackedPosition]:
        with self._lock:
            return dict(self._positions)

    @property
    def open_orders(self) -> List[ManagedOrder]:
        with self._lock:
            return [
                o for o in self._orders.values()
                if o.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)
            ]

    @property
    def trade_journal(self) -> List[Dict]:
        return list(self._trade_journal)

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = 0.0,
        order_type: str = "LIMIT",
        leverage: int = 3,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        reduce_only: bool = False,
        signal_confidence: float = 0.0,
        signal_edge: float = 0.0,
    ) -> Tuple[bool, ManagedOrder]:
        """
        Submit an order through the safety gate to the exchange.

        Returns:
            (success, managed_order)
        """
        internal_id = f"CSA-{uuid.uuid4().hex[:12]}"

        order = ManagedOrder(
            internal_id=internal_id,
            symbol=symbol,
            side=side.upper(),
            order_type=order_type.upper(),
            quantity=quantity,
            price=price,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reduce_only=reduce_only,
            signal_confidence=signal_confidence,
            signal_edge=signal_edge,
            created_at=time.time(),
        )

        # ── Step 1: Log BEFORE anything else ──────────────────
        logger.info(
            "ORDER REQUEST: id=%s %s %s %s qty=%.6f price=%.2f lev=%dx conf=%.3f",
            internal_id, symbol, side, order_type, quantity, price,
            leverage, signal_confidence,
        )

        # ── Step 2: Safety Gate Validation ────────────────────
        safety_request = OrderRequest(
            symbol=symbol,
            side=side.upper(),
            order_type=order_type.upper(),
            quantity=quantity,
            price=price if price > 0 else self._get_current_price(symbol),
            leverage=leverage,
            reduce_only=reduce_only,
            stop_loss=stop_loss,
            take_profit=take_profit,
            signal_confidence=signal_confidence,
            signal_edge=signal_edge,
        )

        approved, reason, message = self._safety.validate_order(safety_request)

        if not approved:
            order.status = OrderStatus.REJECTED_SAFETY
            order.rejection_reason = f"{reason.value}: {message}"
            with self._lock:
                self._orders[internal_id] = order
            logger.warning("ORDER REJECTED: id=%s reason=%s", internal_id, message)
            if self._on_rejection:
                self._on_rejection(order)
            return False, order

        # ── Step 3: Set leverage on exchange ──────────────────
        try:
            self._exchange.set_leverage(symbol, leverage)
        except ExchangeError as e:
            logger.warning("Failed to set leverage for %s: %s", symbol, e)

        # ── Step 4: Submit to exchange ────────────────────────
        try:
            result = self._exchange.place_order(
                symbol=symbol,
                side=side.upper(),
                order_type=order_type.upper(),
                quantity=quantity,
                price=price if price > 0 and order_type.upper() == "LIMIT" else None,
                reduce_only=reduce_only,
                client_order_id=internal_id,
                time_in_force="GTC" if order_type.upper() == "LIMIT" else None,
            )

            order.status = OrderStatus.SUBMITTED
            order.exchange_order_id = result.order_id
            order.exchange_client_order_id = result.client_order_id
            order.submitted_at = time.time()

            # If market order, it's likely already filled
            if result.status == "FILLED":
                order.status = OrderStatus.FILLED
                order.avg_fill_price = result.avg_price
                order.filled_qty = result.executed_qty
                order.filled_at = time.time()
                self._process_fill(order)
            elif result.status == "PARTIALLY_FILLED":
                order.status = OrderStatus.PARTIALLY_FILLED
                order.avg_fill_price = result.avg_price
                order.filled_qty = result.executed_qty

            with self._lock:
                self._orders[internal_id] = order

            logger.info(
                "ORDER SUBMITTED: id=%s exchange_id=%d status=%s",
                internal_id, result.order_id, result.status,
            )

            return True, order

        except ExchangeError as e:
            order.status = OrderStatus.FAILED
            order.rejection_reason = f"exchange_error: {e}"
            with self._lock:
                self._orders[internal_id] = order
            logger.error("ORDER FAILED: id=%s error=%s", internal_id, e)
            return False, order

    def close_position(
        self,
        symbol: str,
        reason: str = "manual",
    ) -> Tuple[bool, Optional[ManagedOrder]]:
        """Close an open position with a market order."""
        with self._lock:
            position = self._positions.get(symbol)

        if not position:
            logger.warning("No position to close for %s", symbol)
            return False, None

        # Determine closing side
        close_side = "SELL" if position.side == "LONG" else "BUY"

        return self.submit_order(
            symbol=symbol,
            side=close_side,
            quantity=position.quantity,
            order_type="MARKET",
            leverage=position.leverage,
            reduce_only=True,
        )

    def close_all_positions(self, reason: str = "kill_switch") -> List[ManagedOrder]:
        """Close all open positions. Used by kill switch."""
        results = []
        with self._lock:
            symbols = list(self._positions.keys())

        for symbol in symbols:
            success, order = self.close_position(symbol, reason)
            if order:
                results.append(order)

        return results

    def handle_order_update(self, exchange_order_id: int, status: str,
                            avg_price: float, filled_qty: float):
        """Handle an order update from WebSocket."""
        with self._lock:
            order = None
            for o in self._orders.values():
                if o.exchange_order_id == exchange_order_id:
                    order = o
                    break

            if not order:
                logger.warning("Unknown order update: exchange_id=%d", exchange_order_id)
                return

            if status == "FILLED":
                order.status = OrderStatus.FILLED
                order.avg_fill_price = avg_price
                order.filled_qty = filled_qty
                order.filled_at = time.time()
            elif status == "PARTIALLY_FILLED":
                order.status = OrderStatus.PARTIALLY_FILLED
                order.avg_fill_price = avg_price
                order.filled_qty = filled_qty
            elif status in ("CANCELED", "CANCELLED"):
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = time.time()
            elif status == "EXPIRED":
                order.status = OrderStatus.EXPIRED
                order.cancelled_at = time.time()

        if status == "FILLED":
            self._process_fill(order)

    def _process_fill(self, order: ManagedOrder):
        """Process a filled order — update positions and journal."""
        with self._lock:
            existing = self._positions.get(order.symbol)

            if order.reduce_only and existing:
                # Closing a position
                trade_record = {
                    "symbol": order.symbol,
                    "side": existing.side,
                    "entry_price": existing.entry_price,
                    "exit_price": order.avg_fill_price,
                    "quantity": order.filled_qty,
                    "leverage": existing.leverage,
                    "pnl": self._calc_pnl(
                        existing.side, existing.entry_price,
                        order.avg_fill_price, order.filled_qty,
                    ),
                    "opened_at": existing.opened_at,
                    "closed_at": time.time(),
                    "order_id": order.internal_id,
                    "stop_loss": existing.stop_loss,
                    "take_profit": existing.take_profit,
                }

                pnl_pct = trade_record["pnl"] / (existing.notional_value / existing.leverage)
                trade_record["pnl_pct"] = pnl_pct
                self._trade_journal.append(trade_record)

                # Update safety gate
                self._safety.record_trade_result(pnl_pct)
                self._safety.update_daily_pnl(
                    self._safety.state.daily_pnl + trade_record["pnl"]
                )

                del self._positions[order.symbol]

                logger.info(
                    "POSITION CLOSED: %s %s entry=%.2f exit=%.2f pnl=%.2f (%.2f%%)",
                    order.symbol, existing.side, existing.entry_price,
                    order.avg_fill_price, trade_record["pnl"], pnl_pct * 100,
                )

                if self._on_position_close:
                    self._on_position_close(trade_record)

            elif not order.reduce_only:
                # Opening a new position
                side = "LONG" if order.side == "BUY" else "SHORT"
                position = TrackedPosition(
                    symbol=order.symbol,
                    side=side,
                    entry_price=order.avg_fill_price,
                    quantity=order.filled_qty,
                    leverage=order.leverage,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    opened_at=time.time(),
                    order_id=order.internal_id,
                )
                self._positions[order.symbol] = position

                # Update safety gate positions
                pos_dict = {s: p.to_dict() for s, p in self._positions.items()}
                self._safety.update_positions(pos_dict)

                logger.info(
                    "POSITION OPENED: %s %s entry=%.2f qty=%.6f lev=%dx SL=%.2f TP=%.2f",
                    order.symbol, side, order.avg_fill_price, order.filled_qty,
                    order.leverage, order.stop_loss, order.take_profit,
                )

                if self._on_fill:
                    self._on_fill(order)

    def _calc_pnl(self, side: str, entry: float, exit_price: float, qty: float) -> float:
        """Calculate P&L for a closed position."""
        if side == "LONG":
            return (exit_price - entry) * qty
        else:
            return (entry - exit_price) * qty

    def _get_current_price(self, symbol: str) -> float:
        """Get current price for safety validation."""
        try:
            return self._exchange.get_ticker_price(symbol)
        except Exception:
            return 0.0

    def check_stop_loss_take_profit(self, symbol: str, current_price: float):
        """Check if any position's SL/TP has been hit."""
        with self._lock:
            position = self._positions.get(symbol)

        if not position:
            return

        triggered = False
        reason = ""

        if position.side == "LONG":
            if position.stop_loss > 0 and current_price <= position.stop_loss:
                triggered = True
                reason = "stop_loss"
            elif position.take_profit > 0 and current_price >= position.take_profit:
                triggered = True
                reason = "take_profit"
        else:  # SHORT
            if position.stop_loss > 0 and current_price >= position.stop_loss:
                triggered = True
                reason = "stop_loss"
            elif position.take_profit > 0 and current_price <= position.take_profit:
                triggered = True
                reason = "take_profit"

        if triggered:
            logger.info(
                "SL/TP TRIGGERED: %s %s at %.2f (reason=%s)",
                symbol, position.side, current_price, reason,
            )
            self.close_position(symbol, reason)

    def update_unrealized_pnl(self, symbol: str, current_price: float):
        """Update unrealized P&L for a position."""
        with self._lock:
            position = self._positions.get(symbol)
            if not position:
                return
            position.unrealized_pnl = self._calc_pnl(
                position.side, position.entry_price, current_price, position.quantity,
            )

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary."""
        with self._lock:
            total_unrealized = sum(p.unrealized_pnl for p in self._positions.values())
            total_margin = sum(
                p.notional_value / p.leverage for p in self._positions.values()
            )
            total_realized = sum(t.get("pnl", 0) for t in self._trade_journal)

            return {
                "open_positions": len(self._positions),
                "positions": {s: p.to_dict() for s, p in self._positions.items()},
                "total_unrealized_pnl": total_unrealized,
                "total_realized_pnl": total_realized,
                "total_margin_used": total_margin,
                "total_trades": len(self._trade_journal),
                "winning_trades": sum(1 for t in self._trade_journal if t.get("pnl", 0) > 0),
                "losing_trades": sum(1 for t in self._trade_journal if t.get("pnl", 0) <= 0),
            }

    def cancel_stale_orders(self, max_age_seconds: int = 300):
        """Cancel orders that have been open too long."""
        now = time.time()
        with self._lock:
            stale = [
                o for o in self._orders.values()
                if o.status == OrderStatus.SUBMITTED
                and o.order_type == "LIMIT"
                and (now - o.submitted_at) > max_age_seconds
            ]

        for order in stale:
            try:
                self._exchange.cancel_order(order.symbol, order.exchange_order_id)
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = now
                logger.info("Cancelled stale order: %s %s", order.internal_id, order.symbol)
            except Exception as e:
                logger.error("Failed to cancel stale order %s: %s", order.internal_id, e)

"""
CoinScopeAI Paper Trading — Execution Safety Layer
=====================================================
Non-bypassable safety checks that gate every order before submission.
The kill switch works independently of all other components.

DESIGN PRINCIPLE: Every check is fail-closed. If any check cannot
determine safety, the order is REJECTED. There is no "override" mode.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import (
    HARDCODED_MAX_CONCURRENT_POSITIONS,
    HARDCODED_MAX_DAILY_LOSS_PCT,
    HARDCODED_MAX_DRAWDOWN_PCT,
    HARDCODED_MAX_LEVERAGE,
    HARDCODED_MAX_POSITION_SIZE_PCT,
    TradingConfig,
)

logger = logging.getLogger("coinscopeai.paper_trading.safety")


class RejectionReason(Enum):
    """Why an order was rejected by the safety layer."""
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    DAILY_LOSS_LIMIT = "daily_loss_limit_exceeded"
    MAX_DRAWDOWN = "max_drawdown_exceeded"
    MAX_POSITIONS = "max_concurrent_positions_exceeded"
    POSITION_TOO_LARGE = "position_size_exceeds_limit"
    LEVERAGE_TOO_HIGH = "leverage_exceeds_limit"
    CONSECUTIVE_LOSSES = "consecutive_loss_limit_hit"
    COOLDOWN_ACTIVE = "loss_cooldown_active"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INVALID_ORDER = "invalid_order_parameters"


@dataclass
class OrderRequest:
    """An order that must pass safety checks before submission."""
    symbol: str
    side: str           # BUY or SELL
    order_type: str     # MARKET, LIMIT
    quantity: float
    price: float        # 0 for market orders
    leverage: int
    reduce_only: bool = False
    stop_loss: float = 0.0
    take_profit: float = 0.0
    signal_confidence: float = 0.0
    signal_edge: float = 0.0


@dataclass
class SafetyState:
    """Current state tracked by the safety layer."""
    initial_equity: float = 10000.0
    current_equity: float = 10000.0
    peak_equity: float = 10000.0
    daily_pnl: float = 0.0
    daily_pnl_reset_time: float = 0.0
    open_positions: Dict[str, Dict] = field(default_factory=dict)
    consecutive_losses: int = 0
    last_loss_time: float = 0.0
    total_orders_submitted: int = 0
    total_orders_rejected: int = 0
    rejection_log: List[Dict] = field(default_factory=list)


class KillSwitch:
    """
    Independent kill switch that can flatten all positions.
    Works even if the main trading engine is unresponsive.

    Uses a file-based flag so it persists across restarts
    and can be triggered externally (e.g., by a cron job or CLI).
    """

    KILL_FILE = "/tmp/coinscopeai_kill_switch.flag"

    def __init__(self):
        self._active = False
        self._lock = threading.Lock()
        self._reason = ""
        self._activated_at = 0.0

        # Check for persistent kill flag on init
        if Path(self.KILL_FILE).exists():
            self._active = True
            self._reason = "persistent_kill_flag"
            self._activated_at = Path(self.KILL_FILE).stat().st_mtime
            logger.warning("Kill switch is ACTIVE (persistent flag found)")

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    def activate(self, reason: str = "manual"):
        """Activate the kill switch. Cannot be deactivated programmatically."""
        with self._lock:
            self._active = True
            self._reason = reason
            self._activated_at = time.time()

        # Write persistent flag
        try:
            Path(self.KILL_FILE).write_text(json.dumps({
                "reason": reason,
                "activated_at": self._activated_at,
                "pid": os.getpid(),
            }))
        except Exception as e:
            logger.error("Failed to write kill flag: %s", e)

        logger.critical(
            "KILL SWITCH ACTIVATED: reason=%s. "
            "All trading halted. Manual intervention required to restart.",
            reason,
        )

    def deactivate(self):
        """
        Deactivate the kill switch.
        This should ONLY be called by the CLI after human review.
        """
        with self._lock:
            self._active = False
            self._reason = ""
            self._activated_at = 0.0

        try:
            Path(self.KILL_FILE).unlink(missing_ok=True)
        except Exception:
            pass

        logger.warning("Kill switch deactivated by operator")

    def status(self) -> Dict:
        with self._lock:
            return {
                "active": self._active,
                "reason": self._reason,
                "activated_at": self._activated_at,
            }


class SafetyGate:
    """
    The safety gate that every order must pass through.
    Checks are layered: hardcoded limits → configurable limits → state checks.
    All checks are fail-closed.
    """

    def __init__(self, config: TradingConfig, kill_switch: Optional[KillSwitch] = None):
        self._config = config
        self._kill_switch = kill_switch or KillSwitch()
        self._state = SafetyState()
        self._lock = threading.Lock()

    @property
    def kill_switch(self) -> KillSwitch:
        return self._kill_switch

    @property
    def state(self) -> SafetyState:
        return self._state

    def update_equity(self, equity: float):
        """Update current equity from exchange."""
        with self._lock:
            self._state.current_equity = equity
            self._state.peak_equity = max(self._state.peak_equity, equity)

    def update_daily_pnl(self, pnl: float):
        """Update daily P&L."""
        with self._lock:
            self._state.daily_pnl = pnl

    def reset_daily_pnl(self):
        """Reset daily P&L counter (called at day boundary)."""
        with self._lock:
            self._state.daily_pnl = 0.0
            self._state.daily_pnl_reset_time = time.time()

    def record_trade_result(self, pnl_pct: float):
        """Record a trade result for consecutive loss tracking."""
        with self._lock:
            if pnl_pct < 0:
                self._state.consecutive_losses += 1
                self._state.last_loss_time = time.time()
            else:
                self._state.consecutive_losses = 0

    def update_positions(self, positions: Dict[str, Dict]):
        """Update tracked open positions."""
        with self._lock:
            self._state.open_positions = positions

    def validate_order(self, order: OrderRequest) -> Tuple[bool, Optional[RejectionReason], str]:
        """
        Validate an order against all safety checks.

        Returns:
            (approved, rejection_reason, message)
        """
        with self._lock:
            return self._validate_locked(order)

    def _validate_locked(self, order: OrderRequest) -> Tuple[bool, Optional[RejectionReason], str]:
        """Internal validation — must be called under lock."""

        # ── Layer 1: Kill Switch (highest priority) ───────────
        if self._kill_switch.is_active:
            return self._reject(
                order, RejectionReason.KILL_SWITCH_ACTIVE,
                f"Kill switch active: {self._kill_switch.reason}"
            )

        # Reduce-only orders always pass safety (they reduce risk)
        if order.reduce_only:
            self._state.total_orders_submitted += 1
            return True, None, "approved_reduce_only"

        # ── Layer 2: Hardcoded Limits (non-configurable) ──────

        # Leverage check
        if order.leverage > HARDCODED_MAX_LEVERAGE:
            return self._reject(
                order, RejectionReason.LEVERAGE_TOO_HIGH,
                f"Leverage {order.leverage}x > hardcoded max {HARDCODED_MAX_LEVERAGE}x"
            )

        # Position size check (% of equity)
        if self._state.current_equity > 0:
            position_value = order.quantity * order.price * order.leverage
            position_pct = position_value / self._state.current_equity
            if position_pct > HARDCODED_MAX_POSITION_SIZE_PCT:
                return self._reject(
                    order, RejectionReason.POSITION_TOO_LARGE,
                    f"Position {position_pct:.1%} > hardcoded max {HARDCODED_MAX_POSITION_SIZE_PCT:.0%}"
                )

        # Max concurrent positions
        n_positions = len(self._state.open_positions)
        if n_positions >= HARDCODED_MAX_CONCURRENT_POSITIONS:
            return self._reject(
                order, RejectionReason.MAX_POSITIONS,
                f"Positions {n_positions} >= hardcoded max {HARDCODED_MAX_CONCURRENT_POSITIONS}"
            )

        # Daily loss (hardcoded)
        if self._state.initial_equity > 0:
            daily_loss_pct = abs(min(self._state.daily_pnl, 0)) / self._state.initial_equity
            if daily_loss_pct >= HARDCODED_MAX_DAILY_LOSS_PCT:
                self._kill_switch.activate(f"hardcoded_daily_loss_{daily_loss_pct:.1%}")
                return self._reject(
                    order, RejectionReason.DAILY_LOSS_LIMIT,
                    f"Daily loss {daily_loss_pct:.1%} >= hardcoded max {HARDCODED_MAX_DAILY_LOSS_PCT:.0%}"
                )

        # Max drawdown (hardcoded)
        if self._state.peak_equity > 0:
            drawdown = (self._state.peak_equity - self._state.current_equity) / self._state.peak_equity
            if drawdown >= HARDCODED_MAX_DRAWDOWN_PCT:
                self._kill_switch.activate(f"hardcoded_max_drawdown_{drawdown:.1%}")
                return self._reject(
                    order, RejectionReason.MAX_DRAWDOWN,
                    f"Drawdown {drawdown:.1%} >= hardcoded max {HARDCODED_MAX_DRAWDOWN_PCT:.0%}"
                )

        # ── Layer 3: Configurable Limits ──────────────────────

        # Configurable daily loss (stricter than hardcoded)
        if self._state.initial_equity > 0:
            daily_loss_pct = abs(min(self._state.daily_pnl, 0)) / self._state.initial_equity
            if daily_loss_pct >= self._config.max_daily_loss_pct:
                return self._reject(
                    order, RejectionReason.DAILY_LOSS_LIMIT,
                    f"Daily loss {daily_loss_pct:.1%} >= config max {self._config.max_daily_loss_pct:.0%}"
                )

        # Configurable max drawdown
        if self._state.peak_equity > 0:
            drawdown = (self._state.peak_equity - self._state.current_equity) / self._state.peak_equity
            if drawdown >= self._config.max_drawdown_pct:
                return self._reject(
                    order, RejectionReason.MAX_DRAWDOWN,
                    f"Drawdown {drawdown:.1%} >= config max {self._config.max_drawdown_pct:.0%}"
                )

        # Configurable max positions
        if n_positions >= self._config.max_concurrent_positions:
            return self._reject(
                order, RejectionReason.MAX_POSITIONS,
                f"Positions {n_positions} >= config max {self._config.max_concurrent_positions}"
            )

        # Configurable position size
        if self._state.current_equity > 0:
            position_value = order.quantity * order.price * order.leverage
            position_pct = position_value / self._state.current_equity
            if position_pct > self._config.max_position_size_pct:
                return self._reject(
                    order, RejectionReason.POSITION_TOO_LARGE,
                    f"Position {position_pct:.1%} > config max {self._config.max_position_size_pct:.0%}"
                )

        # Configurable leverage
        if order.leverage > self._config.leverage:
            return self._reject(
                order, RejectionReason.LEVERAGE_TOO_HIGH,
                f"Leverage {order.leverage}x > config max {self._config.leverage}x"
            )

        # ── Layer 4: State Checks ─────────────────────────────

        # Consecutive losses
        if self._state.consecutive_losses >= self._config.max_consecutive_losses:
            return self._reject(
                order, RejectionReason.CONSECUTIVE_LOSSES,
                f"Consecutive losses {self._state.consecutive_losses} >= max {self._config.max_consecutive_losses}"
            )

        # Loss cooldown
        if self._state.last_loss_time > 0:
            cooldown_end = self._state.last_loss_time + (self._config.cooldown_after_loss_minutes * 60)
            if time.time() < cooldown_end:
                remaining = cooldown_end - time.time()
                return self._reject(
                    order, RejectionReason.COOLDOWN_ACTIVE,
                    f"Loss cooldown active, {remaining:.0f}s remaining"
                )

        # ── All checks passed ─────────────────────────────────
        self._state.total_orders_submitted += 1
        return True, None, "approved"

    def _reject(self, order: OrderRequest, reason: RejectionReason,
                message: str) -> Tuple[bool, RejectionReason, str]:
        """Record a rejection."""
        self._state.total_orders_rejected += 1
        self._state.rejection_log.append({
            "time": time.time(),
            "symbol": order.symbol,
            "side": order.side,
            "reason": reason.value,
            "message": message,
        })

        # Keep only last 100 rejections
        if len(self._state.rejection_log) > 100:
            self._state.rejection_log = self._state.rejection_log[-100:]

        logger.warning("ORDER REJECTED: %s — %s", reason.value, message)
        return False, reason, message

    def get_status(self) -> Dict:
        """Get current safety status."""
        with self._lock:
            drawdown = 0.0
            if self._state.peak_equity > 0:
                drawdown = (self._state.peak_equity - self._state.current_equity) / self._state.peak_equity

            daily_loss_pct = 0.0
            if self._state.initial_equity > 0:
                daily_loss_pct = abs(min(self._state.daily_pnl, 0)) / self._state.initial_equity

            return {
                "kill_switch": self._kill_switch.status(),
                "equity": self._state.current_equity,
                "peak_equity": self._state.peak_equity,
                "drawdown_pct": drawdown,
                "daily_pnl": self._state.daily_pnl,
                "daily_loss_pct": daily_loss_pct,
                "open_positions": len(self._state.open_positions),
                "consecutive_losses": self._state.consecutive_losses,
                "total_orders_submitted": self._state.total_orders_submitted,
                "total_orders_rejected": self._state.total_orders_rejected,
                "recent_rejections": self._state.rejection_log[-5:],
            }

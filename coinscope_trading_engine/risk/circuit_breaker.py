"""
circuit_breaker.py — Trading Circuit Breaker
=============================================
Monitors real-time risk metrics and halts all trading activity when
configurable thresholds are breached.

Triggers
--------
  1. Daily loss cap       — daily_loss_pct ≤ -max_daily_loss_pct
  2. Drawdown cap         — portfolio drawdown ≥ max_drawdown_pct
  3. Consecutive losses   — ≥ max_consecutive_losses trades in a row
  4. Rapid loss           — loss > rapid_loss_pct in rapid_loss_window_s
  5. Manual trip          — forced halt via trip(reason)

States
------
  CLOSED  — trading allowed (circuit is closed = current flows)
  OPEN    — trading halted  (circuit is open   = no current)
  COOLDOWN — cooling down, will auto-reset after reset_after_s

On OPEN:
  * Sends alert via provided callback
  * Records trip reason, timestamp, and metrics
  * Auto-resets after reset_after_s if configured

Usage
-----
    cb = CircuitBreaker(
        on_trip=lambda r, pct: asyncio.create_task(notifier.send_circuit_breaker(r, pct))
    )

    # In the main scan loop:
    cb.check(daily_loss_pct=-2.1, drawdown_pct=3.5, consecutive_losses=3)
    if cb.is_open:
        logger.warning("Circuit open — skipping scan cycle")
        continue
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class BreakerState(str, Enum):
    CLOSED   = "CLOSED"     # trading allowed
    OPEN     = "OPEN"       # trading halted
    COOLDOWN = "COOLDOWN"   # recently tripped, cooling down


@dataclass
class TripEvent:
    """Records details of a circuit breaker activation."""
    reason:           str
    daily_loss_pct:   float
    drawdown_pct:     float
    consecutive_losses: int
    tripped_at:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reset_at:         Optional[datetime] = None

    def __repr__(self) -> str:
        return (
            f"<TripEvent reason={self.reason!r} "
            f"loss={self.daily_loss_pct:.2f}% "
            f"at={self.tripped_at.strftime('%H:%M:%S')}>"
        )


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Monitors risk metrics and halts trading when limits are exceeded.

    Parameters
    ----------
    on_trip         : Async callback(reason, daily_loss_pct) called on trip.
    reset_after_s   : Seconds before auto-reset (0 = manual reset only).
    max_daily_loss  : % daily loss that trips the breaker.
    max_drawdown    : % drawdown that trips the breaker.
    max_consec_loss : Consecutive losing trades before trip.
    rapid_loss_pct  : % loss within rapid_window_s that trips breaker.
    rapid_window_s  : Time window for rapid loss check (seconds).
    """

    def __init__(
        self,
        on_trip:         Optional[Callable] = None,
        reset_after_s:   float = 0,
        max_daily_loss:  Optional[float] = None,
        max_drawdown:    Optional[float] = None,
        max_consec_loss: int = 5,
        rapid_loss_pct:  float = 1.5,
        rapid_window_s:  float = 300.0,
    ) -> None:
        self._on_trip         = on_trip
        self._reset_after_s   = reset_after_s
        self._max_daily_loss  = max_daily_loss  or settings.max_daily_loss_pct
        self._max_drawdown    = max_drawdown    or getattr(settings, "max_drawdown_pct", 10.0)
        self._max_consec_loss = max_consec_loss
        self._rapid_loss_pct  = rapid_loss_pct
        self._rapid_window_s  = rapid_window_s

        self._state        = BreakerState.CLOSED
        self._trip_time:   float = 0.0
        self._trip_history: list[TripEvent] = []

        # Rapid-loss tracking: list of (timestamp, loss_pct) tuples
        self._rapid_log: list[tuple[float, float]] = []

    # ── State checks ─────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        """True if trading is currently halted."""
        self._maybe_auto_reset()
        return self._state == BreakerState.OPEN

    @property
    def is_closed(self) -> bool:
        return not self.is_open

    @property
    def state(self) -> BreakerState:
        self._maybe_auto_reset()
        return self._state

    # ── Check (called each scan cycle) ───────────────────────────────────

    def check(
        self,
        daily_loss_pct:    float = 0.0,
        drawdown_pct:      float = 0.0,
        consecutive_losses: int  = 0,
    ) -> bool:
        """
        Evaluate all trigger conditions.

        Returns True if all checks pass (trading continues),
        False if the breaker was tripped.
        """
        if self._state == BreakerState.OPEN:
            self._maybe_auto_reset()
            return self._state == BreakerState.CLOSED

        reason = None

        # 1. Daily loss cap (loss expressed as negative %)
        if daily_loss_pct <= -abs(self._max_daily_loss):
            reason = (
                f"Daily loss {daily_loss_pct:.2f}% ≤ "
                f"-{self._max_daily_loss}% limit"
            )

        # 2. Drawdown cap
        elif drawdown_pct >= self._max_drawdown:
            reason = (
                f"Drawdown {drawdown_pct:.2f}% ≥ "
                f"{self._max_drawdown}% limit"
            )

        # 3. Consecutive losses
        elif consecutive_losses >= self._max_consec_loss:
            reason = (
                f"{consecutive_losses} consecutive losses ≥ "
                f"{self._max_consec_loss} limit"
            )

        if reason:
            self._trip(
                reason             = reason,
                daily_loss_pct     = daily_loss_pct,
                drawdown_pct       = drawdown_pct,
                consecutive_losses = consecutive_losses,
            )
            return False

        return True

    def record_trade_result(self, pnl_pct: float) -> None:
        """
        Record a trade result for rapid-loss monitoring.

        Call this after every trade closes.
        """
        now = time.monotonic()
        self._rapid_log.append((now, pnl_pct))
        # Prune entries outside the window
        cutoff = now - self._rapid_window_s
        self._rapid_log = [(t, p) for t, p in self._rapid_log if t >= cutoff]

        # Check rapid loss trigger
        window_loss = sum(p for _, p in self._rapid_log if p < 0)
        if abs(window_loss) >= self._rapid_loss_pct:
            self._trip(
                reason             = (
                    f"Rapid loss {window_loss:.2f}% in "
                    f"{self._rapid_window_s:.0f}s window"
                ),
                daily_loss_pct     = window_loss,
                drawdown_pct       = 0.0,
                consecutive_losses = 0,
            )

    # ── Manual controls ──────────────────────────────────────────────────

    def trip(self, reason: str = "Manual halt") -> None:
        """Manually trip the circuit breaker."""
        self._trip(
            reason             = reason,
            daily_loss_pct     = 0.0,
            drawdown_pct       = 0.0,
            consecutive_losses = 0,
        )

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        if self._state == BreakerState.OPEN:
            logger.info("CircuitBreaker manually reset.")
            self._state = BreakerState.CLOSED
        else:
            logger.debug("CircuitBreaker already closed.")

    def reset_daily(self) -> None:
        """Call at start of each trading day to clear daily state."""
        self._rapid_log.clear()
        if self._state == BreakerState.OPEN:
            logger.info("CircuitBreaker daily reset — re-closing.")
            self._state = BreakerState.CLOSED

    # ── Internals ────────────────────────────────────────────────────────

    def _trip(
        self,
        reason:             str,
        daily_loss_pct:     float,
        drawdown_pct:       float,
        consecutive_losses: int,
    ) -> None:
        if self._state == BreakerState.OPEN:
            return   # already open

        self._state     = BreakerState.OPEN
        self._trip_time = time.monotonic()

        event = TripEvent(
            reason             = reason,
            daily_loss_pct     = daily_loss_pct,
            drawdown_pct       = drawdown_pct,
            consecutive_losses = consecutive_losses,
        )
        self._trip_history.append(event)

        logger.error(
            "🛑 CIRCUIT BREAKER TRIPPED | %s | daily_loss=%.2f%% drawdown=%.2f%%",
            reason, daily_loss_pct, drawdown_pct,
        )

        # Fire async callback (don't block)
        if self._on_trip:
            try:
                coro = self._on_trip(reason, daily_loss_pct)
                if asyncio.iscoroutine(coro):
                    asyncio.create_task(coro)
            except Exception as exc:
                logger.error("CircuitBreaker on_trip callback error: %s", exc)

    def _maybe_auto_reset(self) -> None:
        if (
            self._state == BreakerState.OPEN
            and self._reset_after_s > 0
            and time.monotonic() - self._trip_time >= self._reset_after_s
        ):
            logger.info(
                "CircuitBreaker auto-reset after %.0fs cooldown.",
                self._reset_after_s,
            )
            self._state = BreakerState.CLOSED
            if self._trip_history:
                self._trip_history[-1].reset_at = datetime.now(timezone.utc)

    # ── Stats ────────────────────────────────────────────────────────────

    @property
    def trip_count(self) -> int:
        return len(self._trip_history)

    @property
    def last_trip(self) -> Optional[TripEvent]:
        return self._trip_history[-1] if self._trip_history else None

    def status(self) -> dict:
        return {
            "state":        self.state.value,
            "trip_count":   self.trip_count,
            "last_trip":    repr(self.last_trip) if self.last_trip else None,
            "max_daily_loss_pct": self._max_daily_loss,
            "max_drawdown_pct":   self._max_drawdown,
            "max_consec_losses":  self._max_consec_loss,
        }

    def __repr__(self) -> str:
        return (
            f"<CircuitBreaker state={self._state.value} "
            f"trips={self.trip_count}>"
        )

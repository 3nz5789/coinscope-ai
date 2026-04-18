"""
exposure_tracker.py — Portfolio Exposure & P&L Tracker
=======================================================
Tracks open positions, running P&L, daily loss, and total exposure
to enforce risk limits in real time.

Responsibilities
----------------
* Register new positions (long/short, notional, entry)
* Update mark price for open positions and recompute unrealised P&L
* Track realised P&L and daily loss accumulation
* Enforce max_open_positions and max_total_exposure_pct limits
* Provide exposure snapshots for the circuit breaker
* Thread-safe updates via asyncio.Lock

Usage
-----
    tracker = ExposureTracker(balance=10_000)

    tracker.open_position("BTCUSDT", SignalDirection.LONG, qty=0.01, entry=65000)
    tracker.update_price("BTCUSDT", 66000)
    pnl = tracker.unrealised_pnl  # +100 USDT

    tracker.close_position("BTCUSDT", exit_price=64000)
    print(tracker.daily_loss_pct)   # -0.01 → -1.0 %
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from config import settings
from scanner.base_scanner import SignalDirection
from utils.helpers import safe_divide
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------

@dataclass
class Position:
    """A single tracked open position."""
    symbol:     str
    direction:  SignalDirection
    qty:        float
    entry:      float
    notional:   float                    # qty × entry
    mark_price: float = 0.0
    opened_at:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def unrealised_pnl(self) -> float:
        if not self.mark_price:
            return 0.0
        if self.direction == SignalDirection.LONG:
            return (self.mark_price - self.entry) * self.qty
        else:
            return (self.entry - self.mark_price) * self.qty

    @property
    def unrealised_pnl_pct(self) -> float:
        return safe_divide(self.unrealised_pnl, self.notional) * 100

    def __repr__(self) -> str:
        return (
            f"<Position {self.symbol} {self.direction.value} "
            f"qty={self.qty} entry={self.entry:.2f} pnl={self.unrealised_pnl:.2f}>"
        )


# ---------------------------------------------------------------------------
# Exposure Tracker
# ---------------------------------------------------------------------------

class ExposureTracker:
    """
    Tracks portfolio exposure and P&L for all open positions.

    Parameters
    ----------
    balance : Starting account balance (USDT).
    """

    def __init__(self, balance: float) -> None:
        self._balance      = balance
        self._positions: dict[str, Position] = {}
        self._daily_pnl    = 0.0      # accumulated realised + unrealised
        self._realised_pnl = 0.0
        self._lock         = asyncio.Lock()
        self._trade_count  = 0

    # ── Position management ──────────────────────────────────────────────

    async def open_position(
        self,
        symbol:    str,
        direction: SignalDirection,
        qty:       float,
        entry:     float,
    ) -> bool:
        """
        Register a new open position.

        Returns False if adding this position would breach exposure limits.
        """
        async with self._lock:
            if symbol in self._positions:
                logger.warning("Position already open for %s — ignoring.", symbol)
                return False

            if len(self._positions) >= settings.max_open_positions:
                logger.warning(
                    "Max open positions (%d) reached. Cannot open %s.",
                    settings.max_open_positions, symbol,
                )
                return False

            notional = qty * entry
            if self._would_exceed_exposure(notional):
                logger.warning(
                    "Opening %s (%.2f USDT) would exceed max exposure limit.",
                    symbol, notional,
                )
                return False

            pos = Position(
                symbol    = symbol,
                direction = direction,
                qty       = qty,
                entry     = entry,
                notional  = notional,
                mark_price = entry,
            )
            self._positions[symbol] = pos
            logger.info(
                "Position opened: %s %s qty=%.4f entry=%.2f notional=%.2f",
                symbol, direction.value, qty, entry, notional,
            )
            return True

    async def close_position(
        self,
        symbol:     str,
        exit_price: float,
        reason:     str = "",
    ) -> Optional[float]:
        """
        Close an open position and record realised P&L.

        Returns realised P&L or None if position not found.
        """
        async with self._lock:
            pos = self._positions.pop(symbol, None)
            if not pos:
                logger.warning("No open position for %s.", symbol)
                return None

            if pos.direction == SignalDirection.LONG:
                pnl = (exit_price - pos.entry) * pos.qty
            else:
                pnl = (pos.entry - exit_price) * pos.qty

            self._realised_pnl += pnl
            self._daily_pnl    += pnl
            self._trade_count  += 1

            logger.info(
                "Position closed: %s exit=%.2f pnl=%.2f reason=%s",
                symbol, exit_price, pnl, reason or "manual",
            )
            return pnl

    async def update_mark_price(self, symbol: str, price: float) -> None:
        """Update the mark price for an open position."""
        async with self._lock:
            if symbol in self._positions:
                self._positions[symbol].mark_price = price

    async def update_all_prices(self, prices: dict[str, float]) -> None:
        """Bulk-update mark prices from a {symbol: price} dict."""
        async with self._lock:
            for symbol, price in prices.items():
                if symbol in self._positions:
                    self._positions[symbol].mark_price = price

    # ── Exposure metrics ─────────────────────────────────────────────────

    @property
    def open_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    @property
    def position_count(self) -> int:
        return len(self._positions)

    @property
    def total_notional(self) -> float:
        return sum(p.notional for p in self._positions.values())

    @property
    def total_exposure_pct(self) -> float:
        return safe_divide(self.total_notional, self._balance) * 100

    @property
    def unrealised_pnl(self) -> float:
        return sum(p.unrealised_pnl for p in self._positions.values())

    @property
    def realised_pnl(self) -> float:
        return self._realised_pnl

    @property
    def daily_pnl(self) -> float:
        """Realised + unrealised PnL accumulated today."""
        return self._realised_pnl + self.unrealised_pnl

    @property
    def daily_loss_pct(self) -> float:
        """Daily loss as % of balance (negative means loss)."""
        return safe_divide(self.daily_pnl, self._balance) * 100

    @property
    def is_over_exposed(self) -> bool:
        return self.total_exposure_pct > settings.max_total_exposure_pct

    def _would_exceed_exposure(self, new_notional: float) -> bool:
        current = self.total_notional
        max_exp = self._balance * (settings.max_total_exposure_pct / 100)
        return (current + new_notional) > max_exp

    # ── Balance management ───────────────────────────────────────────────

    def update_balance(self, new_balance: float) -> None:
        self._balance = new_balance

    def reset_daily_pnl(self) -> None:
        """Call at start of each trading day."""
        self._realised_pnl = 0.0
        logger.info("Daily PnL reset. trade_count=%d", self._trade_count)

    # ── Snapshot ─────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "balance":          round(self._balance, 2),
            "position_count":   self.position_count,
            "total_notional":   round(self.total_notional, 2),
            "total_exposure_pct": round(self.total_exposure_pct, 2),
            "unrealised_pnl":   round(self.unrealised_pnl, 2),
            "realised_pnl":     round(self.realised_pnl, 2),
            "daily_pnl":        round(self.daily_pnl, 2),
            "daily_loss_pct":   round(self.daily_loss_pct, 4),
            "positions": [
                {
                    "symbol":   p.symbol,
                    "direction": p.direction.value,
                    "qty":      p.qty,
                    "entry":    p.entry,
                    "mark":     p.mark_price,
                    "notional": round(p.notional, 2),
                    "pnl":      round(p.unrealised_pnl, 2),
                    "pnl_pct":  round(p.unrealised_pnl_pct, 4),
                }
                for p in self._positions.values()
            ],
        }

    def __repr__(self) -> str:
        return (
            f"<ExposureTracker positions={self.position_count} "
            f"notional={self.total_notional:.0f} "
            f"daily_pnl={self.daily_pnl:.2f}>"
        )

"""
position_sizer.py — Kelly / Fixed-Fractional Position Sizing
=============================================================
Calculates the recommended position size for a trade setup given the
account balance, risk tolerance, and signal quality.

Methods
-------
Fixed-fractional (default):
    risk_amount = balance × risk_per_trade_pct / 100
    qty         = risk_amount / sl_distance_usdt

Kelly Criterion (optional):
    f* = (p × b - q) / b       where b = avg_win/avg_loss
    Capped at max_kelly_fraction to prevent over-betting.

Both methods cap the notional at max_position_pct × balance.

Output
------
Returns a PositionSize dataclass containing:
  qty           — number of contracts/coins
  notional      — USD value of position
  risk_usdt     — USD amount at risk (entry to SL)
  leverage_used — leverage required at this notional (given margin)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from config import settings
from scanner.base_scanner import SignalDirection
from signals.entry_exit_calculator import TradeSetup
from utils.helpers import safe_divide, round_step
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_KELLY_FRACTION = 0.25     # cap Kelly at 25% of bankroll
MIN_QTY            = 0.001    # minimum tradeable quantity


@dataclass
class PositionSize:
    """Recommended position size for one trade."""
    symbol:        str
    direction:     SignalDirection
    qty:           float           # contracts / coins
    notional:      float           # USD value
    risk_usdt:     float           # USD at risk (to SL)
    margin_usdt:   float           # margin required
    leverage_used: int             # leverage used
    risk_pct:      float           # % of balance at risk
    method:        str             # "FIXED" or "KELLY"
    valid:         bool = True
    reason:        str  = ""

    def summary(self) -> str:
        dir_sym = "▲" if self.direction == SignalDirection.LONG else "▼"
        return (
            f"{dir_sym} {self.symbol} | qty={self.qty:.4f} | "
            f"notional=${self.notional:,.2f} | risk=${self.risk_usdt:.2f} "
            f"({self.risk_pct:.2f}%) | {self.leverage_used}x | {self.method}"
        )

    def __repr__(self) -> str:
        return (
            f"<PositionSize {self.symbol} {self.direction.value} "
            f"qty={self.qty:.4f} notional={self.notional:.2f} valid={self.valid}>"
        )


class PositionSizer:
    """
    Calculates position size using fixed-fractional or Kelly criterion.

    Parameters
    ----------
    risk_per_trade_pct : % of balance to risk per trade (fixed-frac default)
    max_position_pct   : max % of balance in a single position
    max_leverage       : maximum leverage allowed
    tick_size          : quantity rounding step (default 0.001)
    method             : "FIXED" or "KELLY"
    """

    def __init__(
        self,
        risk_per_trade_pct: float = None,
        max_position_pct:   float = None,
        max_leverage:       int   = None,
        tick_size:          float = 0.001,
        method:             str   = "FIXED",
    ) -> None:
        self._risk_pct      = risk_per_trade_pct or settings.risk_per_trade_pct
        self._max_pos_pct   = max_position_pct   or settings.max_position_size_pct
        self._max_leverage  = max_leverage       or settings.max_leverage
        self._tick_size     = tick_size
        self._method        = method.upper()

    # ── Public API ───────────────────────────────────────────────────────

    def calculate(
        self,
        setup:   TradeSetup,
        balance: float,
        win_rate: Optional[float] = None,
        avg_rr:   Optional[float] = None,
    ) -> PositionSize:
        """
        Calculate recommended position size.

        Parameters
        ----------
        setup    : TradeSetup with entry / SL levels
        balance  : Available account balance (USDT)
        win_rate : Historical win rate 0-1 (Kelly only)
        avg_rr   : Average risk:reward ratio (Kelly only)

        Returns
        -------
        PositionSize with qty, notional, and risk metrics.
        """
        if not setup.valid:
            return self._invalid("Invalid trade setup: " + setup.invalid_reason, setup)
        if balance <= 0:
            return self._invalid("Balance must be positive", setup)
        if setup.sl_distance <= 0:
            return self._invalid("SL distance is zero", setup)

        # Determine risk amount
        if self._method == "KELLY" and win_rate and avg_rr:
            risk_fraction = self._kelly_fraction(win_rate, avg_rr)
            method_label  = "KELLY"
        else:
            risk_fraction = self._risk_pct / 100
            method_label  = "FIXED"

        risk_usdt = balance * risk_fraction

        # qty = risk_usdt / SL_distance_per_unit
        qty = safe_divide(risk_usdt, setup.sl_distance)
        qty = round_step(qty, self._tick_size)

        if qty < MIN_QTY:
            return self._invalid(
                f"Computed qty {qty:.6f} below minimum {MIN_QTY}", setup
            )

        notional = qty * setup.entry

        # Cap at max position
        max_notional = balance * (self._max_pos_pct / 100)
        if notional > max_notional:
            notional = max_notional
            qty      = round_step(safe_divide(notional, setup.entry), self._tick_size)
            risk_usdt = qty * setup.sl_distance

        # Determine leverage
        margin_usdt   = safe_divide(notional, self._max_leverage)
        leverage_used = min(
            self._max_leverage,
            max(1, int(notional / max(balance * 0.1, 1))),
        )

        actual_risk_pct = safe_divide(risk_usdt, balance) * 100

        pos = PositionSize(
            symbol        = setup.symbol,
            direction     = setup.direction,
            qty           = qty,
            notional      = round(notional, 2),
            risk_usdt     = round(risk_usdt, 2),
            margin_usdt   = round(margin_usdt, 2),
            leverage_used = leverage_used,
            risk_pct      = round(actual_risk_pct, 4),
            method        = method_label,
            valid         = True,
        )

        logger.info(
            "PositionSize | %s %s | qty=%.4f notional=%.2f risk=%.2f%% %s",
            setup.symbol, setup.direction.value,
            qty, notional, actual_risk_pct, method_label,
        )
        return pos

    # ── Kelly ────────────────────────────────────────────────────────────

    @staticmethod
    def _kelly_fraction(win_rate: float, avg_rr: float) -> float:
        """
        Full Kelly: f* = (p*b - q) / b
        where p=win_rate, q=1-win_rate, b=avg_rr
        Capped at MAX_KELLY_FRACTION and floored at 0.
        """
        q = 1.0 - win_rate
        full_kelly = safe_divide(win_rate * avg_rr - q, avg_rr)
        half_kelly = full_kelly * 0.5   # half-Kelly is standard practice
        return max(0.0, min(half_kelly, MAX_KELLY_FRACTION))

    # ── Invalid factory ──────────────────────────────────────────────────

    @staticmethod
    def _invalid(reason: str, setup: TradeSetup) -> PositionSize:
        logger.warning("PositionSize invalid for %s: %s", setup.symbol, reason)
        return PositionSize(
            symbol=setup.symbol, direction=setup.direction,
            qty=0, notional=0, risk_usdt=0, margin_usdt=0,
            leverage_used=0, risk_pct=0, method="FIXED",
            valid=False, reason=reason,
        )

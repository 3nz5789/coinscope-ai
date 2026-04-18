"""
entry_exit_calculator.py — Entry / Take-Profit / Stop-Loss Calculator
=======================================================================
Calculates precise entry, take-profit (TP), and stop-loss (SL) levels
for a given Signal using ATR-based positioning.

Methods
-------
ATR method (default):
  SL  = entry ± ATR_MULTIPLIER_SL  × ATR
  TP1 = entry ± ATR_MULTIPLIER_TP1 × ATR   (first partial target)
  TP2 = entry ± ATR_MULTIPLIER_TP2 × ATR   (second full target)
  TP3 = entry ± ATR_MULTIPLIER_TP3 × ATR   (extended target)

Structure method (uses recent swing highs/lows):
  SL  = last swing low  (LONG) or last swing high (SHORT)
  TP  = next resistance (LONG) or next support    (SHORT)

Risk-Reward validation:
  Signals with RR < MIN_RISK_REWARD_RATIO are flagged as invalid.

Output: TradeSetup dataclass with all levels + position size recommendation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from config import settings
from data.data_normalizer import Candle
from scanner.base_scanner import SignalDirection
from signals.confluence_scorer import Signal
from signals.indicator_engine import Indicators
from utils.helpers import round_step, safe_divide, risk_reward_ratio, format_usdt, format_pct
from utils.logger import get_logger

logger = get_logger(__name__)

# ATR multipliers
ATR_SL_MULTIPLIER   = 1.5
ATR_TP1_MULTIPLIER  = 1.5    # 1:1 RR
ATR_TP2_MULTIPLIER  = 3.0    # 1:2 RR
ATR_TP3_MULTIPLIER  = 4.5    # 1:3 RR


@dataclass
class TradeSetup:
    """Complete entry/exit plan for a trade signal."""
    symbol:    str
    direction: SignalDirection
    signal_score: float

    # Prices
    entry:     float
    stop_loss: float
    tp1:       float
    tp2:       float
    tp3:       float

    # Risk metrics
    risk_pct:         float   # SL distance as % of entry
    rr_ratio_tp2:     float   # Risk:Reward to TP2
    rr_ratio_tp3:     float   # Risk:Reward to TP3
    atr:              float
    atr_pct:          float

    # Position sizing (filled by risk module)
    recommended_qty:  float = 0.0
    max_notional:     float = 0.0

    # Metadata
    method:    str = "ATR"      # "ATR" or "STRUCTURE"
    valid:     bool = True
    invalid_reason: str = ""
    notes:     list[str] = field(default_factory=list)

    @property
    def sl_distance(self) -> float:
        return abs(self.entry - self.stop_loss)

    @property
    def tp2_distance(self) -> float:
        return abs(self.tp2 - self.entry)

    def summary(self) -> str:
        dir_sym = "▲" if self.direction == SignalDirection.LONG else "▼"
        return (
            f"{dir_sym} {self.symbol} | "
            f"Entry {format_usdt(self.entry)} | "
            f"SL {format_usdt(self.stop_loss)} ({format_pct(-self.risk_pct if self.direction == SignalDirection.LONG else self.risk_pct)}) | "
            f"TP1 {format_usdt(self.tp1)} | "
            f"TP2 {format_usdt(self.tp2)} | "
            f"TP3 {format_usdt(self.tp3)} | "
            f"RR={self.rr_ratio_tp2:.2f} | "
            f"ATR={format_usdt(self.atr)}"
        )

    def __repr__(self) -> str:
        return (
            f"<TradeSetup {self.symbol} {self.direction.value} "
            f"entry={self.entry:.2f} sl={self.stop_loss:.2f} "
            f"tp2={self.tp2:.2f} RR={self.rr_ratio_tp2:.2f} valid={self.valid}>"
        )


class EntryExitCalculator:
    """
    Calculates ATR-based and structure-based entry/exit levels.

    Parameters
    ----------
    atr_sl_mult  : ATR multiplier for stop-loss     (default 1.5)
    atr_tp1_mult : ATR multiplier for first target  (default 1.5)
    atr_tp2_mult : ATR multiplier for second target (default 3.0)
    atr_tp3_mult : ATR multiplier for third target  (default 4.5)
    min_rr       : Minimum acceptable RR ratio      (default settings.min_risk_reward_ratio)
    tick_size    : Price rounding step               (default 0.01)
    """

    def __init__(
        self,
        atr_sl_mult:  float = ATR_SL_MULTIPLIER,
        atr_tp1_mult: float = ATR_TP1_MULTIPLIER,
        atr_tp2_mult: float = ATR_TP2_MULTIPLIER,
        atr_tp3_mult: float = ATR_TP3_MULTIPLIER,
        min_rr: Optional[float] = None,
        tick_size: float = 0.01,
    ) -> None:
        self._sl_mult   = atr_sl_mult
        self._tp1_mult  = atr_tp1_mult
        self._tp2_mult  = atr_tp2_mult
        self._tp3_mult  = atr_tp3_mult
        self._min_rr    = min_rr or settings.min_risk_reward_ratio
        self._tick_size = tick_size

    def calculate(
        self,
        signal: Signal,
        candles: list[Candle],
        current_price: Optional[float] = None,
    ) -> TradeSetup:
        """
        Calculate the full trade setup for a signal.

        Parameters
        ----------
        signal        : Confluence Signal from ConfluenceScorer
        candles       : Recent candles (used for ATR and structure levels)
        current_price : Override for entry price. Defaults to last close.

        Returns
        -------
        TradeSetup with all entry/exit levels populated.
        """
        if not candles:
            return self._invalid_setup(signal, "No candle data available")

        entry = current_price or candles[-1].close
        ind   = signal.indicators

        # Get ATR — prefer precomputed, otherwise compute from candles
        atr = ind.atr if (ind and ind.atr) else self._compute_atr(candles)
        if not atr or atr <= 0:
            return self._invalid_setup(signal, "Could not compute ATR")

        atr_pct = safe_divide(atr, entry) * 100

        # ── ATR-based levels ──────────────────────────────────────────────
        if signal.direction == SignalDirection.LONG:
            sl  = entry - self._sl_mult  * atr
            tp1 = entry + self._tp1_mult * atr
            tp2 = entry + self._tp2_mult * atr
            tp3 = entry + self._tp3_mult * atr
        else:  # SHORT
            sl  = entry + self._sl_mult  * atr
            tp1 = entry - self._tp1_mult * atr
            tp2 = entry - self._tp2_mult * atr
            tp3 = entry - self._tp3_mult * atr

        # Round to tick size
        entry, sl, tp1, tp2, tp3 = (
            round_step(v, self._tick_size)
            for v in (entry, sl, tp1, tp2, tp3)
        )

        # Try to improve SL/TP with structure (swing levels)
        struct_sl = self._find_structure_sl(signal.direction, candles, entry, atr)
        if struct_sl:
            sl     = round_step(struct_sl, self._tick_size)
            method = "STRUCTURE+ATR_TP"
        else:
            method = "ATR"

        # Risk metrics
        risk_pct = safe_divide(abs(entry - sl), entry) * 100
        rr_tp2   = risk_reward_ratio(entry, sl, tp2)
        rr_tp3   = risk_reward_ratio(entry, sl, tp3)
        notes: list[str] = []

        # Validate RR
        valid = True
        invalid_reason = ""
        if rr_tp2 < self._min_rr:
            valid          = False
            invalid_reason = (
                f"RR to TP2 ({rr_tp2:.2f}) below minimum "
                f"({self._min_rr:.2f})"
            )
            notes.append(f"⚠ Low RR: {rr_tp2:.2f} (min {self._min_rr:.2f})")

        # Warn on very tight stops
        if risk_pct < 0.2:
            notes.append(f"⚠ Tight SL: only {risk_pct:.3f}% risk")

        # Warn on extreme ATR
        if atr_pct > 3.0:
            notes.append(f"⚠ High volatility: ATR={atr_pct:.2f}% of price")

        # Add indicator context to notes
        if ind:
            if ind.rsi:      notes.append(f"RSI={ind.rsi:.1f}")
            if ind.adx:      notes.append(f"ADX={ind.adx:.1f} ({'trending' if ind.is_trending else 'ranging'})")
            if ind.bb_pct_b: notes.append(f"BB%B={ind.bb_pct_b:.2f}")

        setup = TradeSetup(
            symbol        = signal.symbol,
            direction     = signal.direction,
            signal_score  = signal.score,
            entry         = entry,
            stop_loss     = sl,
            tp1           = tp1,
            tp2           = tp2,
            tp3           = tp3,
            risk_pct      = risk_pct,
            rr_ratio_tp2  = rr_tp2,
            rr_ratio_tp3  = rr_tp3,
            atr           = atr,
            atr_pct       = atr_pct,
            method        = method,
            valid         = valid,
            invalid_reason = invalid_reason,
            notes         = notes,
        )

        logger.info(
            "TradeSetup | %s %s | entry=%.2f SL=%.2f TP2=%.2f "
            "RR=%.2f risk=%.3f%% method=%s valid=%s",
            signal.symbol, signal.direction.value,
            entry, sl, tp2, rr_tp2, risk_pct, method, valid,
        )
        return setup

    # ── Structure-based SL finder ────────────────────────────────────────

    def _find_structure_sl(
        self,
        direction: SignalDirection,
        candles: list[Candle],
        entry: float,
        atr: float,
        lookback: int = 10,
    ) -> Optional[float]:
        """
        Find the nearest swing high/low to use as a structural stop-loss.

        Returns a price or None if no clean structure found within ATR range.
        """
        recent = candles[-(lookback + 1):-1]  # exclude current candle
        if not recent:
            return None

        if direction == SignalDirection.LONG:
            # Look for the most recent swing low below entry
            swing_lows = [c.low for c in recent if c.low < entry]
            if not swing_lows:
                return None
            sl_candidate = min(swing_lows) - atr * 0.1  # small buffer below
            # Only use if it's within 2× ATR of entry (not too far)
            if abs(entry - sl_candidate) <= atr * 2.5:
                return sl_candidate
        else:
            # Look for the most recent swing high above entry
            swing_highs = [c.high for c in recent if c.high > entry]
            if not swing_highs:
                return None
            sl_candidate = max(swing_highs) + atr * 0.1
            if abs(sl_candidate - entry) <= atr * 2.5:
                return sl_candidate
        return None

    # ── ATR computation fallback ─────────────────────────────────────────

    @staticmethod
    def _compute_atr(candles: list[Candle], period: int = 14) -> float:
        if len(candles) < period + 1:
            return 0.0
        tr_values = []
        for i in range(1, len(candles)):
            c = candles[i]
            p = candles[i - 1]
            tr_values.append(max(
                c.high - c.low,
                abs(c.high - p.close),
                abs(c.low  - p.close),
            ))
        if len(tr_values) < period:
            return 0.0
        atr = sum(tr_values[:period]) / period
        for tr in tr_values[period:]:
            atr = (atr * (period - 1) + tr) / period
        return atr

    # ── Invalid setup factory ────────────────────────────────────────────

    @staticmethod
    def _invalid_setup(signal: Signal, reason: str) -> TradeSetup:
        logger.warning("Invalid TradeSetup for %s: %s", signal.symbol, reason)
        return TradeSetup(
            symbol=signal.symbol, direction=signal.direction,
            signal_score=signal.score,
            entry=0, stop_loss=0, tp1=0, tp2=0, tp3=0,
            risk_pct=0, rr_ratio_tp2=0, rr_ratio_tp3=0,
            atr=0, atr_pct=0,
            valid=False, invalid_reason=reason,
        )

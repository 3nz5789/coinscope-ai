"""
confluence_scorer.py — Signal Aggregation & Scoring
=====================================================
Aggregates raw ScannerHits and IndicatorEngine output into a single
weighted confluence score and a final actionable Signal.

Scoring model
-------------
Each ScannerHit carries a raw score (0-100) and a weight (1/2/3 for
WEAK/MEDIUM/STRONG).  The confluence scorer:

  1. Collects all hits for a symbol across all scanners
  2. Groups hits by direction (LONG / SHORT)
  3. Computes a weighted sum:
       raw_score = Σ (hit.score × hit.weight)
  4. Normalises to 0-100 against a theoretical maximum
  5. Applies indicator confirmation bonuses:
       + trend alignment    (+10 pts)
       + momentum alignment (+8 pts)
       + RSI zone bonus     (+5 pts)
       + MACD cross         (+7 pts)
       + ADX trending       (+5 pts)
  6. Applies penalty for contradicting indicators
  7. Emits a Signal when final score >= MIN_CONFLUENCE_SCORE (from .env)

Signal schema
-------------
  symbol        : e.g. "BTCUSDT"
  direction     : "LONG" | "SHORT"
  score         : 0.0 – 100.0
  strength      : "WEAK" | "MODERATE" | "STRONG" | "VERY_STRONG"
  contributing_hits : list of ScannerHits that voted for this direction
  indicators    : Indicators snapshot
  timestamp     : UTC epoch seconds
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from config import settings
from data.data_normalizer import Candle
from scanner.base_scanner import ScannerHit, ScannerResult, SignalDirection, HitStrength
from signals.indicator_engine import IndicatorEngine, Indicators
from utils.helpers import safe_divide
from utils.logger import get_logger

logger = get_logger(__name__)

# Score thresholds for signal strength labels
SCORE_WEAK      = 40.0
SCORE_MODERATE  = 55.0
SCORE_STRONG    = 70.0
SCORE_VERY_STRONG = 85.0

# Indicator bonus weights
BONUS_TREND      = 10.0
BONUS_MOMENTUM   = 8.0
BONUS_RSI_ZONE   = 5.0
BONUS_MACD_CROSS = 7.0
BONUS_ADX        = 5.0
PENALTY_CONTRA   = 8.0     # deducted when indicators contradict direction

# Theoretical max raw scanner score used for normalisation
MAX_RAW_SCORE = 300.0


@dataclass
class Signal:
    """Final aggregated trading signal for one symbol."""
    symbol:            str
    direction:         SignalDirection
    score:             float                    # 0.0 – 100.0
    strength:          str                      # WEAK / MODERATE / STRONG / VERY_STRONG
    contributing_hits: list[ScannerHit]         = field(default_factory=list)
    indicators:        Optional[Indicators]     = None
    reasons:           list[str]                = field(default_factory=list)
    bonuses:           list[str]                = field(default_factory=list)
    timestamp:         float                    = field(default_factory=time.time)

    @property
    def is_actionable(self) -> bool:
        return self.score >= settings.min_confluence_score

    @property
    def scanner_names(self) -> list[str]:
        return list({h.scanner for h in self.contributing_hits})

    def summary(self) -> str:
        return (
            f"{self.symbol} {self.direction.value} | "
            f"score={self.score:.1f} [{self.strength}] | "
            f"scanners={self.scanner_names} | "
            f"{'✅ ACTIONABLE' if self.is_actionable else '❌ below threshold'}"
        )

    def __repr__(self) -> str:
        return f"<Signal {self.symbol} {self.direction.value} score={self.score:.1f}>"


class ConfluenceScorer:
    """
    Combines scanner hits and indicator confirmations into a scored Signal.

    Parameters
    ----------
    min_score : float
        Minimum confluence score to mark a signal as actionable.
        Defaults to settings.min_confluence_score.
    require_indicator_alignment : bool
        If True, the dominant indicator direction must agree with the
        scanner direction for the signal to be actionable (default True).
    """

    def __init__(
        self,
        min_score: Optional[float] = None,
        require_indicator_alignment: bool = True,
    ) -> None:
        self._min_score  = min_score or settings.min_confluence_score
        self._require_alignment = require_indicator_alignment
        self._engine     = IndicatorEngine()

    def score(
        self,
        symbol: str,
        scanner_results: list[ScannerResult],
        candles: list[Candle],
    ) -> Optional[Signal]:
        """
        Compute a confluence score for a symbol.

        Parameters
        ----------
        symbol          : Trading pair, e.g. "BTCUSDT"
        scanner_results : Latest ScannerResult from every active scanner
        candles         : Recent OHLCV candles (50+ recommended)

        Returns
        -------
        Signal or None
            Returns a Signal if any direction reaches the minimum score.
            Returns None if no significant confluence detected.
        """
        # ── 1. Compute indicators ─────────────────────────────────────────
        indicators = self._engine.compute(candles) if len(candles) >= 26 else Indicators(symbol=symbol)

        # ── 2. Collect all hits by direction ──────────────────────────────
        long_hits:  list[ScannerHit] = []
        short_hits: list[ScannerHit] = []

        for result in scanner_results:
            if result.symbol != symbol or result.error:
                continue
            for hit in result.hits:
                if hit.direction == SignalDirection.LONG:
                    long_hits.append(hit)
                elif hit.direction == SignalDirection.SHORT:
                    short_hits.append(hit)

        if not long_hits and not short_hits:
            return None

        # ── 3. Compute raw weighted scores ───────────────────────────────
        long_raw  = sum(h.score * h.weight for h in long_hits)
        short_raw = sum(h.score * h.weight for h in short_hits)

        long_norm  = min(safe_divide(long_raw,  MAX_RAW_SCORE) * 100, 70.0)
        short_norm = min(safe_divide(short_raw, MAX_RAW_SCORE) * 100, 70.0)

        # ── 4. Pick dominant direction ────────────────────────────────────
        if long_norm >= short_norm:
            direction  = SignalDirection.LONG
            base_score = long_norm
            hits       = long_hits
        else:
            direction  = SignalDirection.SHORT
            base_score = short_norm
            hits       = short_hits

        # ── 5. Indicator bonuses / penalties ─────────────────────────────
        bonus_total = 0.0
        bonuses: list[str] = []
        reasons: list[str] = [h.reason for h in hits]

        bonus_total, bonuses = self._apply_indicator_bonuses(
            direction, indicators, base_score
        )

        final_score = min(base_score + bonus_total, 100.0)

        # ── 6. Indicator alignment gate ───────────────────────────────────
        if self._require_alignment and indicators.trend_direction != "NEUTRAL":
            aligned = (
                (direction == SignalDirection.LONG  and indicators.trend_direction == "BULLISH") or
                (direction == SignalDirection.SHORT and indicators.trend_direction == "BEARISH")
            )
            if not aligned:
                logger.debug(
                    "%s: indicator trend (%s) contradicts direction (%s) — "
                    "applying penalty",
                    symbol, indicators.trend_direction, direction.value,
                )
                final_score = max(final_score - PENALTY_CONTRA, 0.0)
                bonuses.append(f"−{PENALTY_CONTRA:.0f} indicator contradiction penalty")

        # ── 7. Build and return Signal ────────────────────────────────────
        signal = Signal(
            symbol            = symbol,
            direction         = direction,
            score             = round(final_score, 2),
            strength          = self._strength_label(final_score),
            contributing_hits = hits,
            indicators        = indicators,
            reasons           = reasons,
            bonuses           = bonuses,
        )

        logger.info(
            "Confluence | %s %s score=%.1f [%s] hits=%d scanners=%s",
            symbol, direction.value, final_score,
            signal.strength, len(hits), signal.scanner_names,
        )
        return signal

    # ── Indicator bonuses ────────────────────────────────────────────────

    def _apply_indicator_bonuses(
        self,
        direction: SignalDirection,
        ind: Indicators,
        base_score: float,
    ) -> tuple[float, list[str]]:
        bonus  = 0.0
        notes: list[str] = []

        is_long  = direction == SignalDirection.LONG
        is_short = direction == SignalDirection.SHORT

        # Trend alignment
        if (is_long  and ind.trend_direction == "BULLISH") or \
           (is_short and ind.trend_direction == "BEARISH"):
            bonus += BONUS_TREND
            notes.append(f"+{BONUS_TREND:.0f} EMA trend aligned ({ind.trend_direction})")

        # Momentum alignment
        if (is_long  and ind.momentum_bias == "BULLISH") or \
           (is_short and ind.momentum_bias == "BEARISH"):
            bonus += BONUS_MOMENTUM
            notes.append(f"+{BONUS_MOMENTUM:.0f} momentum aligned ({ind.momentum_bias})")

        # RSI zone
        if is_long  and ind.rsi_oversold:
            bonus += BONUS_RSI_ZONE
            notes.append(f"+{BONUS_RSI_ZONE:.0f} RSI oversold ({ind.rsi:.1f})")
        elif is_short and ind.rsi_overbought:
            bonus += BONUS_RSI_ZONE
            notes.append(f"+{BONUS_RSI_ZONE:.0f} RSI overbought ({ind.rsi:.1f})")

        # MACD cross
        if is_long  and ind.macd_bullish_cross:
            bonus += BONUS_MACD_CROSS
            notes.append(f"+{BONUS_MACD_CROSS:.0f} MACD bullish cross")
        elif is_short and ind.macd_bearish_cross:
            bonus += BONUS_MACD_CROSS
            notes.append(f"+{BONUS_MACD_CROSS:.0f} MACD bearish cross")

        # ADX trending confirms momentum
        if ind.is_trending:
            bonus += BONUS_ADX
            notes.append(f"+{BONUS_ADX:.0f} ADX trending ({ind.adx:.1f})")

        # Bollinger band squeeze release
        if ind.bb_width is not None and ind.bb_width < 1.0:
            bonus += 3.0
            notes.append("+3 BB squeeze (volatility breakout expected)")

        return bonus, notes

    @staticmethod
    def _strength_label(score: float) -> str:
        if score >= SCORE_VERY_STRONG: return "VERY_STRONG"
        if score >= SCORE_STRONG:      return "STRONG"
        if score >= SCORE_MODERATE:    return "MODERATE"
        return "WEAK"

    # ── Batch scoring ────────────────────────────────────────────────────

    def score_all(
        self,
        scanner_results: list[ScannerResult],
        candles_by_symbol: dict[str, list[Candle]],
    ) -> dict[str, Signal]:
        """
        Score all symbols that have scanner results.

        Parameters
        ----------
        scanner_results      : All results from the latest scan cycle
        candles_by_symbol    : {symbol: list[Candle]} for indicator computation

        Returns
        -------
        dict[str, Signal] : {symbol: Signal} for every symbol with a signal
        """
        symbols = {r.symbol for r in scanner_results if not r.error}
        signals: dict[str, Signal] = {}

        for symbol in symbols:
            sym_results = [r for r in scanner_results if r.symbol == symbol]
            candles     = candles_by_symbol.get(symbol, [])
            sig = self.score(symbol, sym_results, candles)
            if sig:
                signals[symbol] = sig

        actionable = [s for s in signals.values() if s.is_actionable]
        logger.info(
            "Confluence cycle complete | symbols=%d signals=%d actionable=%d",
            len(symbols), len(signals), len(actionable),
        )
        return signals

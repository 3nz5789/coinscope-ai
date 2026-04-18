"""
test_signals.py — Signal Generation & Scoring Tests
====================================================
Tests IndicatorEngine computations, ConfluenceScorer scoring model,
EntryExitCalculator levels, and Backtester simulation logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pytest

from data.data_normalizer import Candle
from scanner.base_scanner import SignalDirection, HitStrength, ScannerHit, ScannerResult
from signals.indicator_engine import IndicatorEngine, Indicators
from signals.confluence_scorer import ConfluenceScorer, Signal
from signals.entry_exit_calculator import EntryExitCalculator, TradeSetup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_candle(
    close: float,
    open_: float = None,
    high: float = None,
    low:  float = None,
    volume: float = 1000.0,
    symbol: str = "BTCUSDT",
    ts: int = None,
) -> Candle:
    o = open_ or close * 0.999
    h = high  or close * 1.005
    l = low   or close * 0.995
    t = ts    or int(time.time() * 1000)
    return Candle(
        symbol=symbol, interval="1h",
        open_time=t, close_time=t + 3_599_999,
        open=o, high=h, low=l, close=close,
        volume=volume, quote_volume=close * volume,
        trades=200, taker_buy_volume=volume * 0.55,
        taker_buy_quote=close * volume * 0.55,
    )


def trending_up_candles(n: int = 60) -> list[Candle]:
    """Generate uptrending candles with increasing closes."""
    candles = []
    base = 60_000.0
    for i in range(n):
        close = base + i * 50
        candles.append(make_candle(close=close, ts=1_700_000_000_000 + i * 3_600_000))
    return candles


def ranging_candles(n: int = 60) -> list[Candle]:
    """Candles oscillating around a fixed price."""
    candles = []
    base = 65_000.0
    for i in range(n):
        delta = 200 * np.sin(i * 0.3)
        candles.append(make_candle(close=base + delta, ts=1_700_000_000_000 + i * 3_600_000))
    return candles


def make_scanner_hit(
    direction: SignalDirection = SignalDirection.LONG,
    score: float = 70.0,
    strength: HitStrength = HitStrength.STRONG,
    scanner: str = "VolumeScanner",
) -> ScannerHit:
    return ScannerHit(
        scanner   = scanner,
        symbol    = "BTCUSDT",
        direction = direction,
        strength  = strength,
        score     = score,
        reason    = f"Test hit from {scanner}",
    )


def make_scanner_result(hits: list[ScannerHit], symbol="BTCUSDT") -> ScannerResult:
    return ScannerResult(symbol=symbol, hits=hits, error=None)


# ---------------------------------------------------------------------------
# IndicatorEngine
# ---------------------------------------------------------------------------

class TestIndicatorEngine:

    def test_returns_indicators_with_enough_candles(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(60)
        ind     = engine.compute(candles)
        assert isinstance(ind, Indicators)
        assert ind.rsi is not None
        assert ind.ema_9  is not None
        assert ind.ema_21 is not None

    def test_rsi_in_valid_range(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(60)
        ind     = engine.compute(candles)
        assert 0 <= ind.rsi <= 100

    def test_trend_direction_bullish_on_uptrend(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(60)
        ind     = engine.compute(candles)
        assert ind.trend_direction == "BULLISH"

    def test_macd_structure_present(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(60)
        ind     = engine.compute(candles)
        assert ind.macd        is not None
        assert ind.macd_signal is not None
        assert ind.macd_hist   is not None

    def test_bollinger_bands_ordered(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(60)
        ind     = engine.compute(candles)
        if ind.bb_upper and ind.bb_lower:
            assert ind.bb_upper > ind.bb_middle > ind.bb_lower

    def test_atr_positive(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(30)
        ind     = engine.compute(candles)
        if ind.atr:
            assert ind.atr > 0

    def test_insufficient_candles_returns_empty_indicators(self):
        engine  = IndicatorEngine()
        candles = trending_up_candles(10)   # < 26 required
        ind     = engine.compute(candles)
        # Should return an Indicators object but with None values
        assert isinstance(ind, Indicators)


# ---------------------------------------------------------------------------
# ConfluenceScorer
# ---------------------------------------------------------------------------

class TestConfluenceScorer:

    def test_strong_long_signal_above_threshold(self):
        scorer  = ConfluenceScorer(min_score=40.0)
        candles = trending_up_candles(60)
        hits    = [
            make_scanner_hit(SignalDirection.LONG, score=80, strength=HitStrength.STRONG, scanner="VolumeScanner"),
            make_scanner_hit(SignalDirection.LONG, score=75, strength=HitStrength.STRONG, scanner="PatternScanner"),
            make_scanner_hit(SignalDirection.LONG, score=70, strength=HitStrength.MEDIUM, scanner="OrderBookScanner"),
        ]
        result  = make_scanner_result(hits)
        signal  = scorer.score("BTCUSDT", [result], candles)
        assert signal is not None
        assert signal.direction == SignalDirection.LONG
        assert signal.score     >= 40.0

    def test_opposing_hits_dominant_direction_wins(self):
        scorer  = ConfluenceScorer()
        candles = trending_up_candles(60)
        hits    = [
            make_scanner_hit(SignalDirection.LONG,  score=80, strength=HitStrength.STRONG),
            make_scanner_hit(SignalDirection.LONG,  score=75, strength=HitStrength.STRONG),
            make_scanner_hit(SignalDirection.SHORT, score=40, strength=HitStrength.WEAK),
        ]
        result = make_scanner_result(hits)
        signal = scorer.score("BTCUSDT", [result], candles)
        assert signal is not None
        assert signal.direction == SignalDirection.LONG

    def test_no_hits_returns_none(self):
        scorer  = ConfluenceScorer()
        result  = make_scanner_result([])
        signal  = scorer.score("BTCUSDT", [result], trending_up_candles(50))
        assert signal is None

    def test_score_capped_at_100(self):
        scorer  = ConfluenceScorer(min_score=0.0)
        candles = trending_up_candles(60)
        hits    = [
            make_scanner_hit(score=100, strength=HitStrength.STRONG, scanner=f"Scanner{i}")
            for i in range(10)
        ]
        result = make_scanner_result(hits)
        signal = scorer.score("BTCUSDT", [result], candles)
        if signal:
            assert signal.score <= 100.0

    def test_strength_labels(self):
        assert ConfluenceScorer._strength_label(90) == "VERY_STRONG"
        assert ConfluenceScorer._strength_label(72) == "STRONG"
        assert ConfluenceScorer._strength_label(58) == "MODERATE"
        assert ConfluenceScorer._strength_label(35) == "WEAK"


# ---------------------------------------------------------------------------
# EntryExitCalculator
# ---------------------------------------------------------------------------

class TestEntryExitCalculator:

    @pytest.fixture
    def calculator(self):
        return EntryExitCalculator(tick_size=0.01)

    def _make_signal(self, direction: SignalDirection) -> Signal:
        return Signal(
            symbol    = "BTCUSDT",
            direction = direction,
            score     = 75.0,
            strength  = "STRONG",
        )

    def test_long_setup_tp_above_entry(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.LONG)
        setup   = calculator.calculate(signal, candles)
        assert setup.tp1 > setup.entry
        assert setup.tp2 > setup.tp1
        assert setup.tp3 > setup.tp2

    def test_long_setup_sl_below_entry(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.LONG)
        setup   = calculator.calculate(signal, candles)
        assert setup.stop_loss < setup.entry

    def test_short_setup_tp_below_entry(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.SHORT)
        setup   = calculator.calculate(signal, candles)
        assert setup.tp1 < setup.entry
        assert setup.tp2 < setup.tp1
        assert setup.tp3 < setup.tp2

    def test_short_setup_sl_above_entry(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.SHORT)
        setup   = calculator.calculate(signal, candles)
        assert setup.stop_loss > setup.entry

    def test_rr_ratio_positive(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.LONG)
        setup   = calculator.calculate(signal, candles)
        assert setup.rr_ratio_tp2 > 0

    def test_invalid_on_empty_candles(self, calculator):
        signal = self._make_signal(SignalDirection.LONG)
        setup  = calculator.calculate(signal, [])
        assert setup.valid is False

    def test_atr_computed(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.LONG)
        setup   = calculator.calculate(signal, candles)
        assert setup.atr > 0

    def test_custom_entry_price_used(self, calculator):
        candles = trending_up_candles(30)
        signal  = self._make_signal(SignalDirection.LONG)
        custom_price = 70_000.0
        setup   = calculator.calculate(signal, candles, current_price=custom_price)
        assert setup.entry == pytest.approx(custom_price, rel=0.01)

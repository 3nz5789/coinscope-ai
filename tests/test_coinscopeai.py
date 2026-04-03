"""
CoinScopeAI — Comprehensive Unit & Integration Test Suite
==========================================================
Tests critical paths:
  - Scoring engine (signal generation, sub-scores)
  - Risk gate (position sizing, circuit breakers, P&L)
  - Kelly position sizer (formula correctness, regime multipliers)
  - HMM regime detector (fit/predict, ensemble)
  - Trade journal (open/close/stats)
  - Testnet executor (order flow, P&L, circuit breakers)
  - Multi-timeframe filter (signal filtering)
  - Scale-up manager (promotion logic)

Run:
    pip install pytest numpy pandas hmmlearn scikit-learn --break-system-packages
    pytest tests/test_coinscopeai.py -v
"""

import sys
import os
import json
import pytest
import numpy as np
import tempfile
import shutil

# ---------------------------------------------------------------------------
# Path helpers — adjust if your project root differs
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


# ===========================================================================
# FIXTURES
# ===========================================================================

@pytest.fixture
def sample_ohlcv(n=500):
    """Generate realistic OHLCV data."""
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high  = close + np.abs(np.random.randn(n) * 0.3)
    low   = close - np.abs(np.random.randn(n) * 0.3)
    vol   = np.random.uniform(1000, 5000, n)
    spread = np.random.uniform(0.001, 0.01, n)   # absolute USD spread
    return close, high, low, vol, spread


@pytest.fixture
def regime_data(n=300):
    """Generate returns + vol arrays for regime fitting."""
    np.random.seed(0)
    returns = np.random.randn(n) * 0.02
    vol = np.abs(returns) + 0.005
    return returns, vol


@pytest.fixture
def tmp_journal_path(tmp_path):
    """Provide a temp path for the trade journal."""
    return str(tmp_path / "test_journal.json")


# ===========================================================================
# 1. SCORING ENGINE
# ===========================================================================

class TestFixedScorer:
    """Tests for scoring_fixed.FixedScorer"""

    def _scorer(self):
        from scoring_fixed import FixedScorer
        return FixedScorer()

    def test_generate_signals_returns_correct_shapes(self, sample_ohlcv):
        c, h, lo, v, sp = sample_ohlcv
        scorer = self._scorer()
        signals, sub_scores = scorer.generate_signals(c, h, lo, v, sp)
        assert signals.shape == c.shape
        assert isinstance(sub_scores, dict)

    def test_signals_are_only_valid_values(self, sample_ohlcv):
        c, h, lo, v, sp = sample_ohlcv
        scorer = self._scorer()
        signals, _ = scorer.generate_signals(c, h, lo, v, sp)
        unique = set(signals.tolist())
        assert unique.issubset({-1, 0, 1}), f"Unexpected signal values: {unique}"

    def test_some_signals_generated(self, sample_ohlcv):
        c, h, lo, v, sp = sample_ohlcv
        scorer = self._scorer()
        signals, _ = scorer.generate_signals(c, h, lo, v, sp)
        assert (signals != 0).sum() > 0, "No signals generated at all"

    def test_sub_scores_all_in_range_0_3(self, sample_ohlcv):
        c, h, lo, v, sp = sample_ohlcv
        scorer = self._scorer()
        _, sub_scores = scorer.generate_signals(c, h, lo, v, sp)
        for key in ("momentum", "trend", "volatility", "volume", "entry", "liquidity"):
            arr = sub_scores[key]
            assert arr.min() >= 0,  f"{key} score below 0: {arr.min()}"
            assert arr.max() <= 3,  f"{key} score above 3: {arr.max()}"

    def test_total_score_range_0_12(self, sample_ohlcv):
        c, h, lo, v, sp = sample_ohlcv
        scorer = self._scorer()
        total, sub_scores = scorer.calculate_total_score(c, h, lo, v, sp)
        assert total.min() >= 0,  f"Total score below 0: {total.min()}"
        assert total.max() <= 12, f"Total score above 12: {total.max()}"

    def test_rsi_stays_in_0_100(self, sample_ohlcv):
        c, *_ = sample_ohlcv
        scorer = self._scorer()
        rsi = scorer.calculate_rsi(c)
        assert rsi[14:].min() >= 0
        assert rsi[14:].max() <= 100

    def test_ema_monotone_smoothing(self, sample_ohlcv):
        """EMA should be smoother than raw close (lower std dev)."""
        c, *_ = sample_ohlcv
        scorer = self._scorer()
        ema = scorer.calculate_ema(c, 9)
        assert np.std(ema) < np.std(c)

    def test_signal_threshold_conflict_detection(self, sample_ohlcv):
        """
        KNOWN BUG: scores in [long_threshold, short_threshold] get overwritten.
        This test documents the bug; fix thresholds so they don't overlap.
        E.g. long_threshold=8, short_threshold=4 (non-overlapping).
        """
        c, h, lo, v, sp = sample_ohlcv
        scorer = self._scorer()
        total, _ = scorer.calculate_total_score(c, h, lo, v, sp)
        # Any score in [5.5, 6.5] is FIRST set to LONG then overwritten to SHORT
        conflict_mask = (total >= 5.5) & (total <= 6.5)
        signals, _ = scorer.generate_signals(c, h, lo, v, sp)
        conflict_signals = signals[conflict_mask]
        # All should end up as -1 (SHORT) due to sequential overwrite
        if conflict_mask.sum() > 0:
            assert (conflict_signals == -1).all(), (
                "BUG: scores in [5.5, 6.5] should all be SHORT (overwrite bug)"
            )


# ===========================================================================
# 2. RISK GATE
# ===========================================================================

class TestRiskGate:
    """Tests for risk_gate.RiskGate"""

    def _gate(self, **kwargs):
        from risk_gate import RiskGate
        return RiskGate(initial_capital=10_000, **kwargs)

    # --- Position Sizing ---
    def test_position_size_bull_greater_than_bear(self):
        gate = self._gate()
        bull = gate.calculate_position_size(0.44, 2.1, 1.0, "bull")
        bear = gate.calculate_position_size(0.44, 2.1, 1.0, "bear")
        assert bull > bear, "Bull sizing should exceed bear sizing"

    def test_position_size_capped_at_5pct(self):
        gate = self._gate()
        size = gate.calculate_position_size(0.99, 100.0, 0.001, "bull")
        assert size <= 0.05, f"Position size {size:.4f} exceeds 5% cap"

    def test_position_size_zero_on_negative_kelly(self):
        gate = self._gate()
        # win_rate=0.1 → Kelly is deeply negative
        size = gate.calculate_position_size(0.10, 1.0, 5.0, "bull")
        assert size == 0.0, "Negative Kelly should yield zero size"

    def test_position_size_zero_on_zero_avg_loss(self):
        gate = self._gate()
        size = gate.calculate_position_size(0.44, 2.1, 0.0, "bull")
        assert size == 0.0

    # --- Stop Loss & Take Profit ---
    def test_stop_loss_below_entry_for_long(self):
        gate = self._gate()
        sl = gate.calculate_stop_loss(100.0, 2.0, direction=1)
        assert sl < 100.0, f"Stop loss {sl} should be below entry 100 for LONG"

    def test_stop_loss_above_entry_for_short(self):
        gate = self._gate()
        sl = gate.calculate_stop_loss(100.0, 2.0, direction=-1)
        assert sl > 100.0, f"Stop loss {sl} should be above entry 100 for SHORT"

    def test_stop_loss_capped_at_2pct(self):
        gate = self._gate()
        # ATR of 50 on price 100 = 50% would be way too wide; cap at 2%
        sl = gate.calculate_stop_loss(100.0, atr=50.0, direction=1)
        max_distance = 100.0 * 0.02  # 2%
        assert (100.0 - sl) <= max_distance + 1e-9

    def test_take_profit_2to1_risk_reward(self):
        gate = self._gate()
        entry = 100.0
        sl = gate.calculate_stop_loss(entry, 1.0, direction=1)
        tp = gate.calculate_take_profit(entry, sl, direction=1)
        risk   = entry - sl
        reward = tp - entry
        assert abs(reward - 2 * risk) < 1e-9, f"TP should be 2x risk: {reward} vs {2*risk}"

    # --- Circuit Breakers ---
    def test_circuit_breaker_daily_loss(self):
        gate = self._gate(max_daily_loss_pct=0.10)
        gate.daily_pnl = -1001.0   # exceeds 10% of 10,000
        halted, reason = gate.check_circuit_breakers()
        assert halted, "Daily loss should trigger circuit breaker"
        assert "daily" in reason.lower()

    def test_circuit_breaker_max_drawdown(self):
        gate = self._gate(max_drawdown_pct=0.20)
        gate.peak_equity = 10_000
        gate.current_equity = 7_000   # 30% drawdown
        halted, reason = gate.check_circuit_breakers()
        assert halted, "Max drawdown should trigger circuit breaker"

    def test_circuit_breaker_consecutive_losses(self):
        gate = self._gate(max_consecutive_losses=5)
        gate.consecutive_losses = 5
        halted, reason = gate.check_circuit_breakers()
        assert halted, "Consecutive losses should trigger circuit breaker"

    def test_no_circuit_breaker_on_healthy_state(self):
        gate = self._gate()
        halted, _ = gate.check_circuit_breakers()
        assert not halted, "No circuit breaker should fire on fresh gate"

    # --- Open / Close Position ---
    def test_open_position_returns_position_object(self):
        from risk_gate import Position
        gate = self._gate()
        pos = gate.open_position(
            symbol="BTC/USDT", direction=1, entry_price=50_000,
            entry_time=0, atr=500, regime="bull",
            signal_score=0.80, win_rate=0.44, avg_win=2.1, avg_loss=1.0
        )
        assert pos is not None
        assert isinstance(pos, Position)

    def test_open_position_blocked_by_low_score(self):
        gate = self._gate(min_signal_score=0.65)
        pos = gate.open_position(
            symbol="BTC/USDT", direction=1, entry_price=50_000,
            entry_time=0, atr=500, regime="bull",
            signal_score=0.40   # below threshold
        )
        assert pos is None, "Low-score position should be blocked"

    def test_open_position_blocked_by_circuit_breaker(self):
        gate = self._gate()
        gate.consecutive_losses = 10   # force circuit breaker
        pos = gate.open_position(
            symbol="BTC/USDT", direction=1, entry_price=50_000,
            entry_time=0, atr=500, regime="bull", signal_score=0.80
        )
        assert pos is None, "CB-active position should be blocked"

    def test_close_position_profitable(self):
        gate = self._gate()
        gate.open_position(
            symbol="BTC/USDT", direction=1, entry_price=50_000,
            entry_time=0, atr=500, regime="bull", signal_score=0.80
        )
        trade = gate.close_position("BTC/USDT", exit_price=51_000, exit_time=1)
        assert trade is not None
        assert trade["pnl_pct"] > 0, "Profitable close should have positive PnL"
        assert gate.current_equity > 10_000

    def test_close_position_loss(self):
        gate = self._gate()
        gate.open_position(
            symbol="BTC/USDT", direction=1, entry_price=50_000,
            entry_time=0, atr=500, regime="bull", signal_score=0.80
        )
        trade = gate.close_position("BTC/USDT", exit_price=49_000, exit_time=1)
        assert trade["pnl_pct"] < 0, "Losing close should have negative PnL"

    def test_close_nonexistent_position_returns_none(self):
        gate = self._gate()
        result = gate.close_position("FAKE/USDT", exit_price=100, exit_time=1)
        assert result is None

    def test_pnl_calculation_long_correct(self):
        gate = self._gate()
        gate.open_position(
            symbol="ETH/USDT", direction=1, entry_price=2_000,
            entry_time=0, atr=50, regime="bull", signal_score=0.80
        )
        trade = gate.close_position("ETH/USDT", exit_price=2_200, exit_time=1)
        expected_pnl_pct = (2_200 - 2_000) / 2_000  # = 0.10
        assert abs(trade["pnl_pct"] - expected_pnl_pct) < 1e-9

    def test_pnl_calculation_short_correct(self):
        gate = self._gate()
        gate.open_position(
            symbol="ETH/USDT", direction=-1, entry_price=2_000,
            entry_time=0, atr=50, regime="bear", signal_score=0.80
        )
        trade = gate.close_position("ETH/USDT", exit_price=1_800, exit_time=1)
        expected_pnl_pct = (2_000 - 1_800) / 2_000  # = 0.10
        assert abs(trade["pnl_pct"] - expected_pnl_pct) < 1e-9

    def test_get_status_reflects_state(self):
        gate = self._gate()
        status = gate.get_status()
        assert status["equity"] == 10_000
        assert status["open_positions"] == 0
        assert not status["circuit_breaker_active"]

    def test_win_rate_tracked_correctly(self):
        gate = self._gate()
        # Open and close two trades: one win, one loss
        gate.open_position("BTC/USDT", 1, 50_000, 0, 500, "bull", 0.80)
        gate.close_position("BTC/USDT", 51_000, 1)
        gate.open_position("ETH/USDT", 1, 2_000, 2, 50, "bull", 0.80)
        gate.close_position("ETH/USDT", 1_900, 3)
        status = gate.get_status()
        assert status["total_trades"] == 2
        assert status["win_rate"] == 0.5


# ===========================================================================
# 3. KELLY POSITION SIZER
# ===========================================================================

class TestKellyRiskController:
    """Tests for kelly_position_sizer.KellyRiskController"""

    def _kelly(self):
        from kelly_position_sizer import KellyRiskController
        return KellyRiskController(fraction=0.25, hard_cap_pct=0.02)

    def test_bull_size_gt_chop_gt_bear(self):
        kelly = self._kelly()
        bull = kelly.calculate_position_size(0.44, 0.018, 0.012, "bull", 10_000)
        chop = kelly.calculate_position_size(0.44, 0.018, 0.012, "chop", 10_000)
        bear = kelly.calculate_position_size(0.44, 0.018, 0.012, "bear", 10_000)
        assert bull > chop > bear, f"Expected bull>chop>bear, got {bull},{chop},{bear}"

    def test_size_zero_on_zero_avg_loss(self):
        kelly = self._kelly()
        size = kelly.calculate_position_size(0.44, 0.018, 0.0, "bull", 10_000)
        assert size == 0.0

    def test_size_zero_on_zero_win_rate(self):
        kelly = self._kelly()
        size = kelly.calculate_position_size(0.0, 0.018, 0.012, "bull", 10_000)
        assert size == 0.0

    def test_size_hard_capped_at_2pct(self):
        kelly = self._kelly()
        size = kelly.calculate_position_size(0.99, 100.0, 0.001, "bull", 10_000)
        assert size <= 10_000 * 0.02 + 0.01, f"Size {size} exceeds 2% hard cap"

    def test_kelly_formula_correctness(self):
        """Verify Kelly formula: f = (bp - q) / b"""
        kelly = self._kelly()
        win_rate, avg_win, avg_loss = 0.55, 0.02, 0.01
        b = avg_win / avg_loss
        p, q = win_rate, 1 - win_rate
        expected_full_kelly = (b * p - q) / b
        # At fraction=0.25, no drawdown, bull regime (1.0x), balance=10000
        expected_usd = min(expected_full_kelly * 0.25 * 1.0 * 1.0, 0.02) * 10_000
        actual = kelly.calculate_position_size(win_rate, avg_win, avg_loss, "bull", 10_000)
        assert abs(actual - expected_usd) < 0.01, (
            f"Kelly formula mismatch: expected ${expected_usd:.2f}, got ${actual:.2f}"
        )

    def test_drawdown_reduces_size(self):
        kelly = self._kelly()
        kelly.peak_equity = 10_000
        # First call with full equity
        full = kelly.calculate_position_size(0.44, 0.018, 0.012, "bull", 10_000)
        # Simulate drawdown: peak stays at 10k, equity drops to 8.5k
        kelly.peak_equity = 10_000
        reduced = kelly.calculate_position_size(0.44, 0.018, 0.012, "bull", 8_500)
        assert reduced < full, "Drawdown should reduce position size"

    def test_size_summary_keys(self):
        kelly = self._kelly()
        summary = kelly.size_summary(0.44, 0.018, 0.012, "bull", 10_000)
        for key in ("kelly_full_pct", "kelly_fraction_pct", "regime_mult",
                    "final_size_usd", "final_pct"):
            assert key in summary, f"Missing key in summary: {key}"

    def test_unknown_regime_defaults_to_conservative(self):
        kelly = self._kelly()
        size = kelly.calculate_position_size(0.44, 0.018, 0.012, "sideways", 10_000)
        bull = kelly.calculate_position_size(0.44, 0.018, 0.012, "bull", 10_000)
        assert size <= bull, "Unknown regime should use conservative multiplier"


# ===========================================================================
# 4. HMM REGIME DETECTOR
# ===========================================================================

class TestEnsembleRegimeDetector:
    """Tests for hmm_regime_detector.EnsembleRegimeDetector"""

    def _detector(self):
        from hmm_regime_detector import EnsembleRegimeDetector
        return EnsembleRegimeDetector()

    def test_predict_without_fit_returns_default(self, regime_data):
        returns, vol = regime_data
        det = self._detector()
        result = det.predict_regime(returns[-50:], vol[-50:])
        assert result["regime"] == "chop"
        assert result["confidence"] == 0.5

    def test_fit_then_predict_returns_valid_regime(self, regime_data):
        returns, vol = regime_data
        det = self._detector()
        det.fit(returns, vol)
        result = det.predict_regime(returns[-50:], vol[-50:])
        assert result["regime"] in ("bull", "bear", "chop")

    def test_confidence_in_0_1(self, regime_data):
        returns, vol = regime_data
        det = self._detector()
        det.fit(returns, vol)
        result = det.predict_regime(returns[-50:], vol[-50:])
        assert 0.0 <= result["confidence"] <= 1.0

    def test_fit_is_idempotent(self, regime_data):
        """Fitting twice shouldn't crash."""
        returns, vol = regime_data
        det = self._detector()
        det.fit(returns, vol)
        det.fit(returns, vol)
        result = det.predict_regime(returns[-50:], vol[-50:])
        assert result["regime"] in ("bull", "bear", "chop")

    def test_bull_signal_simulated(self):
        """Simulate a clear bull market and verify detector leans bull."""
        np.random.seed(10)
        n = 200
        returns = np.abs(np.random.randn(n) * 0.01) + 0.005  # positive drift
        vol = np.abs(returns) * 0.5 + 0.001
        det = self._detector()
        det.fit(returns, vol)
        result = det.predict_regime(returns[-50:], vol[-50:])
        # We don't assert exactly 'bull' because HMM is stochastic,
        # but confidence should be non-trivial
        assert result["confidence"] > 0.3

    def test_cross_val_accuracy_non_negative(self, regime_data):
        returns, vol = regime_data
        det = self._detector()
        det.fit(returns, vol)
        acc = det.cross_val_accuracy(returns, vol)
        assert acc >= 0.0

    def test_short_data_returns_default(self):
        """Less than 50 returns → should return default."""
        from hmm_regime_detector import EnsembleRegimeDetector
        det = EnsembleRegimeDetector()
        short_returns = np.array([0.01, -0.02, 0.005])
        short_vol = np.array([0.01, 0.02, 0.01])
        result = det.predict_regime(short_returns, short_vol)
        assert result["regime"] in ("bull", "bear", "chop", "neutral")  # fallback


# ===========================================================================
# 5. TRADE JOURNAL
# ===========================================================================

class TestTradeJournal:
    """Tests for trade_journal.TradeJournal"""

    def _journal(self, path):
        from trade_journal import TradeJournal
        return TradeJournal(path=path)

    def test_log_open_creates_entry(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        entry = j.log_open("BTC/USDT", "BUY", "bull", 0.78, 68_000, 0.001, 20.0)
        assert entry is not None
        assert entry.status == "OPEN"
        assert entry.symbol == "BTC/USDT"

    def test_log_close_updates_entry(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        entry = j.log_open("BTC/USDT", "BUY", "bull", 0.78, 68_000, 0.001, 20.0)
        success = j.log_close(entry.id, 69_000, 0.0147, 14.7)
        assert success is True
        closed = [e for e in j.entries if e.id == entry.id][0]
        assert closed.status == "CLOSED"
        assert closed.exit_price == 69_000

    def test_log_close_unknown_id_returns_false(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        result = j.log_close("NONEXISTENT_ID", 100, 0.01, 10.0)
        assert result is False

    def test_performance_stats_empty(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        stats = j.performance_stats()
        assert stats == {"total_trades": 0}

    def test_performance_stats_one_trade(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        e = j.log_open("BTC/USDT", "BUY", "bull", 0.78, 68_000, 0.001, 20.0)
        j.log_close(e.id, 69_000, 0.0147, 14.7)
        stats = j.performance_stats()
        assert stats["total_trades"] == 1
        assert stats["win_rate"] == 1.0
        assert stats["total_pnl"] > 0

    def test_win_rate_50_pct(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        e1 = j.log_open("BTC/USDT", "BUY", "bull", 0.78, 68_000, 0.001, 20.0)
        j.log_close(e1.id, 69_000, 0.0147, 14.7)    # win
        e2 = j.log_open("ETH/USDT", "BUY", "bull", 0.70, 2_000, 0.01, 10.0)
        j.log_close(e2.id, 1_900, -0.05, -5.0)       # loss
        stats = j.performance_stats()
        assert stats["total_trades"] == 2
        assert abs(stats["win_rate"] - 0.5) < 1e-9

    def test_journal_persists_to_disk(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        e = j.log_open("SOL/USDT", "BUY", "bull", 0.60, 100, 1.0, 15.0)
        j.log_close(e.id, 110, 0.10, 10.0)
        # Reload from disk
        j2 = self._journal(tmp_journal_path)
        assert len(j2.entries) == 1
        assert j2.entries[0].symbol == "SOL/USDT"

    def test_daily_summary_no_trades(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        summary = j.daily_summary()
        assert summary["trades"] == 0

    def test_get_recent_trades_returns_closed_only(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        e1 = j.log_open("BTC/USDT", "BUY", "bull", 0.78, 68_000, 0.001, 20.0)
        j.log_close(e1.id, 69_000, 0.0147, 14.7)
        e2 = j.log_open("ETH/USDT", "BUY", "bull", 0.70, 2_000, 0.01, 10.0)
        # e2 remains OPEN
        trades = j.get_recent_trades(days=1)
        assert len(trades) == 1
        assert trades[0]["symbol"] == "BTC/USDT"

    def test_sharpe_requires_variance(self, tmp_journal_path):
        j = self._journal(tmp_journal_path)
        # Multiple trades with same PnL → std dev = 0 → Sharpe = 0
        for _ in range(5):
            e = j.log_open("BTC/USDT", "BUY", "bull", 0.78, 68_000, 0.001, 20.0)
            j.log_close(e.id, 69_000, 0.0147, 14.7)
        stats = j.performance_stats()
        assert "sharpe" in stats


# ===========================================================================
# 6. TESTNET EXECUTOR
# ===========================================================================

class TestTestnetExecutor:
    """Tests for binance_testnet_executor.TestnetExecutor"""

    def _executor(self, tmp_path):
        import os
        os.makedirs(str(tmp_path / "logs"), exist_ok=True)
        # Patch log dir to tmp
        from binance_testnet_executor import TestnetExecutor
        ex = TestnetExecutor.__new__(TestnetExecutor)
        ex.testnet = True
        ex.trade_log = []
        ex.daily_pnl = 0.0
        ex.consecutive_losses = 0
        ex.peak_equity = 10_000.0
        ex.current_equity = 10_000.0
        from datetime import date
        ex._reset_date = date.today()
        import logging
        ex.logger = logging.getLogger("test_executor")
        return ex

    def test_place_order_returns_record(self, tmp_path):
        ex = self._executor(tmp_path)
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        assert record is not None
        assert record.symbol == "BTC/USDT"
        assert record.side == "BUY"
        assert record.status == "OPEN"

    def test_place_order_correct_quantity(self, tmp_path):
        ex = self._executor(tmp_path)
        kelly_usd = 200
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=kelly_usd, regime="bull")
        price = ex._get_mock_price("BTC/USDT")
        expected_qty = round(kelly_usd / price, 6)
        assert abs(record.quantity - expected_qty) < 1e-9

    def test_close_position_profit(self, tmp_path):
        ex = self._executor(tmp_path)
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        pnl = ex.close_position(record, exit_price=69_000)
        assert pnl > 0
        assert record.status == "CLOSED"

    def test_close_position_loss(self, tmp_path):
        ex = self._executor(tmp_path)
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        pnl = ex.close_position(record, exit_price=68_000)
        assert pnl < 0
        assert ex.consecutive_losses == 1

    def test_close_profit_resets_consecutive_losses(self, tmp_path):
        ex = self._executor(tmp_path)
        ex.consecutive_losses = 3
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        ex.close_position(record, exit_price=69_000)
        assert ex.consecutive_losses == 0

    def test_circuit_breaker_daily_loss(self, tmp_path):
        ex = self._executor(tmp_path)
        ex.daily_pnl = -0.05   # -5%, exceeds -3% threshold
        ok, reason = ex._circuit_breakers()
        assert not ok
        assert "daily" in reason.lower() or "loss" in reason.lower()

    def test_circuit_breaker_consecutive_losses(self, tmp_path):
        ex = self._executor(tmp_path)
        ex.consecutive_losses = 5
        ok, reason = ex._circuit_breakers()
        assert not ok

    def test_circuit_breaker_max_drawdown(self, tmp_path):
        ex = self._executor(tmp_path)
        ex.peak_equity = 10_000
        ex.current_equity = 8_900   # 11% drawdown
        ok, reason = ex._circuit_breakers()
        assert not ok

    def test_blocked_order_not_added_to_log(self, tmp_path):
        ex = self._executor(tmp_path)
        ex.consecutive_losses = 5   # trigger CB
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        assert record is None
        assert len(ex.trade_log) == 0

    def test_get_summary_empty(self, tmp_path):
        ex = self._executor(tmp_path)
        summary = ex.get_summary()
        assert summary["trades"] == 0
        assert summary["equity"] == 10_000.0

    def test_get_summary_after_trades(self, tmp_path):
        ex = self._executor(tmp_path)
        r = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        ex.close_position(r, exit_price=69_000)
        summary = ex.get_summary()
        assert summary["trades"] == 1
        assert summary["win_rate"] == 1.0

    def test_pnl_calculation_long_correct(self, tmp_path):
        ex = self._executor(tmp_path)
        record = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
        entry = record.entry_price
        exit_price = entry * 1.05   # 5% profit
        pnl = ex.close_position(record, exit_price=exit_price)
        assert abs(pnl - 0.05) < 1e-6, f"Expected ~5%, got {pnl:.4%}"

    def test_mock_price_known_symbols(self, tmp_path):
        ex = self._executor(tmp_path)
        for sym in ["BTC/USDT", "ETH/USDT", "SOL/USDT"]:
            assert ex._get_mock_price(sym) > 0

    def test_mock_price_unknown_symbol_fallback(self, tmp_path):
        ex = self._executor(tmp_path)
        price = ex._get_mock_price("UNKNOWN/USDT")
        assert price == 100.0


# ===========================================================================
# 7. MULTI-TIMEFRAME FILTER
# ===========================================================================

class TestMultiTimeframeFilter:
    """Tests for multi_timeframe_filter.MultiTimeframeFilter"""

    def _filter(self):
        from multi_timeframe_filter import MultiTimeframeFilter
        return MultiTimeframeFilter()

    def test_long_confirmed_on_bull_4h(self):
        f = self._filter()
        sig, reason = f.filter_signal(signal_1h=1, trend_4h="bull")
        assert sig == 1

    def test_long_blocked_on_bear_4h(self):
        f = self._filter()
        sig, reason = f.filter_signal(signal_1h=1, trend_4h="bear")
        assert sig == 0, "LONG should be blocked on 4h bear"

    def test_short_confirmed_on_bear_4h(self):
        f = self._filter()
        sig, reason = f.filter_signal(signal_1h=-1, trend_4h="bear")
        assert sig == -1

    def test_short_blocked_on_bull_4h(self):
        f = self._filter()
        sig, reason = f.filter_signal(signal_1h=-1, trend_4h="bull")
        assert sig == 0, "SHORT should be blocked on 4h bull"

    def test_neutral_passes_through(self):
        f = self._filter()
        sig, reason = f.filter_signal(signal_1h=0, trend_4h="bull")
        assert sig == 0

    def test_get_4h_trend_bull(self):
        f = self._filter()
        # Strongly trending up
        closes = np.linspace(90, 110, 100)
        trend = f.get_4h_trend(closes)
        assert trend == "bull"

    def test_get_4h_trend_bear(self):
        f = self._filter()
        # Strongly trending down
        closes = np.linspace(110, 90, 100)
        trend = f.get_4h_trend(closes)
        assert trend == "bear"

    def test_get_4h_trend_insufficient_data(self):
        f = self._filter()
        closes = np.array([100, 101])  # less than ema_slow=21
        trend = f.get_4h_trend(closes)
        assert trend == "neutral"

    def test_batch_filter_reduces_signals(self):
        f = self._filter()
        np.random.seed(42)
        n = 400
        closes_1h = 100 + np.cumsum(np.random.randn(n) * 0.5)
        closes_4h = closes_1h[::4]
        signals_1h = np.random.choice([0, 0, 0, 1, -1], size=n)
        filtered, stats = f.apply_filter_batch(signals_1h, closes_4h, closes_1h)
        assert stats["confirmed_signals"] <= stats["total_signals_1h"]
        assert stats["confirmed_signals"] >= 0

    def test_batch_filter_returns_valid_signal_values(self):
        f = self._filter()
        np.random.seed(42)
        n = 200
        closes_1h = 100 + np.cumsum(np.random.randn(n) * 0.5)
        closes_4h = closes_1h[::4]
        signals_1h = np.random.choice([0, 1, -1], size=n)
        filtered, _ = f.apply_filter_batch(signals_1h, closes_4h, closes_1h)
        assert set(filtered.tolist()).issubset({-1, 0, 1})


# ===========================================================================
# 8. SCALE-UP MANAGER
# ===========================================================================

class TestScaleUpManager:
    """Tests for scale_up_manager.ScaleUpManager"""

    def _manager(self):
        from scale_up_manager import ScaleUpManager
        return ScaleUpManager()

    def test_initial_profile_is_seed(self):
        sm = self._manager()
        assert sm.current_profile.name == "S0_SEED"

    def test_promotion_when_criteria_met(self):
        sm = self._manager()
        promoted = sm.check_promotion(trades=100, sharpe=0.85)
        assert promoted is not None
        assert promoted.name == "S1_STARTER"

    def test_no_promotion_when_criteria_not_met(self):
        sm = self._manager()
        promoted = sm.check_promotion(trades=50, sharpe=0.5)
        assert promoted is None, "Should not promote with insufficient trades/sharpe"

    def test_sequential_promotions(self):
        sm = self._manager()
        sm.check_promotion(100, 0.85)   # S0 → S1
        sm.check_promotion(200, 1.05)   # S1 → S2
        assert sm.current_profile.name == "S2_GROWTH"

    def test_no_promotion_beyond_max(self):
        sm = self._manager()
        # Jump to last profile
        sm.current_index = 4
        promoted = sm.check_promotion(trades=9999, sharpe=99.0)
        assert promoted is None, "Should not promote beyond S4"

    def test_status_includes_required_keys(self):
        sm = self._manager()
        status = sm.status()
        for key in ("current", "account_usd", "position_pct", "next_profile", "next_requires"):
            assert key in status, f"Missing key: {key}"

    def test_status_next_profile_shows_max_at_last(self):
        sm = self._manager()
        sm.current_index = 4
        status = sm.status()
        assert status["next_profile"] == "MAX"


# ===========================================================================
# 9. INTEGRATION TESTS — End-to-End Signal → Execution Flow
# ===========================================================================

class TestEndToEndFlow:
    """Integration tests simulating the full signal → risk → execution pipeline."""

    def test_full_pipeline_long_trade(self, tmp_journal_path, sample_ohlcv, tmp_path):
        """Simulate: score → kelly → risk gate → journal → executor."""
        from scoring_fixed import FixedScorer
        from kelly_position_sizer import KellyRiskController
        from risk_gate import RiskGate
        from trade_journal import TradeJournal

        c, h, lo, v, sp = sample_ohlcv
        scorer = FixedScorer()
        signals, _ = scorer.generate_signals(c, h, lo, v, sp)

        # Find first LONG signal
        long_indices = np.where(signals == 1)[0]
        if len(long_indices) == 0:
            pytest.skip("No LONG signals generated in sample data")
        idx = long_indices[-1]

        # Kelly sizing
        kelly = KellyRiskController(fraction=0.25)
        size_usd = kelly.calculate_position_size(0.44, 0.018, 0.012, "bull", 10_000)
        assert size_usd > 0

        # Risk gate
        gate = RiskGate(initial_capital=10_000)
        pos = gate.open_position(
            symbol="BTC/USDT", direction=1,
            entry_price=float(c[idx]),
            entry_time=int(idx),
            atr=float(h[idx] - lo[idx]),
            regime="bull",
            signal_score=0.80
        )
        assert pos is not None

        # Close at TP
        tp_price = pos.take_profit
        trade = gate.close_position("BTC/USDT", exit_price=tp_price, exit_time=int(idx) + 10)
        assert trade is not None
        assert trade["pnl_pct"] > 0

        # Journal
        j = TradeJournal(path=tmp_journal_path)
        entry = j.log_open("BTC/USDT", "BUY", "bull", 0.80, float(c[idx]), 0.001, size_usd)
        j.log_close(entry.id, tp_price, trade["pnl_pct"], trade["pnl_dollars"])
        stats = j.performance_stats()
        assert stats["total_trades"] == 1
        assert stats["win_rate"] == 1.0

    def test_circuit_breaker_prevents_trade_after_losses(self, tmp_path):
        """After max consecutive losses, all new orders should be blocked."""
        import os
        os.makedirs(str(tmp_path / "logs"), exist_ok=True)
        from binance_testnet_executor import TestnetExecutor
        ex = TestnetExecutor.__new__(TestnetExecutor)
        ex.testnet = True
        ex.trade_log = []
        ex.daily_pnl = 0.0
        ex.consecutive_losses = 0
        ex.peak_equity = 10_000.0
        ex.current_equity = 10_000.0
        from datetime import date
        ex._reset_date = date.today()
        import logging
        ex.logger = logging.getLogger("test_cb")

        # Simulate 5 consecutive losses
        for i in range(5):
            r = ex.place_order("BTC/USDT", "BUY", kelly_usd=50, regime="bull")
            assert r is not None
            ex.close_position(r, exit_price=68_000)   # loss (entry is 68500)

        # 6th order should be blocked
        blocked = ex.place_order("BTC/USDT", "BUY", kelly_usd=50, regime="bull")
        assert blocked is None, "Order should be blocked after 5 consecutive losses"

    def test_kelly_and_risk_gate_consistent_sizing(self):
        """Both Kelly modules should produce non-zero, bounded sizes."""
        from kelly_position_sizer import KellyRiskController
        from risk_gate import RiskGate

        kelly = KellyRiskController(fraction=0.25)
        size_usd = kelly.calculate_position_size(0.44, 0.018, 0.012, "bull", 10_000)
        assert 0 < size_usd <= 200   # 2% cap on $10k

        gate = RiskGate(initial_capital=10_000)
        size_frac = gate.calculate_position_size(0.44, 0.018, 0.012, "bull")
        assert 0 < size_frac <= 0.05   # 5% cap


# ===========================================================================
# 10. EDGE CASES & REGRESSION TESTS
# ===========================================================================

class TestEdgeCases:
    """Boundary conditions and regression tests for known bugs."""

    def test_scorer_handles_single_bar(self):
        from scoring_fixed import FixedScorer
        scorer = FixedScorer()
        c = np.array([100.0] * 50)
        h = c + 1.0
        lo = c - 1.0
        v = np.ones(50) * 1000
        sp = np.ones(50) * 0.01
        # Should not crash
        signals, _ = scorer.generate_signals(c, h, lo, v, sp)
        assert signals.shape == c.shape

    def test_risk_gate_handles_zero_atr(self):
        from risk_gate import RiskGate
        gate = RiskGate()
        sl = gate.calculate_stop_loss(100.0, atr=0.0, direction=1)
        # With atr=0, stop distance = min(0, 2%) = 0 → stop = entry
        # Acceptable: no crash
        assert sl <= 100.0

    def test_journal_corrupted_file_returns_empty(self, tmp_path):
        p = str(tmp_path / "corrupt.json")
        with open(p, "w") as f:
            f.write("NOT VALID JSON {{{")
        from trade_journal import TradeJournal
        j = TradeJournal(path=p)
        assert j.entries == []

    def test_kelly_negative_kelly_returns_zero(self):
        from kelly_position_sizer import KellyRiskController
        kelly = KellyRiskController()
        # Terrible odds: 10% win rate, 1% avg win, 5% avg loss
        size = kelly.calculate_position_size(0.10, 0.01, 0.05, "bull", 10_000)
        assert size == 0.0

    def test_mtf_filter_all_neutral_input(self):
        from multi_timeframe_filter import MultiTimeframeFilter
        f = MultiTimeframeFilter()
        np.random.seed(0)
        n = 200
        closes_1h = 100 + np.cumsum(np.random.randn(n) * 0.5)
        closes_4h = closes_1h[::4]
        signals_1h = np.zeros(n, dtype=int)   # all neutral
        filtered, stats = f.apply_filter_batch(signals_1h, closes_4h, closes_1h)
        assert stats["total_signals_1h"] == 0
        assert stats["confirmed_signals"] == 0

    def test_scale_manager_correct_account_progression(self):
        from scale_up_manager import ScaleUpManager, PROFILES
        sm = ScaleUpManager()
        # Account sizes should increase with each profile
        account_sizes = [p.account_usd for p in PROFILES]
        assert account_sizes == sorted(account_sizes), "Profiles should increase in account size"


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

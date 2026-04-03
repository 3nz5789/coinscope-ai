"""
CoinScopeAI System Tests - Master Test Runner

Run all system tests in sequence.
Usage: python run_tests.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.makedirs("logs", exist_ok=True)

results = {}


def test(name: str, fn):
    """Run a single test"""
    print(f"\n{'─' * 50}")
    print(f"TEST: {name}")
    print("─" * 50)
    try:
        t0 = time.time()
        fn()
        elapsed = time.time() - t0
        results[name] = ("✅ PASS", round(elapsed, 2))
        print(f"✅ PASSED ({elapsed:.2f}s)")
    except Exception as e:
        results[name] = ("❌ FAIL", str(e))
        print(f"❌ FAILED: {e}")


def test_scoring():
    """Test scoring engine"""
    import numpy as np

    from core.scoring_fixed import FixedScorer

    np.random.seed(42)
    n = 500
    c = 100 + np.cumsum(np.random.randn(n) * 0.5)
    h = c + np.abs(np.random.randn(n) * 0.3)
    lo = c - np.abs(np.random.randn(n) * 0.3)
    v = np.random.uniform(1000, 5000, n)
    sp = np.random.uniform(0.001, 0.01, n)
    scorer = FixedScorer()
    signals, sub_scores = scorer.generate_signals(c, h, lo, v, sp)
    longs = int((signals == 1).sum())
    shorts = int((signals == -1).sum())
    print(f"  LONG: {longs} | SHORT: {shorts} | NEUTRAL: {n - longs - shorts}")
    assert longs + shorts > 0, "No signals generated"


def test_risk_gate():
    """Test risk gate"""
    from core.risk_gate import RiskGate

    gate = RiskGate(initial_capital=10000)
    size = gate.calculate_position_size(
        win_rate=0.44,
        avg_win=0.018,
        avg_loss=0.012,
        regime="bull",
    )
    print(f"  Risk gate position size: ${size:.2f}")
    assert size > 0


def test_regime():
    """Test HMM regime detector"""
    import numpy as np

    from intelligence.hmm_regime_detector import EnsembleRegimeDetector

    np.random.seed(0)
    returns = np.random.randn(200) * 0.02
    vol = np.abs(returns) + 0.01
    det = EnsembleRegimeDetector()
    det.fit(returns, vol)
    result = det.predict_regime(returns[-50:], vol[-50:])
    print(f"  Regime: {result['regime']} ({result['confidence']:.0%})")
    assert result["regime"] in ("bull", "bear", "chop")


def test_kelly():
    """Test Kelly position sizer"""
    from intelligence.kelly_position_sizer import KellyRiskController

    kelly = KellyRiskController(fraction=0.25)
    for regime in ["bull", "chop", "bear"]:
        size = kelly.calculate_position_size(0.44, 0.018, 0.012, regime, 10000)
        print(f"  {regime:4s}: ${size:.2f}")
    assert size > 0


def test_journal():
    """Test trade journal"""
    from storage.trade_journal import TradeJournal

    j = TradeJournal(path="logs/test_journal.json")
    entry = j.log_open(
        "BTC/USDT", "BUY", "bull", 0.78, 68000, 0.001, 20.0, signal_score=2.5
    )
    j.log_close(entry.id, 69000, 0.0147, 14.7)
    stats = j.performance_stats()
    print(f"  Stats: {stats}")
    assert stats["total_trades"] >= 1
    if os.path.exists("logs/test_journal.json"):
        os.remove("logs/test_journal.json")


def test_executor():
    """Test testnet executor"""
    from live.binance_testnet_executor import TestnetExecutor

    ex = TestnetExecutor()
    rec = ex.place_order("BTC/USDT", "BUY", kelly_usd=20, regime="bull", signal_score=2.5)
    assert rec is not None
    pnl = ex.close_position(rec, exit_price=69000)
    summary = ex.get_summary()
    print(f"  PnL: {pnl:+.2%} | Summary: {summary}")


def test_scale_manager():
    """Test scale-up manager"""
    from alerts.scale_up_manager import ScaleUpManager

    sm = ScaleUpManager()
    print(f"  Current: {sm.status()['current']}")
    promoted = sm.check_promotion(trades=100, sharpe=0.85)
    print(f"  Promoted: {promoted.name if promoted else 'No'}")
    assert sm.current_profile is not None


def test_api_import():
    """Test FastAPI import"""
    import importlib

    spec = importlib.util.find_spec("fastapi")
    assert spec is not None, "FastAPI not installed"
    print("  FastAPI import OK")


# ── Run all tests ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print(" CoinScopeAI System Tests")
    print("=" * 50)

    test("Scoring Engine", test_scoring)
    test("Risk Gate", test_risk_gate)
    test("HMM Regime", test_regime)
    test("Kelly Sizer", test_kelly)
    test("Trade Journal", test_journal)
    test("Testnet Executor", test_executor)
    test("Scale Manager", test_scale_manager)
    test("FastAPI Import", test_api_import)

    print("\n" + "=" * 50)
    print(" TEST RESULTS")
    print("=" * 50)
    passed = sum(1 for v in results.values() if v[0].startswith("✅"))
    total = len(results)
    for name, (status, detail) in results.items():
        print(f" {status}  {name:25s}  {detail}")
    print("-" * 50)
    print(f" {passed}/{total} PASSED")
    print("=" * 50)

    exit(0 if passed == total else 1)

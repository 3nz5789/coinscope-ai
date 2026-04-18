# CoinScopeAI — Full System Audit Report
**Date:** 2026-04-02
**Files reviewed:** 19 Python modules + Dockerfile
**Auditor:** Claude (automated static analysis + logic review)

---

## 1. Architectural Summary

CoinScopeAI is a crypto futures signal engine that runs a 4-hour polling loop across 6 pairs (BTC, ETH, SOL, BNB, XRP, TAO). The system is organized in several layers:

```
┌─────────────────────────────────────────────────────────┐
│                     API Layer (api.py)                   │
│   FastAPI REST bridge → React frontend (port 8001)       │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│             Orchestration (master_orchestrator.py)        │
│  CoinScopeOrchestrator.run_loop() / run_scan()           │
│  Polls PAIRS every 4h; coordinates all sub-modules       │
└──────┬──────────┬──────────┬────────────┬───────────────┘
       │          │          │            │
┌──────▼──┐ ┌────▼────┐ ┌───▼───┐ ┌─────▼──────┐
│ Scoring  │ │  HMM    │ │ Kelly │ │   Whale    │
│ Engine   │ │ Regime  │ │ Sizer │ │  Filter    │
│(0-12 pts)│ │Detector │ │(USD)  │ │(on-chain)  │
└──────────┘ └─────────┘ └───────┘ └────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│              Execution Layer                             │
│  RiskGate ←→ TestnetExecutor ←→ TradeJournal            │
└─────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│              Monitoring / Ops Layer                      │
│  MetricsExporter (Prometheus) | TelegramAlerts           │
│  AlphaDecayMonitor | WeeklyRetrainer | ScaleUpManager   │
└─────────────────────────────────────────────────────────┘
```

**Signal Flow (per pair, per 4h candle):**
1. Fetch 300 × 4h OHLCV bars from Binance
2. HMM + Random Forest → regime classification (bull / bear / chop)
3. FixedScorer (RSI, EMA, ATR, volume, entry timing, spread) → 0-12 score → signal (LONG/SHORT/NEUTRAL)
4. MockSentimentFilter → block if sentiment opposes
5. WhaleSignalFilter → block if on-chain whale flow opposes
6. KellyRiskController → position size in USD
7. Output result dict for API / Telegram / executor

---

## 2. Detected Issues

### 🔴 CRITICAL — Will crash or produce silently wrong results

---

**[BUG-1] `master_orchestrator.py` line 29 — Missing module `finbert_sentiment_filter`**
```python
from intelligence.finbert_sentiment_filter import MockSentimentFilter
```
This file is not present in the codebase. The orchestrator will raise `ImportError` at startup. Every run of `master_orchestrator.py` or any `/scan` API call will immediately fail.

**Fix:** Create a minimal stub file `intelligence/finbert_sentiment_filter.py` with:
```python
class MockSentimentFilter:
    def should_block(self, direction, data):
        return False, "Sentiment filter disabled"
```

---

**[BUG-2] `scoring_fixed.py` lines 289-290 — LONG/SHORT threshold overlap overwrites signals**
```python
signals[total_score >= long_threshold] = 1      # LONG when score >= 5.5
signals[total_score <= short_threshold] = -1    # SHORT when score <= 6.5
```
Any bar with a total score in the range **[5.5, 6.5]** is first tagged as LONG, then immediately overwritten to SHORT. This means moderate-scoring bars always emit SHORT signals, never LONG — the signal polarity is inverted for a whole band of scores. This is a critical logic bug that corrupts signal quality.

**Fix:** Use non-overlapping thresholds, e.g.:
```python
signals[total_score >= 8.0] = 1      # Strong LONG: top 1/3 of range
signals[total_score <= 4.0] = -1     # Strong SHORT: bottom 1/3 of range
# Scores 4-8 = NEUTRAL (no trade)
```

---

**[BUG-3] `api.py` line 61 — Setting `orch.PAIRS` has no effect**
```python
orch.PAIRS = pair_list   # sets instance attribute
# but run_scan() uses the MODULE-LEVEL constant:
for pair in PAIRS:       # ← reads module constant, ignores orch.PAIRS
```
The `/scan` endpoint's `pairs` query parameter is silently ignored. The API always scans the hardcoded 6 pairs regardless of what the caller requests.

**Fix:** In `master_orchestrator.py`, change `run_scan()` to use `self.pairs` and set it in `__init__`:
```python
def __init__(self, testnet=True, pairs=None):
    self.pairs = pairs or PAIRS

def run_scan(self):
    for pair in self.pairs:   # ← use self.pairs
        ...
```

---

**[BUG-4] `binance_testnet_executor.py` line 54 — `logs/` directory not created before FileHandler**
```python
logging.FileHandler(f"logs/testnet_{datetime.now():%Y%m%d}.log")
```
If `logs/` doesn't exist, this raises `FileNotFoundError` during `__init__`, before any trading logic runs.

**Fix:** Add `os.makedirs("logs", exist_ok=True)` at the top of `_setup_logging()`, before the `FileHandler` line.

---

**[BUG-5] `risk_gate.py` lines 305-310 — Consecutive loss counter logic is wrong**
```python
if self.current_equity > self.peak_equity:
    self.peak_equity = self.current_equity
    self.consecutive_losses = 0   # ← resets on equity peak, not on win
else:
    self.consecutive_losses += 1  # ← increments even on profitable trades
```
A profitable trade that doesn't exceed the equity peak (e.g., partial recovery from a drawdown) will incorrectly increment `consecutive_losses`. The counter should track individual trade outcomes, not equity peaks.

**Fix:** Base the counter on the trade's own `pnl_pct`:
```python
if pnl_pct > 0:
    self.consecutive_losses = 0
else:
    self.consecutive_losses += 1
self.current_equity += pnl_dollars
self.peak_equity = max(self.peak_equity, self.current_equity)
```

---

**[BUG-6] `alpha_decay_monitor.py` lines 257, 271 — Calls non-existent methods on TelegramAlerts**
```python
await self.alerts.alert_error("Alpha Decay", msg)       # line 257
await self.alerts.alert_status_check(report['metrics']) # line 271
```
`TelegramAlerts` has no `alert_error` or `alert_status_check` methods. These calls will raise `AttributeError`. Additionally, all `TelegramAlerts` methods are synchronous (`def`), but are being `await`ed — this will raise `TypeError`.

**Fix:** Replace with existing methods:
```python
self.alerts.send_critical(msg)        # instead of await alert_error
self.alerts.send_heartbeat(report['metrics'])  # instead of await alert_status_check
```

---

**[BUG-7] `retrain_scheduler.py` lines 82, 185, 200 — Calls non-existent Telegram methods**
The retrainer calls `self.alerts.alert_signal(...)`, `self.alerts.alert_scale_up(...)` which don't exist in the `TelegramAlerts` class. The docstring says it expects a `TelegramAlertBot` (a different class with a different API), but the actual `TelegramAlerts` class is what exists in the codebase.

**Fix:** Either create a `TelegramAlertBot` adapter class, or replace calls with existing `TelegramAlerts` methods like `send_signal(...)` and `send_alert(...)`.

---

**[BUG-8] `alpha_decay_monitor.py` line 58 — Calls `await journal.get_trades()` on a synchronous class**
```python
trades_30d = await self.journal.get_trades(limit=500)
```
`TradeJournal` has no `get_trades()` method at all (it has `get_recent_trades(days=...)`), and none of its methods are `async`. This will raise `AttributeError`.

**Fix:** Replace with:
```python
trades_30d = self.journal.get_recent_trades(days=30)
```

---

**[BUG-9] `funding_rate_filter.py` — async wrapper over synchronous ccxt**
All methods are `async def`, but internally call `self.exchange.fetch_funding_rate()` — which is the synchronous ccxt API. Calling a blocking synchronous function inside an async method will block the event loop.

**Fix:** Either use `ccxt.async_support.binance` with `await self.exchange.fetch_funding_rate()`, or remove the `async` decorators and use the synchronous API consistently.

---

**[BUG-10] `master_orchestrator.py` — `self.mtf_filter` and `self.risk_gate` initialized but never used**
Both `MultiTimeframeFilter` and `RiskGate` are instantiated in `__init__` but never called in `scan_pair()`. The MTF filter and full risk gate circuit breakers are silently bypassed on every scan. Signal quality and risk controls are therefore weaker than the architecture implies.

---

### 🟡 MEDIUM — Logic errors that won't crash but produce incorrect results

---

**[BUG-11] `master_orchestrator.py` line 104 — Spread calculation produces wrong scale for liquidity scoring**
```python
spread = (h - lo) / c * 0.1   # dimensionless ratio ≈ 0.001
```
This spread is then passed to `score_liquidity()` which does `(bid_ask_spread / close) * 100`. The result is `(0.001 / 68500) * 100 ≈ 1.5e-6 %` — essentially zero. Every bar gets a liquidity score of 3 (best possible), permanently. The liquidity sub-score is meaningless.

**Fix:** Pass spread as an absolute price difference (e.g., 1-tick size in USD), or compute it as a true percentage that doesn't get divided by close again.

---

**[BUG-12] `scoring_fixed.py` line 84 — `np.roll` wraps around for first bar's ATR**
```python
tr = np.maximum(high - low,
    np.maximum(np.abs(high - np.roll(close, 1)), ...))
```
`np.roll(close, 1)` at index 0 uses `close[-1]` (last element), creating a spurious True Range for the first bar. This makes ATR and ATR-based sub-scores incorrect for the warm-up period.

**Fix:** Set `tr[0] = high[0] - low[0]` explicitly after computing the array.

---

**[BUG-13] `trade_journal.py` line 144 — Hardcoded `10000` initial capital in equity curve**
```python
equity = np.cumsum(pnls) + 10000
```
If the actual account starts at a different size, drawdown and Sharpe calculations will be wrong.

**Fix:** Pass `initial_capital` as a constructor parameter and use it here.

---

**[BUG-14] `alpha_decay_monitor.py` line 184 — Sharpe annualization factor is wrong**
```python
daily_sharpe = mean_pnl / std_pnl
return daily_sharpe * np.sqrt(365)  # comment says "4 trades per day"
```
If there are ~4 trades per day, the correct factor is `np.sqrt(365 * 4)` = `np.sqrt(1460)`. Using `np.sqrt(365)` underestimates the Sharpe ratio by ~2×.

---

**[BUG-15] `scale_up_manager.py` — State not persisted across restarts**
`current_index` resets to 0 (S0_SEED) every time the API server restarts. After a promotion to S3, restarting the server drops back to S0.

**Fix:** Persist `current_index` to a small JSON file or environment variable.

---

**[BUG-16] Two conflicting versions of `whale_signal_filter.py`**
The repo contains two files with the same class name `WhaleSignalFilter`:
- `whale_signal_filter.py` — synchronous, uses `requests`, has `should_block(direction, symbol)`
- `whale_signal_filter (1).py` — async, uses `aiohttp`, has `should_block_trade(direction, symbol)`

The orchestrator imports the synchronous version (correct for its sync execution model), but the async version has a richer API. These should be consolidated or clearly named differently.

---

### 🟢 MINOR — Style, robustness, and improvement opportunities

| # | File | Issue |
|---|------|-------|
| M1 | `retrain_scheduler.py:139` | Bare `from hmm_regime_detector import ...` — will fail unless cwd is set correctly |
| M2 | `master_orchestrator.py:41` | Exchange initialized without testnet URL — should use testnet API endpoint when `testnet=True` |
| M3 | `binance_testnet_executor.py:121-128` | Mock prices are hardcoded and stale (BTC at $68,500) — use a live feed even in testnet mode |
| M4 | `kelly_position_sizer.py:67` | Unknown regime falls back to `0.5x` multiplier (correct) but silently — should log a warning |
| M5 | `funding_rate_filter.py` | `FundingRateFilter` is never connected to the orchestrator — it's dead code in the main pipeline |
| M6 | `run_tests.py:95` | `assert size > 0` references outer-loop `size` which is the last regime's value; could mask failures for bull/chop |
| M7 | All files | No type hints on numpy array parameters — makes IDE assistance and future refactors harder |

---

## 3. Suggested Fixes Summary

Priority order for fixes:

1. **[BUG-1]** Create `intelligence/finbert_sentiment_filter.py` stub → system won't start without it
2. **[BUG-2]** Fix signal threshold overlap → scoring engine is producing wrong signals
3. **[BUG-4]** Add `os.makedirs("logs", exist_ok=True)` before `FileHandler` → prevents crash on fresh install
4. **[BUG-3]** Fix `orch.PAIRS` → make `run_scan()` respect instance pairs
5. **[BUG-5]** Fix consecutive loss counter logic → circuit breaker fires at wrong times
6. **[BUG-6], [BUG-7], [BUG-8]** Fix Telegram API mismatches → monitoring layer is completely broken
7. **[BUG-9]** Fix async/sync mismatch in `FundingRateFilter`
8. **[BUG-10]** Wire `mtf_filter` and `risk_gate` into `scan_pair()` loop
9. **[BUG-11]** Fix spread calculation scale → liquidity score is permanently saturated
10. **[BUG-15]** Persist `ScaleUpManager.current_index` to disk

---

## 4. Test Suite

A comprehensive pytest test suite has been written covering all critical paths.

**File:** `tests/test_coinscopeai.py`

**Coverage:**

| Module | Test Class | Test Count |
|--------|-----------|-----------|
| `scoring_fixed.py` | `TestFixedScorer` | 8 tests |
| `risk_gate.py` | `TestRiskGate` | 15 tests |
| `kelly_position_sizer.py` | `TestKellyRiskController` | 8 tests |
| `hmm_regime_detector.py` | `TestEnsembleRegimeDetector` | 7 tests |
| `trade_journal.py` | `TestTradeJournal` | 10 tests |
| `binance_testnet_executor.py` | `TestTestnetExecutor` | 13 tests |
| `multi_timeframe_filter.py` | `TestMultiTimeframeFilter` | 10 tests |
| `scale_up_manager.py` | `TestScaleUpManager` | 7 tests |
| Integration | `TestEndToEndFlow` | 3 tests |
| Edge cases | `TestEdgeCases` | 6 tests |
| **Total** | | **87 tests** |

**To run:**
```bash
# Install deps (adjust paths to your project root)
pip install pytest numpy pandas hmmlearn scikit-learn --break-system-packages

# Run all tests
pytest tests/test_coinscopeai.py -v

# Run a single class
pytest tests/test_coinscopeai.py::TestRiskGate -v

# Run with coverage report
pip install pytest-cov --break-system-packages
pytest tests/test_coinscopeai.py --cov=. --cov-report=term-missing
```

---

## 5. Concrete End-to-End Test Scenarios

These can be run manually (or automated) to verify the full system:

### Scenario A — Clean startup and single scan
```bash
# Should complete without ImportError
python master_orchestrator.py
# Expected: fetches bars, detects regime, emits signals, prints summary
```

### Scenario B — API health + scan endpoint
```bash
uvicorn api:app --port 8001
curl http://localhost:8001/health
curl "http://localhost:8001/scan?pairs=BTC/USDT,ETH/USDT"
# Expected: JSON with signals, active_count, total_scanned
```

### Scenario C — Testnet order flow
```python
from binance_testnet_executor import TestnetExecutor
ex = TestnetExecutor()
r = ex.place_order("BTC/USDT", "BUY", kelly_usd=200, regime="bull")
pnl = ex.close_position(r, exit_price=69000)
print(ex.get_summary())
# Expected: trades=1, win_rate=1.0, equity > 10000
```

### Scenario D — Circuit breaker engagement
```python
from binance_testnet_executor import TestnetExecutor
ex = TestnetExecutor()
for _ in range(5):
    r = ex.place_order("BTC/USDT", "BUY", kelly_usd=50, regime="bull")
    ex.close_position(r, exit_price=68000)  # force loss
result = ex.place_order("BTC/USDT", "BUY", kelly_usd=50, regime="bull")
assert result is None   # should be blocked
```

### Scenario E — Regime detection stability
```python
from hmm_regime_detector import EnsembleRegimeDetector
import numpy as np
np.random.seed(42)
returns = np.random.randn(300) * 0.02
vol = np.abs(returns) + 0.005
det = EnsembleRegimeDetector()
det.fit(returns, vol)
result = det.predict_regime(returns[-50:], vol[-50:])
print(result)
# Expected: {'regime': one of bull/bear/chop, 'confidence': 0.0-1.0}
```

### Scenario F — Kelly sizing across regimes
```python
from kelly_position_sizer import KellyRiskController
kelly = KellyRiskController(fraction=0.25)
for r in ["bull", "chop", "bear"]:
    size = kelly.calculate_position_size(0.44, 0.018, 0.012, r, 10000)
    print(f"{r}: ${size:.2f}")
# Expected: bull > chop > bear, all ≤ $200 (2% of $10k)
```

### Scenario G — Trade journal round-trip
```python
from trade_journal import TradeJournal
j = TradeJournal(path="logs/test.json")
e = j.log_open("BTC/USDT", "BUY", "bull", 0.8, 68000, 0.003, 200)
j.log_close(e.id, 69000, 0.0147, 14.7)
print(j.performance_stats())
# Expected: total_trades=1, win_rate=1.0
```

### Scenario H — Scale-up promotion chain
```python
from scale_up_manager import ScaleUpManager
sm = ScaleUpManager()
print(sm.status())   # S0_SEED
sm.check_promotion(100, 0.85)
print(sm.status())   # S1_STARTER
sm.check_promotion(200, 1.05)
print(sm.status())   # S2_GROWTH
```

---

## 6. Recommended Next Steps

1. **Fix BUG-1 immediately** — the system cannot run without `finbert_sentiment_filter.py`
2. **Fix BUG-2 before any live/testnet trading** — signal polarity is corrupted for moderate scores
3. **Wire in `mtf_filter` and `risk_gate`** — they are initialized but not connected
4. **Fix the monitoring layer** (BUG-6, 7, 8) — `AlphaDecayMonitor` and `WeeklyRetrainer` are completely broken
5. **Add integration tests against testnet** using `pytest-asyncio` for the async modules
6. **Consider replacing `MockSentimentFilter`** with a real implementation or at least a configurable stub that reads from env vars
7. **Persist `ScaleUpManager` state** to survive restarts

---

*Report generated by automated code review. All line numbers refer to the uploaded file versions.*

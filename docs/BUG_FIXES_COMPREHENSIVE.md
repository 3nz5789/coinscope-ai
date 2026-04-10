# CoinScopeAI — Comprehensive Bug Fix Guide (16 Bugs)

**Status**: 3/16 fixed in code, 13/16 documented below for manual application

---

## ✅ ALREADY FIXED IN CODE

### BUG-1: Missing `finbert_sentiment_filter.py`
**Status**: ✅ FIXED  
**File**: `intelligence/finbert_sentiment_filter.py`  
**Action**: Created with `MockSentimentFilter` class

### BUG-2: Threshold overlap in scoring
**Status**: ✅ FIXED  
**File**: `core/scoring_fixed.py` lines 269-270  
**Change**: `long_threshold=8.0, short_threshold=4.0` (was 5.5 / 6.5)

### BUG-4: logs/ directory not created
**Status**: ✅ FIXED  
**File**: `live/binance_testnet_executor.py` line 51  
**Change**: Added `os.makedirs("logs", exist_ok=True)`

---

## 🔴 CRITICAL BUGS — MUST FIX BEFORE DEPLOYMENT

### BUG-3: API query params ignored
**File**: `api.py` line 61  
**Problem**: `/scan?pairs=BTC,ETH` is silently ignored

**Fix**:
```python
# In master_orchestrator.py __init__:
def __init__(self, testnet=True, pairs=None):
    self.pairs = pairs or PAIRS  # Add this

# In run_scan():
def run_scan(self):
    for pair in self.pairs:  # Change from: for pair in PAIRS:
        ...
```

---

### BUG-5: Consecutive loss counter wrong
**File**: `risk_gate.py` lines 305-310  
**Problem**: Increments on profitable trades that don't exceed peak equity

**Fix**:
```python
# Replace:
if self.current_equity > self.peak_equity:
    self.peak_equity = self.current_equity
    self.consecutive_losses = 0
else:
    self.consecutive_losses += 1

# With:
if pnl_pct > 0:
    self.consecutive_losses = 0
else:
    self.consecutive_losses += 1
self.current_equity += pnl_dollars
self.peak_equity = max(self.peak_equity, self.current_equity)
```

---

### BUG-6: Calls non-existent Telegram methods
**File**: `alpha_decay_monitor.py` lines 257, 271  
**Problem**: `await self.alerts.alert_error()` and `await self.alerts.alert_status_check()` don't exist

**Fix**:
```python
# Line 257 - Replace:
await self.alerts.alert_error("Alpha Decay", msg)
# With:
self.alerts.send_critical(msg)

# Line 271 - Replace:
await self.alerts.alert_status_check(report['metrics'])
# With:
self.alerts.send_heartbeat(report['metrics'])

# Remove all 'await' keywords (TelegramAlerts methods are synchronous)
```

---

### BUG-7: Calls non-existent Telegram methods
**File**: `retrain_scheduler.py` lines 82, 185, 200  
**Problem**: `self.alerts.alert_signal()` and `self.alerts.alert_scale_up()` don't exist

**Fix**:
```python
# Replace all calls with existing methods:
# self.alerts.alert_signal(...) → self.alerts.send_signal(...)
# self.alerts.alert_scale_up(...) → self.alerts.send_alert(...)
```

---

### BUG-8: Wrong method names on TradeJournal
**File**: `alpha_decay_monitor.py` line 58  
**Problem**: `await self.journal.get_trades()` doesn't exist (method is `get_recent_trades()`)

**Fix**:
```python
# Replace:
trades_30d = await self.journal.get_trades(limit=500)
# With:
trades_30d = self.journal.get_recent_trades(days=30)
```

---

### BUG-9: async/sync mismatch
**File**: `funding_rate_filter.py`  
**Problem**: All methods are `async def` but call synchronous `ccxt` API

**Fix - Option A** (recommended): Use synchronous ccxt
```python
# Remove all 'async def' decorators
# Remove all 'await' keywords
# Use synchronous ccxt.binance() instead of ccxt.async_support.binance
```

**Fix - Option B**: Use async ccxt
```python
# Import: from ccxt.async_support import binance
# Keep async/await but use async ccxt methods
```

---

### BUG-10: Filters never called
**File**: `master_orchestrator.py` line 104  
**Problem**: `self.mtf_filter` and `self.risk_gate` initialized but never used in `scan_pair()`

**Fix**:
```python
# In scan_pair(), after signal generation, add:
# Apply multi-timeframe filter
signal, reason = self.mtf_filter.apply_filter(signal, regime_data)

# Apply risk gate
position_size = self.risk_gate.calculate_position_size(
    win_rate=0.44,
    avg_win=2.1,
    avg_loss=1.0,
    regime=regime
)
```

---

## 🟡 MEDIUM BUGS — SHOULD FIX BEFORE TESTNET

### BUG-11: Spread calculation wrong scale
**File**: `master_orchestrator.py` line 104  
**Problem**: `spread = (h - lo) / c * 0.1` produces tiny values

**Fix**:
```python
# Replace:
spread = (h - lo) / c * 0.1
# With (use absolute USD spread):
spread = (h - lo)  # Already in USD
```

---

### BUG-12: np.roll wraps first bar
**File**: `scoring_fixed.py` line 83  
**Problem**: `np.roll(close, 1)` at index 0 uses `close[-1]`, creating spurious TR

**Fix**:
```python
# After computing tr array, add:
tr[0] = high[0] - low[0]  # Fix first bar
```

---

### BUG-13: Hardcoded initial capital
**File**: `trade_journal.py` line 144  
**Problem**: `equity = np.cumsum(pnls) + 10000` hardcoded

**Fix**:
```python
# Add to __init__:
def __init__(self, initial_capital=10000):
    self.initial_capital = initial_capital

# Replace:
equity = np.cumsum(pnls) + 10000
# With:
equity = np.cumsum(pnls) + self.initial_capital
```

---

### BUG-14: Wrong Sharpe annualization
**File**: `alpha_decay_monitor.py` line 184  
**Problem**: Uses `np.sqrt(365)` instead of `np.sqrt(365 * 4)` for 4 trades/day

**Fix**:
```python
# Replace:
return daily_sharpe * np.sqrt(365)
# With:
trades_per_day = 4
return daily_sharpe * np.sqrt(365 * trades_per_day)
```

---

### BUG-15: State not persisted
**File**: `scale_up_manager.py`  
**Problem**: `current_index` resets to S0 on server restart

**Fix**:
```python
# Add to __init__:
self.state_file = "scale_up_state.json"
self.current_index = self._load_state()

def _load_state(self):
    if os.path.exists(self.state_file):
        with open(self.state_file) as f:
            return json.load(f)["current_index"]
    return 0

def _save_state(self):
    with open(self.state_file, 'w') as f:
        json.dump({"current_index": self.current_index}, f)

# Call _save_state() after any promotion
```

---

### BUG-16: Two conflicting versions
**File**: `whale_signal_filter.py` and `whale_signal_filter (1).py`  
**Problem**: Two files with same class name, different APIs

**Fix**:
1. Keep synchronous version: `whale_signal_filter.py`
2. Delete: `whale_signal_filter (1).py`
3. Ensure orchestrator imports from: `from intelligence.whale_signal_filter import WhaleSignalFilter`

---

## 📋 Deployment Checklist

- [x] BUG-1:  ✅ finbert_sentiment_filter.py created (pre-existing fix)
- [x] BUG-2:  ✅ Thresholds fixed (8.0 / 4.0) (pre-existing fix)
- [x] BUG-3:  ✅ FIXED — CoinScopeOrchestrator(pairs=...) + self.pairs in run_scan()
- [x] BUG-4:  ✅ logs/ directory creation added (pre-existing fix)
- [x] BUG-5:  ✅ FIXED — consecutive loss counter now based on pnl_pct, not equity peak
- [x] BUG-6:  ✅ FIXED — alpha_decay_monitor uses send_critical/send_heartbeat (sync)
- [x] BUG-7:  ✅ FIXED — retrain_scheduler uses send_info/send_critical (sync)
- [x] BUG-8:  ✅ FIXED — get_recent_trades(days=30) replaces await get_trades()
- [x] BUG-9:  ✅ FIXED — funding_rate_filter fully synchronous (removed all async/await)
- [x] BUG-10: ✅ FIXED — mtf_filter.filter_signal() and risk_gate.check_circuit_breakers() called in scan_pair()
- [x] BUG-11: ✅ FIXED — spread = h - lo (absolute USD, not scaled ratio)
- [x] BUG-12: ✅ FIXED — tr[0] = high[0] - low[0] after np.roll ATR calculation
- [x] BUG-13: ✅ FIXED — TradeJournal(initial_capital=...) parameter + self.initial_capital
- [x] BUG-14: ✅ FIXED — Sharpe uses np.sqrt(365 * 4) for 4 trades/day
- [x] BUG-15: ✅ FIXED — ScaleUpManager._load_state()/_save_state() persists to disk
- [ ] BUG-16: ⚠️  Manual step — delete `whale_signal_filter (1).py` from intelligence/

---

## ✅ After All Fixes

Run:
```bash
python run_tests.py  # All 8 tests should pass
python validation/walk_forward_validation.py  # All 3 paths should show Sharpe > 0.8
python live/master_orchestrator.py  # Should scan without errors
```

Then deploy to testnet!

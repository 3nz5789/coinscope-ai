# CoinScopeAI Daily Code Review
**Date:** 2026-04-05
**Scope:** `scanner/`, `signals/`, `alerts/`, `data/`, `risk/`
**Last Commit:** `ac2d5c7` — Add CoinScopeAI engine: FastAPI, HMM regime, Kelly sizing, Risk Gate, Notion journal

---

## Executive Summary

The codebase is architecturally well-structured with clean abstractions (BaseScanner, ConfluenceScorer, AlertQueue, CircuitBreaker). Code style is consistent, documentation is thorough, and the data-flow from scanner → confluence → alerts → risk is logically coherent. However, several **bugs**, **correctness issues**, and **performance concerns** are identified below that could impact live trading reliability.

**Priority Classification:**
- 🔴 **CRITICAL** — could cause incorrect trades, data corruption, or unhandled crashes
- 🟠 **HIGH** — degrades reliability or correctness in production
- 🟡 **MEDIUM** — sub-optimal design or latent bugs
- 🟢 **LOW** — style, maintainability, minor improvements

---

## 1. scanner/ Module

### 🔴 CRITICAL — `pattern_scanner.py` imports serializers from `volume_scanner.py`

`pattern_scanner._fetch_candles()` imports `_candle_to_dict` and `_dict_to_candle` directly from `volume_scanner`:

```python
from scanner.volume_scanner import _dict_to_candle
from scanner.volume_scanner import _candle_to_dict
```

This creates an undocumented tight coupling. If `volume_scanner` is refactored or these private helpers are renamed, `pattern_scanner` will silently break with an `ImportError`. These serializers should live in `data/data_normalizer.py` or a shared `scanner/serializers.py` module.

---

### 🔴 CRITICAL — `signal_generator.py` calls `res["signal"]` on a `ScannerResult` object

In `signals/signal_generator.py`, `_liquidation_signal` and `_volume_signal` call scanners from the legacy `scanners/` module and access their results via dict key syntax:

```python
res = self.liq_scan.scan(symbol)
return int(res["signal"])  # LiquidationScanner.scan() returns ScannerResult, not dict
```

`ScannerResult` is a dataclass, not a dict, so `res["signal"]` will raise `TypeError: 'ScannerResult' object is not subscriptable` on first execution. The `scanners/` (old) and `scanner/` (new) modules appear to have diverged. Verify which implementation is used in production and unify them.

---

### 🟠 HIGH — `liquidation_scanner.py` serializer loses symbol information

`_dict_to_liq()` reconstructs `LiquidationOrder` with `symbol=""`:

```python
return LiquidationOrder(
    symbol="",  # ← symbol is lost on cache round-trip
    side=d["side"], ...
)
```

When a cached liquidation order is reconstructed and used downstream, any logic that checks `order.symbol` will receive an empty string. `_liq_to_dict` should store and restore the symbol field.

---

### 🟠 HIGH — `base_scanner.py` scan loop swallows full exception details

In `_loop()`, exceptions are caught and converted to strings:

```python
except Exception as exc:
    logger.error("%s error scanning %s: %s", self.name, symbol, exc)
```

The stack trace is lost. For debugging production issues, this should use `logger.exception(...)` or `logger.error(..., exc_info=True)` to preserve the full traceback.

---

### 🟡 MEDIUM — `pattern_scanner.py` hardcodes 6-candle structure lookback

In `scan()`, chart structure analysis always uses the last 6 candles regardless of `_candles_needed`:

```python
hits += self._check_structure(symbol, candles[-6:])
```

This is disconnected from the configurable parameter and will give unreliable HH/HL signals on fast timeframes where 6 candles cover very little time. The lookback should be a configurable parameter.

---

### 🟡 MEDIUM — False `Optional[float]` pattern on scanner constructors

All scanner constructors use `or` to handle `Optional` defaults, e.g.:

```python
self._spike_multiplier = spike_multiplier or settings.volume_spike_multiplier
```

If a caller explicitly passes `spike_multiplier=0` (to disable detection), the `or` will silently fall back to the settings value, ignoring the caller's intent. Use `if x is not None` pattern instead:

```python
self._spike_multiplier = spike_multiplier if spike_multiplier is not None else settings.volume_spike_multiplier
```

---

### 🟢 LOW — `orderbook_scanner.py` reports conflicting walls simultaneously

`_check_walls()` can return both a bullish support wall (bid side) AND a bearish resistance wall (ask side) in the same scan result, which adds contradictory hits to the confluence scorer. Consider only reporting the wall closer to the current price, or filtering the wall check by imbalance direction.

---

## 2. signals/ Module

### 🔴 CRITICAL — `signal_generator.py` uses `sys.path.insert` hack

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

This modifies the Python module search path at runtime, which can cause import priority conflicts in production (e.g., shadowing installed packages). Use proper package structure and `PYTHONPATH` / `pyproject.toml` instead.

---

### 🟠 HIGH — `confluence_scorer.py` dead parameter in `_apply_indicator_bonuses`

The method signature accepts `base_score: float` but never references it:

```python
def _apply_indicator_bonuses(
    self,
    direction: SignalDirection,
    ind: Indicators,
    base_score: float,  # ← never used inside the function
) -> tuple[float, list[str]]:
```

The parameter suggests an intent to scale bonuses relative to base score (e.g., lower bonuses for weak base signals), but this logic was never implemented. Either implement the intended scaling or remove the parameter to reduce confusion.

---

### 🟠 HIGH — `confluence_scorer.py` MAX_RAW_SCORE is hardcoded and stale

```python
MAX_RAW_SCORE = 300.0
```

This value needs to be manually updated whenever a new scanner is added or hit scores are changed. As new scanners have been added (pattern, orderbook), the theoretical max score has grown, making `long_norm` and `short_norm` artificially deflated (capped at 70%). Consider computing this dynamically or deriving it from scanner configurations.

---

### 🟠 HIGH — `indicator_engine.py` trend/momentum labels use bare truthiness checks

```python
if ind.ema_9 and ind.ema_21 and ind.ema_9 > ind.ema_21:  signals += 1
```

If any EMA value happens to be exactly `0.0` (possible with synthetic test data), the condition evaluates to `False` incorrectly. Use explicit `is not None` checks:

```python
if ind.ema_9 is not None and ind.ema_21 is not None and ind.ema_9 > ind.ema_21:
```

---

### 🟡 MEDIUM — `signal_generator.py` `_regime_fit` dict is a memory leak

```python
self._regime_fit: dict[str, bool] = {}
```

Symbols are added to `_regime_fit` when first seen but never removed. Over time, as the symbol list changes, this dict grows without bound. Because the `EnsembleRegimeDetector` is refitted on each new symbol, the entry only marks "has been fitted" — it could be replaced with a TTL-based set or cleared periodically.

---

### 🟡 MEDIUM — `entry_exit_calculator.py` structure SL for SHORT uses max instead of nearest

```python
swing_highs = [c.high for c in recent if c.high > entry]
sl_candidate = max(swing_highs) + atr * 0.1  # uses the highest, not the nearest
```

For a SHORT trade, the stop-loss should be placed at the **nearest** swing high above entry (most conservative valid stop), not the **highest** high in the lookback window. Using `max()` places the stop unreasonably far away, reducing the effective RR ratio and potentially invalidating otherwise good setups.

**Fix:**
```python
sl_candidate = min(swing_highs) + atr * 0.1  # nearest swing high above entry
```

---

### 🟡 MEDIUM — `indicator_engine.py` `_obv` uses a Python loop (performance)

```python
def _obv(closes: np.ndarray, volumes: np.ndarray) -> float:
    obv = 0.0
    for i in range(1, len(closes)):
        ...
```

With 200+ candles, this pure Python loop runs ~200 iterations per call per symbol. Since OBV is called inside `IndicatorEngine.compute()` which runs on every scan cycle for every symbol, this adds meaningful latency. A vectorized numpy implementation would be 10-50× faster:

```python
direction = np.sign(np.diff(closes))
obv_series = np.cumsum(np.where(direction > 0, volumes[1:],
             np.where(direction < 0, -volumes[1:], 0)))
return float(obv_series[-1])
```

---

## 3. alerts/ Module

### 🟠 HIGH — `alert_queue.py` drops CRITICAL alerts when queue is full

When the queue reaches `MAX_QUEUE_SIZE=200`, new items are silently dropped:

```python
if self._queue.full():
    self._dropped += 1
    logger.warning("AlertQueue full. Dropping %s alert...", item.alert_type)
    return False
```

If the queue fills with LOW-priority daily summaries, a subsequent `CRITICAL` circuit breaker alert would be silently dropped. CRITICAL alerts should either bypass the queue size limit or evict the lowest-priority item to make room.

---

### 🟠 HIGH — `telegram_notifier.py` bot token exposed via `self._base` string

```python
self._base = TELEGRAM_API_BASE.format(token=self._token) if self._enabled else ""
```

If `self._base` is ever logged (e.g., in an exception message or debug `repr`), the full bot token appears in logs. The token should be stored separately and only used at the point of the HTTP call. The `__repr__` of the notifier should never include the base URL.

---

### 🟠 HIGH — `telegram_alerts.py` (root-level legacy) blocks the event loop

The legacy `TelegramAlerts` class in the root module uses the synchronous `requests` library:

```python
requests.post(
    f"https://api.telegram.org/bot{self.token}/sendMessage", ...
    timeout=5,
)
```

Calling this from within an asyncio event loop will block all other coroutines for up to 5 seconds per call. Either migrate all callers to the async `TelegramNotifier` in `alerts/` and delete this file, or replace `requests` with `httpx` or `aiohttp`.

---

### 🟡 MEDIUM — `rate_limiter.py` uses `threading.Lock` in async context

`_TokenBucket` uses `threading.Lock`:

```python
from threading import Lock
...
self._lock = Lock()
```

In an async context, acquiring a `threading.Lock` that is held by another coroutine in the same event loop thread would deadlock — the event loop would block waiting for a lock that the same thread holds. Use `asyncio.Lock` for buckets used within async code.

---

### 🟡 MEDIUM — `rate_limiter.py` `allow_signal` refund bypasses bucket lock

```python
def allow_signal(self, symbol: str) -> bool:
    if not self.allow_symbol(symbol):
        return False
    if not self.allow_telegram():
        # refund: directly writes to _tokens without acquiring the lock
        self._get_symbol_bucket(symbol)._tokens = min(
            self._symbol_capacity,
            self._get_symbol_bucket(symbol)._tokens + 1,
        )
        return False
    return True
```

The refund writes to `_tokens` without the bucket's lock, creating a TOCTOU race condition. The `_TokenBucket` should expose an explicit `refund()` method that acquires the lock.

---

### 🟡 MEDIUM — `alert_queue.py` `AlertType` is a non-standard string class

```python
class AlertType(str):
    SIGNAL = "signal"
    STATUS = "status"
    ...
```

This pattern is unusual and doesn't give IDE type safety or exhaustiveness checking. It should be a proper `StrEnum` (Python 3.11+) or `Enum`:

```python
from enum import StrEnum
class AlertType(StrEnum):
    SIGNAL = "signal"
    STATUS = "status"
    ...
```

---

## 4. data/ Module

### 🟠 HIGH — `cache_manager.py` `get_all_signals()` uses KEYS (O(N) blocking)

```python
async def get_all_signals(self) -> dict[str, Any]:
    keys = await self.keys("signal:*")   # calls Redis KEYS — O(N), blocks server
```

The Redis `KEYS` command scans the entire keyspace and blocks the Redis server. With 100+ symbols each caching multiple data types, this could cause latency spikes. The existing `scan_keys()` method should be used instead, or signal keys should be tracked in a Redis set.

---

### 🟠 HIGH — `binance_rest.py` retry loop makes 4 attempts, not 3

The retry loop increments `attempt` after sleeping:

```python
while attempt <= retries:   # retries = MAX_RETRIES = 3
    ...
    if resp.status >= 500 and attempt < retries:
        attempt += 1
        continue
raise BinanceRESTError(503, -1, f"Max retries ({retries}) exceeded...")
```

With `attempt` starting at 0 and the condition being `attempt <= retries` (i.e., ≤ 3), the loop body executes at attempts 0, 1, 2, and 3 — **4 total attempts** — but the error message says "Max retries (3) exceeded". This is a misleading off-by-one. Change the condition to `attempt < retries` or document that `MAX_RETRIES` is the total attempt count.

---

### 🟡 MEDIUM — `binance_rest.py` `get_symbol_info` fetches full exchange info on every call

```python
async def get_symbol_info(self, symbol: str) -> Optional[dict]:
    info = await self.get_exchange_info()  # downloads ALL symbols every call
    for sym in info.get("symbols", []):
        if sym["symbol"] == symbol:
            return sym
```

`get_exchange_info()` returns hundreds of symbols and is expensive (weight=1 but large payload). This is called from `get_min_notional()` which may be called before every order. The result should be cached in `CacheManager` with a long TTL (e.g., 1 hour).

---

### 🟡 MEDIUM — `cache_manager.py` `subscribe()` context manager missing error handling

The `subscribe()` async context manager creates a new Redis connection but only cleans it up on normal exit. If the subscriber errors mid-iteration, the new `sub_client` connection might not be closed. The `finally` block already handles unsubscribe, but a try/except around `pubsub.listen()` would make it more robust.

---

### 🟢 LOW — `binance_rest.py` POST requests should validate parameters before sending

No validation is performed on `place_order` parameters (e.g., `order_type`, `side`, `time_in_force`). Invalid values only fail at the Binance API, costing a round-trip and consuming rate limit weight. Basic validation with a clear error message locally would improve developer experience.

---

## 5. risk/ Module

### 🟠 HIGH — `exposure_tracker.py` has a dead `_daily_pnl` attribute

The class initializes `_daily_pnl = 0.0` and increments it in `close_position`, but none of the public properties use it. The `daily_pnl` property independently computes `self._realised_pnl + self.unrealised_pnl`. The `_daily_pnl` accumulation is therefore wasted work and will drift from `daily_pnl` once unrealised PnL exists. Remove the dead attribute or use it consistently.

---

### 🟠 HIGH — `position_sizer.py` type annotations are incorrect (Python warning in strict mode)

```python
def __init__(
    self,
    risk_per_trade_pct: float = None,   # ← annotated float, default is None
    max_position_pct:   float = None,
    max_leverage:       int   = None,
    ...
```

These should be `Optional[float] = None` / `Optional[int] = None`. Under `mypy --strict` or Pyright, these will produce type errors. In Python 3.11+ with `from __future__ import annotations`, this can cause subtle issues at runtime.

---

### 🟠 HIGH — `position_sizer.py` leverage calculation is incorrect

```python
leverage_used = min(
    self._max_leverage,
    max(1, int(notional / max(balance * 0.1, 1))),
)
```

This formula computes `notional / (10% of balance)`, which for a $1,000 notional on a $10,000 balance gives `1000 / 1000 = 1x` — reasonable, but for a $5,000 notional it gives 5x, and for a $200 notional it gives 0.2 → rounded to 1x. The formula doesn't reflect actual leverage being applied (which is `notional / margin`). The actual margin is computed as `notional / max_leverage`, not as a percentage of balance. This `leverage_used` value should be `ceil(notional / margin_usdt)` to be accurate.

---

### 🟡 MEDIUM — `circuit_breaker.py` mutable state in `is_open` property getter

```python
@property
def is_open(self) -> bool:
    self._maybe_auto_reset()   # ← side effect inside a property!
    return self._state == BreakerState.OPEN
```

Properties with side effects violate the principle of least surprise. Calling `cb.is_open` twice in quick succession could return different values if the reset timer expires between calls. The auto-reset check should be performed in `check()` and at the start of the background loop, not embedded in the property getter.

---

### 🟡 MEDIUM — `correlation_analyzer.py` `append_price` uses O(n) `list.pop(0)`

```python
if len(self._prices[symbol]) > self._lookback:
    self._prices[symbol].pop(0)   # O(n) operation
```

With 50-period lookback and hundreds of symbols each receiving price ticks, this becomes expensive. Replace with `collections.deque(maxlen=lookback)` for O(1) append and automatic eviction:

```python
from collections import deque
self._prices[symbol] = deque(maxlen=self._lookback)
```

---

### 🟡 MEDIUM — `circuit_breaker.py` `check()` is not concurrency-safe

`check()` evaluates conditions and then calls `_trip()` without a lock. In an async environment where multiple coroutines could call `check()` simultaneously, two concurrent evaluations could both pass the "not already open" guard and both attempt to trip the breaker:

```python
if self._state == BreakerState.OPEN:
    ...  # both coroutines see CLOSED here
reason = ...
self._trip(...)  # both coroutines trip it
```

`_trip()` has a secondary guard (`if self._state == BreakerState.OPEN: return`) but there is still a window for double-callbacks. Protect `check()` with an `asyncio.Lock`.

---

### 🟡 MEDIUM — `exposure_tracker.py` `open_positions` shallow copy is unsafe

```python
@property
def open_positions(self) -> dict[str, Position]:
    return dict(self._positions)   # shallow copy
```

The returned dict is a copy but the `Position` objects inside are shared references. Callers who mutate a `Position` (e.g., `pos.mark_price = x`) will mutate the internal state without acquiring `_lock`. Either return deep copies or document that `Position` objects must not be mutated by callers.

---

### 🟢 LOW — `correlation_analyzer.py` `is_safe_to_add` doesn't handle NaN from `np.corrcoef`

If two symbols have identical price series (e.g., in tests or with synthetic data), `np.corrcoef` may return `NaN` (standard deviation = 0). The `pearson()` method returns `float(np.corrcoef(...)[0,1])` without checking for NaN, which could then cause comparisons to silently evaluate to `False`, allowing a potentially over-correlated position through.

**Fix:** Add `if np.isnan(r): return None` before returning.

---

## Summary Table

| Severity | Module | Issue | Count |
|----------|--------|-------|-------|
| 🔴 CRITICAL | scanner, signals | Broken dict access on ScannerResult; cross-module serializer coupling; sys.path hack | 3 |
| 🟠 HIGH | All modules | Lost symbol on cache round-trip; dead parameter; KEYS O(N); blocking HTTP; queue drops CRITICAL; token exposure; retry count off-by-one; wrong type annotations; wrong leverage calc | 11 |
| 🟡 MEDIUM | All modules | Hardcoded lookback; or-vs-None pattern; OBV loop perf; wrong structure SL direction; threading.Lock in async; memory leak; NaN not checked; shallow copy safety | 10 |
| 🟢 LOW | scanner, alerts, risk | Conflicting wall hits; AlertType enum style; parameter validation; NaN guard | 4 |

---

## Top 5 Recommended Actions (Priority Order)

1. **Fix `signal_generator.py`** — Remove `sys.path.insert`, unify the `scanner/` vs `scanners/` duplication, and correct the dict-style access on `ScannerResult` objects before any live trading is enabled on this path.

2. **Move serializers out of `volume_scanner.py`** — Place `_candle_to_dict` / `_dict_to_candle` in `data/data_normalizer.py` to eliminate the cross-scanner import dependency.

3. **Fix CRITICAL alert queue drop** — CRITICAL priority alerts must not be discarded. Add a bypass or eviction policy so circuit breaker alerts always reach the Telegram channel.

4. **Replace `threading.Lock` with `asyncio.Lock` in `rate_limiter.py`** — The current threading lock in an async context is a potential deadlock hazard.

5. **Fix `entry_exit_calculator.py` SHORT structure SL** — Change `max(swing_highs)` to `min(swing_highs)` so the nearest swing high is used for SHORT stop-losses, preventing excessively wide stops and improving trade validity rates.

---

*Generated by CoinScopeAI daily-code-review scheduled task — 2026-04-05 09:00 UTC*

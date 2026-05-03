# CoinScopeAI — Trading Engine Code Review
**Date:** 2026-04-19
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}`
**Reviewer:** Automated daily review (Claude)
**Prime directive per CoinScopeAI trading rules:** capital preservation

---

## Executive Summary

Overall the engine is well-structured: clear separation between data ingestion, signal generation, confluence scoring, alerting, and risk gating. Code is type-hinted, dataclass-heavy, and uses async consistently. However, several **capital-preservation-critical** issues were found — particularly around silent failure modes in risk gates, race conditions in state that is read by position sizing, and a handful of bugs that can cause stale or misleading values to be treated as valid.

| Severity | Count | Notes |
|---|---|---|
| **P0 — fix before next trading session** | 6 | silent-zero correlations, race on circuit-breaker state, stats.reconnects no-op bug, `_dict_to_liq` empty-symbol, RateLimitError swallows Retry-After, orphaned imports in signal_generator |
| **P1 — fix this week** | 14 | Kelly with zero/neg avg_rr, RSI=100 on zero loss, ADX index OOB, exposure double-count risk, dedup cache eviction churn, webhook `except Exception`, alert_queue full check race, and others |
| **P2 — hygiene / maintainability** | 18 | hardcoded constants, inconsistent sort semantics, naive UTC timestamps, unused paths, duplication between `telegram_alerts.py` and `telegram_notifier.py`, deprecated `datetime.utcnow()` |

---

## 1. Code Quality Assessment

### 1.1 Security

**HMAC signing (REST + webhook):** correct. `data/binance_rest.py` inserts `timestamp` and `recvWindow` before computing HMAC-SHA256 over the urlencoded query; `alerts/webhook_dispatcher.py::_sign_payload` hashes the exact JSON body that is sent.

**Secrets handling:** API keys are pulled from `settings` only; never logged. `data/cache_manager.py::_safe_url()` partially masks the password in Redis URLs but **leaves the username exposed** — low severity, but worth fixing for full-URL log redaction.

**Webhook payload signing uses `X-Signature` hex** but does **not include a timestamp inside the signed body**. The `X-Timestamp` header is sent but not covered by the HMAC. A replay-capable attacker who captures one webhook could resend it indefinitely. *Recommendation:* include the timestamp (and ideally a nonce) in the signed bytes: `hmac(secret, f"{ts}.{body}")`.

**Excessive `except Exception` (and sometimes `except (httpx.HTTPError, Exception)`):** swallows `KeyboardInterrupt`/`SystemExit` and hides real bugs. Offenders include:
- `alerts/webhook_dispatcher.py::_post_to_endpoint` (line ~253): `except (httpx.HTTPError, Exception)` — the `Exception` branch is redundant *and* catches everything.
- `scanner/base_scanner.py::run` result-merge block: bare `except Exception`.
- `risk/correlation_analyzer.py` — catches and returns 0.0, masking data outages as "uncorrelated" (see §2.1).

### 1.2 Performance

Hot paths are generally fine — numpy/pandas in `signals/indicator_engine.py`, async fan-out in scanners, websockets with keepalive. Hotspots worth attention:

- **`signals/indicator_engine.py`** recomputes full EMA/RSI/ATR vectors on every tick on every symbol. For 50+ symbols × 1m-5m-15m-1h-4h this adds up. Consider per-symbol caches keyed on `last_closed_candle_ts`.
- **`alerts/telegram_notifier.py::_is_duplicate()`** evicts expired entries on *every* call (O(N) per call). At steady-state N stays small, but under a burst the eviction pass is worst-case quadratic. Replace with a TTL-backed collection (e.g., `cachetools.TTLCache`) or amortize eviction.
- **`data/cache_manager.py::subscribe()`** opens a fresh Redis connection per subscribe call. Reuse a single pub/sub connection or manage via a pool.
- **`data/binance_websocket.py`** — the `_pending` dict (keyed by request id) is mutated from both send and receive paths without a lock. See §2.5.

### 1.3 Maintainability

- **Duplication:** `alerts/telegram_alerts.py` (synchronous, `requests.post`, no retry, no dedup) is an older shape that duplicates `alerts/telegram_notifier.py` (async httpx, retry, dedup). The former is still imported by `retrain_scheduler.py` and `alpha_decay_monitor.py`. *Recommendation:* deprecate `telegram_alerts.py`, or have it delegate to the async notifier.
- **Magic numbers** sprinkled through scanners (`0.001` tweezer tolerance in `pattern_scanner.py`, `1.5x` volume multiplier, `MAX_RAW_SCORE = 300` in `confluence_scorer.py` which does not match the documented 0–12 bucket math). Extract to config.
- **Orphaned imports** in `signals/signal_generator.py`: `from core.scoring_fixed import ...` and `from intelligence.hmm_regime_detector import ...` — these modules do not exist in the current tree. Module fails to import in fresh envs. **P0.**
- **Naive UTC timestamps** (`datetime.utcnow()`) are used widely in `alerts/alpha_decay_monitor.py`, `alerts/telegram_alerts.py`. Python 3.12+ deprecates `utcnow`. Use `datetime.now(timezone.utc)`.

---

## 2. Bugs and Edge Cases (severity-ordered)

### 2.1 [P0] `risk/correlation_analyzer.py` silently returns 0.0 on missing data

```python
# ~line 140
try:
    corr = np.corrcoef(...)[0, 1]
except Exception:
    return 0.0
```

A returned correlation of 0.0 is indistinguishable from a *legitimately* uncorrelated pair. `risk/exposure_tracker.py` uses this to decide whether a new position aggravates a cluster. If the data feed is stale or two price histories happen to misalign, the engine will **approve concentrated positions** thinking they are diversified. This directly contradicts capital preservation.

**Fix:**
```python
except Exception as exc:
    logger.warning("corr failed for %s/%s: %s — returning None", a, b, exc)
    return None   # or a sentinel that callers MUST handle
# in callers: if corr is None, block the trade (fail-closed) or flag the cluster
```

### 2.2 [P0] `risk/circuit_breaker.py` — race on state transitions

Two places mutate `self.state` / `self.daily_pnl` without any `asyncio.Lock`:
1. `record_pnl()` called by the scanner after each trade close.
2. `tick()` called by the main loop each second to check timeouts.

If `record_pnl` is mid-update when `tick` reads, the breaker may evaluate against a partially-updated value and **fail to trip**. Additionally, the sign convention switches between "loss as positive" (`abs(daily_loss_pct)`) and "pnl as negative" inconsistently.

**Fix:** wrap all state reads/writes in a single `asyncio.Lock`; standardise on PnL-signed (loss is negative) and compute `loss_pct = -min(pnl_pct, 0)` in one helper.

### 2.3 [P0] `data/binance_websocket.py` line ~234 — `stats.reconnects` counter is a no-op

```python
self.stats.reconnects += 1 if self.stats.reconnects else 0
```

This increments only when the counter is already non-zero — so it can never leave 0. Reconnect observability is silently broken.

**Fix:**
```python
self.stats.reconnects += 1
```

### 2.4 [P0] `data/binance_rest.py` RateLimitError throws away `Retry-After`

On 429, the header is parsed into a local variable, logged, and then `raise RateLimitError(...)` — the caller does not sleep. Under sustained rate pressure the caller will retry immediately and re-trigger 429, possibly escalating to IP ban (418).

**Fix:**
```python
if resp.status_code == 429:
    retry_after = float(resp.headers.get("Retry-After", "1"))
    await asyncio.sleep(retry_after)    # actually wait
    raise RateLimitError(retry_after=retry_after)
```
…or have the caller's retry logic read `.retry_after` off the exception.

### 2.5 [P0] `scanner/liquidation_scanner.py::_dict_to_liq()` hardcodes empty symbol

```python
# line ~73
return Liquidation(symbol="", side=..., qty=..., price=..., ts=...)
```

All liquidations produced via this path have `symbol=""`. Any downstream filter by symbol silently drops them, so the liquidation scanner appears quiet while live data is flowing through.

**Fix:** pass the symbol in from the stream key:
```python
return Liquidation(symbol=symbol, side=..., qty=..., price=..., ts=...)
```

### 2.6 [P0] `signals/signal_generator.py` orphaned imports

`from core.scoring_fixed import ...` and `from intelligence.hmm_regime_detector import ...` reference files that don't exist in `coinscope_trading_engine/`. Clean-install of the repo fails at import time. Either vendor the modules back in or rewrite the imports to the actual current paths (e.g., the HMM detector now lives under `alerts/retrain_scheduler.py`'s siblings, not `intelligence/`).

### 2.7 [P1] `signals/indicator_engine.py` — RSI returns 100 on zero loss

When average loss over the lookback is exactly 0 (a flat or only-up window), `rs = avg_gain / avg_loss` divides by zero. The code guards with `if avg_loss == 0: return 100.0`. This is mathematically defensible but means the scorer sees maximum overbought *any time the market has no down bars in N candles* — e.g., during illiquid periods or after a thin-volume push. This then feeds into short bias and can recommend fading non-trends. **Fix:** return `50.0` (neutral) when there is insufficient variance, and surface an `insufficient_data` flag.

### 2.8 [P1] `signals/indicator_engine.py` — ADX index out of bounds

In the ADX computation, the final `di_plus[-1]`/`di_minus[-1]` access assumes the smoothed arrays are full-length, but when `len(high) < period * 2`, the smoothing step returns a shorter array and `-1` points into an empty slot → `IndexError`. Add an explicit length guard and return `None` when insufficient.

### 2.9 [P1] `risk/position_sizer.py` — Kelly blows up when `avg_rr ≤ 0`

```python
edge = win_rate - (1 - win_rate) / avg_rr
```

If `avg_rr` is 0 or negative (which can happen early in a cycle with few trades, or after a bad streak), `edge` → −∞ or NaN, then clipped sizing produces inconsistent behavior depending on whether the negative is trapped earlier or later. Add an explicit guard: `if avg_rr <= 0: return {"size": 0.0, "reason": "insufficient track record"}`.

### 2.10 [P1] `signals/backtester.py` — multiple correctness issues

- Line ~177: the position entry timestamp is taken from the *signal* candle, not the *next* candle. Signals fire on the close of bar *t* but a real fill happens at bar *t+1* open. As written, the backtester is look-ahead biased and will overstate PnL.
- Line ~263: stop-loss checks use `low <= stop_loss` but enters via `close` of the same bar on the entry pass — double-counts the entry bar for stop checks.
- Line ~287: `equity_curve` appends before the exit is applied, so drawdown metrics are off by one bar.
- Line ~334: max drawdown is computed as `min(equity) / max(equity) - 1` **over the whole series**, not peak-to-trough-in-order. Use a cumulative max.

### 2.11 [P1] `risk/exposure_tracker.py` — double-counts concurrent positions

When a new signal's setup is staged (added to pending) before the previous signal has cleared, both are summed into `total_exposure_usd`. No de-duplication by `signal_id`/`symbol+direction`. Under fast-fire scenarios this causes the risk gate to reject legitimate trades. Also there is no price sanity check — a zero-price fill (data glitch) would compute `exposure = 0` and never trip the gate.

### 2.12 [P1] `alerts/alert_queue.py::_enqueue` — race between `full()` check and `await put()`

```python
if self._queue.full():
    self._dropped += 1; return False
await self._queue.put(item)
```

Between the `full()` check and the `await put`, other tasks may fill the queue → `put()` blocks indefinitely, stalling every enqueue caller. Use `put_nowait()` with `except asyncio.QueueFull` instead.

### 2.13 [P1] `alerts/webhook_dispatcher.py` — `record_failure` only counts once per batch

Individual retry attempts increment no counter; only the terminal failure does. Per-endpoint failure rates therefore *undercount* by a factor of `MAX_RETRIES`, so `is_disabled` takes longer than intended to trip. Move `total_failed += 1` into the per-attempt exception branch, and keep `consecutive_fails` as the terminal-failure count.

### 2.14 [P1] `scanner/base_scanner.py::run` — `_results` dict mutated from concurrent tasks

The merge loop at ~172-182 writes to `self._results` while subtask coroutines may also be writing. Works accidentally today because CPython's GIL makes dict assignment atomic *per key*, but the aggregated iteration a few lines later is **not** safe. Gather results into a local list first, then commit under a lock or after gather completes.

### 2.15 [P2] `scanner/orderbook_scanner.py::_find_wall()` divide-by-zero (line ~115)

If `total_volume == 0` (empty book snapshot at boot), the ratio division raises ZeroDivisionError inside the scanner. Return `None` / skip the snapshot.

### 2.16 [P2] `scanner/pattern_scanner.py` — hardcoded tweezer tolerance

`0.001` (10 bps) is brittle across assets with very different tick sizes. Normalize by ATR or by symbol tick size.

### 2.17 [P2] `scanner/volume_scanner.py` — taker-buy ratio fires independently of volume magnitude

A high taker-buy ratio in a 0.1× volume bar is not a real flow signal. Require both `volume_multiplier ≥ threshold` *and* `taker_buy_ratio ≥ threshold` before emitting.

### 2.18 [P2] `scanner/funding_rate_scanner.py` — confusing descending sort

The scanner sorts funding rates descending then takes the *top* N as "expensive longs", but naming reads "high-funding opportunities". Depending on intent (fade extremes vs. ride them), the wrong direction may be emitted. Rename and add a direction-explicit comment.

### 2.19 [P2] `signals/confluence_scorer.py` — `MAX_RAW_SCORE = 300` mis-scales the 0–12 system

The documented CoinScopeAI confluence score is `0–12`. The raw internal scale is 0–300, then divided by 25. Changing any single weight silently rescales the whole thing. Either normalize at the bucket level (each bucket returns 0–2) or compute the divisor from the actual sum of weights.

### 2.20 [P2] `data/data_normalizer.py::ws_depth_to_orderbook` uses `__import__` hack

Uses `__import__("time").time()` mid-function to avoid a top-level import. Cheap, but confusing — just import `time` at the top.

### 2.21 [P2] `alerts/telegram_notifier.py` — ReadTimeout correctly NOT retried, but connect errors are

Good: `ReadTimeout` is explicitly not retried (to avoid duplicate sends on server-accepted-but-slow-ack). Consider logging the *message hash* whenever a ReadTimeout occurs so the operator can verify manually.

---

## 3. Optimisation Opportunities

1. **Cache indicator frames keyed on last-closed-candle-ts.** `indicator_engine` currently recomputes RSI/ATR/EMA/Bollinger on every signal generation call. A dict keyed by `(symbol, tf, last_closed_ts)` with bounded size (say 4 per symbol) cuts recompute cost by 80–95% during a scan cycle.
2. **Batch webhook dispatch.** `webhook_dispatcher._dispatch_all` fans out to all endpoints concurrently — good. Currently opens a fresh `httpx.AsyncClient` lazily per call. Consider promoting it to a long-lived client with HTTP/2 and connection reuse — big win on multi-endpoint fanout.
3. **Use `asyncio.Queue`'s built-in backpressure** in the alert queue instead of manual `.full()` checks; then `put_nowait` naturally raises `QueueFull` which maps cleanly to the "drop" branch.
4. **Redis pub/sub connection pooling** in `cache_manager.subscribe()` — today each subscribe opens a new TCP connection; over many symbols this burns file descriptors.
5. **Replace `cachetools`-style manual TTL eviction** in `telegram_notifier.py::_is_duplicate` with `cachetools.TTLCache` (O(1) amortised) — removes the O(N) sweep.
6. **Vector-scan indicators with polars/numba.** If you stay on pandas, `pandas.rolling` is fine, but `polars` on a 5-minute hot loop gives a 3–5× boost for 50+ symbols. Low priority; flag for later.
7. **Share one HMM model instance across workers** — currently each backtest instantiates a fresh one; cache a read-only singleton.

---

## 4. Best-Practice Violations

| File | Violation | Fix |
|---|---|---|
| `signals/signal_generator.py` | Imports reference non-existent modules (`core.scoring_fixed`, `intelligence.hmm_regime_detector`) | Remove or re-route imports |
| `risk/correlation_analyzer.py` | Returns `0.0` on error (fail-open) | Return `None` and fail-closed at caller |
| `alerts/webhook_dispatcher.py` | `except (httpx.HTTPError, Exception)` | Catch specific httpx errors only; propagate programming errors |
| `alerts/telegram_alerts.py` | Duplicates `telegram_notifier`; uses sync `requests` inside async engine | Delete or re-implement as thin shim over notifier |
| `alerts/alpha_decay_monitor.py`, `telegram_alerts.py` | `datetime.utcnow()` deprecated | `datetime.now(timezone.utc)` |
| `data/cache_manager.py` | `_safe_url()` leaks username | Mask username too |
| `scanner/pattern_scanner.py`, `scanner/volume_scanner.py` | Magic constants | Move to `config/thresholds.py` |
| `signals/confluence_scorer.py` | `MAX_RAW_SCORE` hardcoded to 300 | Derive from weight config |
| `alerts/alert_queue.py` | `full()`+`put()` race | `put_nowait` + `QueueFull` |
| `data/binance_websocket.py` | `_pending` dict lacks concurrency guard | Wrap mutations in a lock |
| Multiple | Bare `except Exception:` swallowing errors | Narrow to expected exception classes and re-raise unknowns |
| `signals/backtester.py` | Look-ahead bias on entry bar | Execute at next bar's open |
| `risk/position_sizer.py` | Kelly undefined behaviour for `avg_rr ≤ 0` | Explicit guard, return 0-size |

---

## 5. Specific Recommendations (prioritized with code)

### Recommendation 1 — Fail-closed correlation (P0)

```python
# risk/correlation_analyzer.py
def pearson_correlation(self, a: list[float], b: list[float]) -> Optional[float]:
    if not a or not b or len(a) != len(b) or len(a) < self.MIN_WINDOW:
        return None
    try:
        return float(np.corrcoef(a, b)[0, 1])
    except Exception as exc:
        logger.warning("correlation failed for pair: %s", exc)
        return None

# risk/exposure_tracker.py — caller
corr = self.correlator.pearson_correlation(px_a, px_b)
if corr is None:
    logger.warning("corr unavailable for %s/%s — blocking new exposure", a, b)
    return RiskDecision.BLOCK  # fail-closed
if abs(corr) >= self.HIGH_CORR_THRESHOLD:
    return RiskDecision.BLOCK
```

### Recommendation 2 — Single lock around circuit-breaker state (P0)

```python
# risk/circuit_breaker.py
class CircuitBreaker:
    def __init__(self, ...):
        ...
        self._lock = asyncio.Lock()

    async def record_pnl(self, pnl_pct: float) -> None:
        async with self._lock:
            self.daily_pnl += pnl_pct
            self._evaluate_locked()

    async def tick(self) -> None:
        async with self._lock:
            self._evaluate_locked()

    def _evaluate_locked(self) -> None:
        loss = -min(self.daily_pnl, 0.0)           # always ≥ 0
        if loss >= self.max_daily_loss_pct:
            self._trip(reason="daily_loss_limit")
```

### Recommendation 3 — Fix reconnect stat & add lock for `_pending` (P0 + P1)

```python
# data/binance_websocket.py
# line ~234
self.stats.reconnects += 1      # was: += 1 if self.stats.reconnects else 0

# _pending access
self._pending_lock = asyncio.Lock()
...
async with self._pending_lock:
    self._pending[req_id] = fut
...
async with self._pending_lock:
    fut = self._pending.pop(req_id, None)
```

### Recommendation 4 — Honour Retry-After (P0)

```python
# data/binance_rest.py
if resp.status_code == 429:
    retry_after = float(resp.headers.get("Retry-After", "1"))
    logger.warning("rate-limited by Binance, sleeping %.2fs", retry_after)
    await asyncio.sleep(retry_after)
    raise RateLimitError(retry_after=retry_after)
```

### Recommendation 5 — Fix liquidation symbol (P0)

```python
# scanner/liquidation_scanner.py
@staticmethod
def _dict_to_liq(raw: dict, *, symbol: str) -> Liquidation:
    return Liquidation(
        symbol=symbol,                          # was: ""
        side=raw["S"].lower(),
        qty=float(raw["q"]),
        price=float(raw["p"]),
        ts=int(raw["T"]),
    )

# caller — feed the stream-key symbol through
liq = self._dict_to_liq(msg["o"], symbol=stream_symbol)
```

### Recommendation 6 — Kelly guard (P1)

```python
# risk/position_sizer.py
def kelly_fraction(self, win_rate: float, avg_rr: float) -> float:
    if not (0.0 < win_rate < 1.0) or avg_rr <= 0:
        return 0.0
    edge = win_rate - (1 - win_rate) / avg_rr
    return max(0.0, min(self.MAX_KELLY, edge))
```

### Recommendation 7 — Alert queue backpressure (P1)

```python
# alerts/alert_queue.py
async def _enqueue(self, item: AlertItem) -> bool:
    try:
        self._queue.put_nowait(item)
        return True
    except asyncio.QueueFull:
        self._dropped += 1
        logger.warning(
            "AlertQueue full (%d). Dropped %s (total dropped=%d)",
            self._queue.maxsize, item.alert_type, self._dropped,
        )
        return False
```

### Recommendation 8 — Backtester entry on next bar (P1)

```python
# signals/backtester.py
for i in range(len(candles) - 1):
    bar = candles[i]
    next_bar = candles[i + 1]
    if not signal_fires_on_close_of(bar):
        continue
    fill_price = next_bar.open        # realistic next-bar-open fill
    fill_ts    = next_bar.ts
    # stop/tp loop starts from next_bar, not bar
```

---

## 6. Follow-up / Tracking

Suggested actions:

- Open P0 Linear tickets for items §2.1–§2.6 and block the next live-trading deploy on them (capital-preservation-critical).
- Add an integration test that verifies `correlation_analyzer` returns `None` (not 0.0) on missing data, and that `exposure_tracker` blocks the trade on `None`.
- Add a unit test that asserts `stats.reconnects` increments across a forced disconnect cycle.
- Delete or collapse `alerts/telegram_alerts.py` in favour of `alerts/telegram_notifier.py`; route `retrain_scheduler` and `alpha_decay_monitor` through the async notifier.
- Add CI lint that rejects `except Exception:` without a `logger.exception` call and a re-raise or explicit handling comment.

---

*End of report — CoinScopeAI daily code review, 2026-04-19.*

# CoinScopeAI — Daily Code Review
**Date:** 2026-04-22
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` (~9,865 LOC, 31 files)
**Reviewer:** Automated daily review (Claude, scheduled 09:00)
**Prime directive per CoinScopeAI trading rules:** capital preservation

---

## 0. Delta Since Last Review

- **No new commits** since `59416a2` on 2026-04-18 (Tier-1 docs restructure). Branch `restructure/2026-04-18-tier1-docs` remains ahead of `main`; no tracked source changes in scope.
- Prior automated reviews at `CODE_REVIEW_2026-04-19.md` and `CODE_REVIEW_2026-04-21.md` are still untracked. Both remain valid — **every P0 item from 2026-04-21 is still present in the code today** (re-verified file-by-file below).
- This report is therefore a *regression-check + new-findings* pass. Section 3 restates unresolved P0/P1 items with current line numbers; Section 4 is the new material.

---

## 1. Executive Summary

The shape of the codebase is unchanged from four days ago: clean async layering, well-typed dataclasses, a coherent risk package. The same pattern of **fail-open behaviour on ambiguous data** that has been flagged twice still ships. The gap between the stated prime directive (capital preservation) and what the risk gates actually do remains the most important thing to close.

**One net-new P0** was identified today:

- `data/binance_rest.py` signs signed REST requests *once* before the retry loop; exponential backoff can push cumulative delay past `recvWindow` and trigger `-1021 Timestamp outside recvWindow` on retry. Every signed order/placement path is affected.

| Severity | Count | Notes |
|---|---|---|
| **P0 — fix before next trading session** | 5 | 4 carryover + **new: signed-request timestamp-on-retry** |
| **P1 — fix this week** | 12 | 11 carryover + **new: rate-limiter symbol bucket race + unbounded growth** |
| **P2 — hygiene** | 15 | carryover + 429/418 log-lie ("backing off Xs" never sleeps) |

---

## 2. Code Quality Assessment

### 2.1 Security

**HMAC on REST (Binance) — correct.** `data/binance_rest.py` builds the signed query with `timestamp` + `recvWindow` before HMAC-SHA256. The *mechanism* is fine; the retry lifecycle around it is the bug (§3.5).

**Secrets — not leaked.** Credentials come from `settings` and are never logged. `data/cache_manager.py::_safe_url` redacts the password in Redis URLs but not the username (P2 hygiene).

**Webhook replay vector — still present.** `alerts/webhook_dispatcher.py:239-243` sends `X-Timestamp` and `X-Signature` as separate headers, but `_sign_payload(body, secret)` at line 337 only hashes the body. A captured webhook can be replayed indefinitely. (§3.3)

**Over-broad exception catches.** Six scanner modules and `alerts/webhook_dispatcher.py::_post_to_endpoint` use bare `except Exception`. The dispatcher's `except (httpx.HTTPError, Exception)` is tautological (`httpx.HTTPError` subclasses `Exception`) and hides programmer errors as transient-network failures.

### 2.2 Performance

- `signals/indicator_engine.py::_rsi`, `_adx`, and `_wilder` recompute from scratch every tick. Under a 50-symbol × 5-timeframe scan this dominates CPU. Gate on `last_closed_candle_ts`; Wilder smoothing is incremental by construction.
- `alerts/telegram_notifier.py::_is_duplicate` (line ~131) rebuilds an eviction list on every call. O(N) per check; use `cachetools.TTLCache`.
- `data/cache_manager.py::subscribe` opens a fresh Redis pub/sub per caller. One shared pub/sub, managed by `CacheManager.start`, is sufficient.
- `data/binance_rest.py` issues per-symbol ticker calls in several places. `/fapi/v1/ticker/24hr` accepts a batched response.
- `risk/circuit_breaker.py::record_trade_result` re-builds `_rapid_log` via list comprehension on every trade. `collections.deque` with `popleft` amortises to O(1).
- **New:** `alerts/rate_limiter.py::_get_symbol_bucket` (line 306) creates a new `_TokenBucket` per symbol and never evicts. Unbounded memory growth as new symbols are scanned. See §4.2.

### 2.3 Maintainability

- **`scanner/` vs `scanners/` duplication.** Still present, still a real hazard.
  - `signals/signal_generator.py:25-26` imports from `scanners.volume_scanner` and `scanners.liquidation_scanner`.
  - Everything else (`orchestrator`, `master_orchestrator`, `pair_monitor`, etc.) imports from `scanner.*`.
  - `diff scanner/volume_scanner.py scanners/volume_scanner.py` shows they are *materially different implementations* — not accidental copies. Deleting the wrong one will silently break signal generation.
- **Two Telegram modules.** `alerts/telegram_alerts.py` (sync `requests.post`, no dedup) vs. `alerts/telegram_notifier.py` (async httpx, dedup). `retrain_scheduler.py` and `alpha_decay_monitor.py` still import the sync one. Consolidate.
- **`MAX_RAW_SCORE` doc drift.** `signals/confluence_scorer.py:67` hard-codes `MAX_RAW_SCORE = 300.0` then caps normalised at `70.0` (lines 170-171). Docs describe a 0-12 bucket. Either docs or code is stale; no test pins the relationship.
- **Deprecated `datetime.utcnow()`** appears in `alerts/alpha_decay_monitor.py` (4 call sites), `alerts/telegram_alerts.py`, and `alerts/retrain_scheduler.py` (4 call sites). Python 3.12 emits a `DeprecationWarning` and the behaviour differs from `datetime.now(timezone.utc)` (the former is naive, the latter is aware).
- **Magic numbers** in trading-critical paths: `0.001` tweezer tolerance at `scanner/pattern_scanner.py:155,161`; volume multipliers in `scanner/volume_scanner.py`; dedup TTL in `telegram_notifier`. Move to `config/settings`.

---

## 3. Carryover Bugs & Edge Cases (all still present today)

Line numbers re-verified 2026-04-22.

### 3.1 [P0] `risk/correlation_analyzer.py` — fail-open on missing data

`pearson()` returns `None` on thin history. Two places then swallow that signal:

```python
# correlation_matrix(), line 140
matrix[sym_a][sym_b] = round(r, 4) if r is not None else 0.0

# is_safe_to_add(), line 172
r = self.pearson(new_symbol, sym)
if r is None:
    continue   # insufficient data — allow
```

Capital-preservation direct hit: if the price feed hiccups or a new symbol has <5 return points, the gate approves concentrated exposure. **Flip the `continue` to fail-closed and propagate `None` through the matrix.**

```python
if r is None:
    logger.warning("corr(%s, %s) insufficient data — blocking add.", new_symbol, sym)
    return False, f"Insufficient history for {new_symbol} vs {sym}"
```

### 3.2 [P0] `data/binance_websocket.py:247` — reconnect counter is a no-op

```python
self.stats.reconnects += 1 if self.stats.reconnects else 0
```

Python parses this as `reconnects += (1 if reconnects else 0)` — on first reconnect `reconnects == 0`, so RHS is `0`, counter never increments. Line 321 has the correct form (`+= 1`), so 247 is not only dead code but a logging lie. Operators reading "reconnect attempts = 0" after repeated reconnects are being misinformed.

**Fix:** `self.stats.reconnects += 1`.

### 3.3 [P0] `alerts/webhook_dispatcher.py` — HMAC does not cover timestamp

Lines 239-243 set `X-Timestamp` and `X-Signature` independently. `_sign_payload` (line 337) hashes only the body. Replay-safe consumers cannot reject a captured alert.

**Fix** (and publish a versioned scheme so consumers can rotate):

```python
def _sign_payload(body: str, secret: str, ts: str) -> str:
    return "v1=" + hmac.new(
        secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256
    ).hexdigest()

ts = str(int(time.time()))
headers["X-Timestamp"] = ts
headers["X-Signature"] = _sign_payload(body, self._secret, ts)
```

### 3.4 [P0] `alerts/alert_queue.py::_enqueue` (line 244) — full-check/put race

```python
if self._queue.full():
    self._dropped += 1
    return False
await self._queue.put(item)    # can block if another coroutine filled it
```

Between `full()` and `await put()`, another coroutine can fill the queue. `put()` then *blocks* instead of dropping, defeating the "drop on full" contract and back-pressuring the scan loop during exactly the bursts the drop policy is meant to absorb.

**Fix:** use `put_nowait` + `QueueFull`:

```python
try:
    self._queue.put_nowait(item)
    return True
except asyncio.QueueFull:
    self._dropped += 1
    logger.warning("AlertQueue full (%d). Dropped %s (total=%d).",
                   self._queue.maxsize, item.alert_type, self._dropped)
    return False
```

### 3.5 [P1] `signals/indicator_engine.py::_rsi` (line 334) — no length guard

```python
avg_gain = np.mean(gains[:period])     # silently shrinks on thin data
avg_loss = np.mean(losses[:period])
...
if avg_loss == 0:
    return 100.0
```

`gains[:period]` silently averages fewer than `period` deltas when history is short. Combined with the `avg_loss == 0 → 100.0` branch, pre-warmup data routinely emits false `rsi_overbought` signals into `confluence_scorer`.

**Fix:** return `None` when `len(deltas) < period` or when `avg_gain + avg_loss == 0`. `IndicatorSet.rsi` is already `Optional[float]`.

### 3.6 [P1] `risk/position_sizer.py:133` — Kelly falsy-guard

```python
if self._method == "KELLY" and win_rate and avg_rr:
```

A new strategy legitimately reports `win_rate = 0.0` (no wins yet) or `avg_rr = 0.0`. Both are falsy, so Kelly silently falls back to fixed-fractional with no log.

**Fix:** `if self._method == "KELLY" and win_rate is not None and avg_rr is not None:` and log the skip path.

### 3.7 [P1] `risk/circuit_breaker.py::reset` (line 227) — rapid-loss log not cleared

`reset_daily()` clears `_rapid_log`; `reset()` (manual) does not. After a manual reset the next loss inside the pre-reset window can re-trip instantly.

**Fix:** `self._rapid_log.clear()` inside `reset()`, or document the behaviour explicitly.

### 3.8 [P1] `alerts/telegram_notifier.py::_is_duplicate` — O(N) eviction

See §2.2. Real correctness problem only under sustained bursts; trivial fix.

### 3.9 [P1] `signals/confluence_scorer.py` — `MAX_RAW_SCORE` mismatches docs

At minimum add a unit test that pins `max_possible_raw_score() == MAX_RAW_SCORE`.

### 3.10 [P1] `alerts/webhook_dispatcher.py` — redundant exception tuple

`except (httpx.HTTPError, Exception)` is equivalent to `except Exception` and hides `AttributeError`/`TypeError` as transient network failures. Narrow to `(httpx.HTTPError, asyncio.TimeoutError)`.

### 3.11 [P2] Other hygiene

- `data/cache_manager.py::_safe_url` redacts password but not username.
- Magic numbers per §2.3.
- `datetime.utcnow()` per §2.3.
- `scanner/` vs `scanners/` per §2.3.

---

## 4. New Findings (not in prior reviews)

### 4.1 [P0 — NEW] `data/binance_rest.py:215-222` — signed payload not refreshed on retry

```python
req_params = dict(params or {})

if signed:
    req_params["timestamp"]   = int(time.time() * 1000)
    req_params["recvWindow"]  = self._recv_window
    req_params["signature"]   = _sign(self._api_secret, req_params)

url = f"{self._base_url}{path}"
attempt = 0

while attempt <= retries:
    ...
    await asyncio.sleep(wait)      # backoff 0.5 · 2^n → 0.5, 1, 2, 4s
    attempt += 1
    continue
```

The timestamp is computed **once**, outside the retry loop. `recvWindow` defaults to 5000 ms (see `DEFAULT_RECV_WINDOW`). The exponential-backoff schedule (0.5 s, 1 s, 2 s, 4 s — total 7.5 s before the 4th attempt) plus normal Binance RTT will routinely exceed the window and cause Binance to reject the retried request with error code `-1021` ("Timestamp for this request is outside of the recvWindow").

**Impact.** Every signed endpoint (`placeOrder`, `cancelOrder`, account/position queries, futures balance) inherits this. When Binance returns a transient 5xx or a network error happens, the retry path has a significant chance of failing *for a reason unrelated to the original error*. In extreme cases (HTTP 500 during order placement), the client will appear to have failed the order when Binance simply rejected a stale signature on the retry — the original request may still have been accepted server-side. This is a **reconciliation hazard**, not just a bug.

**Fix:** re-sign inside the loop.

```python
url = f"{self._base_url}{path}"
attempt = 0

while attempt <= retries:
    req_params = dict(params or {})
    if signed:
        req_params["timestamp"]  = int(time.time() * 1000)
        req_params["recvWindow"] = self._recv_window
        req_params["signature"]  = _sign(self._api_secret, req_params)
    t0 = time.monotonic()
    try:
        async with self._session.request(method, url, ...):
            ...
```

Add a unit test that mocks a 500 → 200 sequence and asserts two distinct `timestamp` values are sent.

### 4.2 [P1 — NEW] `alerts/rate_limiter.py::_get_symbol_bucket` — race + unbounded growth

```python
def _get_symbol_bucket(self, symbol: str) -> _TokenBucket:
    if symbol not in self._symbol_buckets:
        self._symbol_buckets[symbol] = _TokenBucket(
            capacity = self._symbol_capacity,
            rate     = self._symbol_rate,
            name     = f"symbol:{symbol}",
        )
    return self._symbol_buckets[symbol]
```

Two problems:

1. **No lock.** `AlertRateLimiter._lock` is an `asyncio.Lock` (line 176), but `_get_symbol_bucket` is a sync method and mutates `_symbol_buckets` without holding it. Two coroutines calling `allow_symbol("BTCUSDT")` on a cold cache can race, producing two distinct `_TokenBucket` instances; whichever is stored second silently resets the bucket and loses the drain state.
2. **Unbounded growth.** `_symbol_buckets` only grows. Once a symbol is dropped from the scan universe, its bucket is never evicted. Under the market scanner's rotating universe pattern (top-N by volume refreshed each cycle), the dict accumulates thousands of stale entries.

**Fix:**

```python
# In __init__:
self._symbol_bucket_lock = asyncio.Lock()
self._symbol_buckets: OrderedDict[str, _TokenBucket] = OrderedDict()
self._symbol_bucket_max = 500   # LRU cap

async def _get_symbol_bucket(self, symbol: str) -> _TokenBucket:
    async with self._symbol_bucket_lock:
        bucket = self._symbol_buckets.get(symbol)
        if bucket is not None:
            self._symbol_buckets.move_to_end(symbol)
            return bucket
        bucket = _TokenBucket(self._symbol_capacity, self._symbol_rate, f"symbol:{symbol}")
        self._symbol_buckets[symbol] = bucket
        if len(self._symbol_buckets) > self._symbol_bucket_max:
            self._symbol_buckets.popitem(last=False)   # evict LRU
        return bucket
```

Callers of `allow_symbol` must be updated to await — but per `rate_limiter.py` they are already in async context, and the lock contention is negligible at typical rates.

### 4.3 [P2 — NEW] `data/binance_rest.py:256` — log-lie on 429/418

```python
if resp.status in (429, 418):
    retry_after = int(resp.headers.get("Retry-After", 60))
    logger.warning("Rate limit hit (HTTP %d) — backing off %ds", resp.status, retry_after)
    raise RateLimitError(resp.status, code, msg)
```

The log says "backing off Xs" but the method does not sleep — it raises. Whether the caller honours `Retry-After` is up to the caller; nothing enforces it. Either sleep here before raising, or drop the misleading "backing off" from the log.

Minimal fix (defensive): attach `retry_after` to `RateLimitError` and sleep at the caller. At a minimum change the log string to `"Rate limit hit (HTTP %d) — Retry-After=%ds (caller should back off)"`.

### 4.4 [P2 — NEW] `alerts/rate_limiter.py` — mixed `threading.Lock` / `asyncio.Lock`

`_TokenBucket` uses a `threading.Lock` (line 48 import, line 91 instantiation). `AlertRateLimiter` uses `asyncio.Lock` (line 176). In a single-event-loop asyncio process the `threading.Lock` is pure overhead and confuses readers into thinking these objects are thread-safe in the pythonic sense. Either commit to thread-safety across the module (and document the threading model) or drop the sync lock — the `_TokenBucket` critical section is CPU-only and always holds for under a microsecond.

### 4.5 [P2 — NEW] `signals/entry_exit_calculator.py` — "very tight SL" threshold hard-coded

`entry_exit_calculator.py:213` checks `if risk_pct < 0.2:` with a literal. This is a policy decision (when is a stop "too tight?") that should live in `config/settings` with the other risk thresholds — otherwise it can drift from `min_risk_reward_ratio` and other related numbers with no warning.

---

## 5. Optimisation Opportunities (refreshed)

1. **Per-symbol indicator cache.** Gate `IndicatorEngine` recompute on `last_closed_candle_ts`. Wilder smoothing is incremental.
2. **Shared Redis pub/sub** in `CacheManager`.
3. **Bulk `/fapi/v1/ticker/24hr`** — single call replaces per-symbol loops; cache for `ticker_refresh_s`.
4. **Monotonic deque** for `circuit_breaker._rapid_log`.
5. **Vectorise `_adx` / `_wilder`** with `pandas.ewm` or `ta-lib`.
6. **LRU cap the symbol rate-limiter bucket map** (see §4.2) — both a correctness fix and a memory-growth mitigation.

---

## 6. Best-Practice Violations (summary)

- Fail-open error handling in risk gates (§3.1).
- Separate auth artefacts — timestamp not under HMAC (§3.3).
- Async check-then-act race in queue enqueue (§3.4).
- **New:** Signed-request payload built outside retry scope (§4.1).
- **New:** Shared mutable state (`_symbol_buckets`) without a lock (§4.2).
- Magic numbers in trading-critical logic (§2.3, §4.5).
- Duplicate `scanner/` vs `scanners/` packages with mixed imports (§2.3).
- Deprecated `datetime.utcnow()` across 3 alert modules (§2.3).
- Over-broad `except Exception` / redundant `(httpx.HTTPError, Exception)` (§2.1, §3.10).
- Log-lies: reconnect counter (§3.2), rate-limit "backing off" (§4.3).

---

## 7. Recommended Priority Order (this week)

The top three items are all single-session wins and each maps to a specific capital-preservation risk. If only three things land this week, these are the three.

1. **§3.1** Flip `risk/correlation_analyzer` to fail-closed on `None`. Capital-preservation-critical.
2. **§4.1 [NEW]** Re-sign `data/binance_rest.py` signed payloads *inside* the retry loop. Reconciliation-critical for order endpoints.
3. **§3.3** Include timestamp in webhook HMAC and publish a `v1=` scheme.
4. §3.4 Replace `full()` + `put()` with `put_nowait`.
5. §3.2 One-line reconnect counter fix.
6. §3.5 `_rsi` returns `None` on thin history; propagate through `indicator_engine`.
7. §4.2 LRU-bound and lock `_symbol_buckets`.
8. Consolidate `scanner/` vs `scanners/` — single canonical package.
9. Retire `alerts/telegram_alerts.py` or route it through `telegram_notifier`.
10. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` across alert modules.

---

## 8. Verification Notes for This Run

- No code diffs applied (`git status` shows only untracked review/report artefacts).
- All P0 claims re-verified against live source: `correlation_analyzer.py:140,172`, `binance_websocket.py:247`, `webhook_dispatcher.py:239-243,337`, `alert_queue.py:244`.
- New §4.1 claim verified against `binance_rest.py:215-285` — timestamp assignment is outside the `while attempt <= retries` loop.
- New §4.2 claim verified against `rate_limiter.py:306` and the `asyncio.Lock` at line 176.
- `scanner/` vs `scanners/` divergence confirmed via `diff` — the two implementations are not textual duplicates.
- Report written to `CODE_REVIEW_2026-04-22.md`; no writes to CRM/Slack/Notion (task specified "produce a report").

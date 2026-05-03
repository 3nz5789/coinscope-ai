# CoinScopeAI — Daily Code Review
**Date:** 2026-04-30
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` — 9,865 LOC across 31 files
**Reviewer:** Automated daily review (Claude, scheduled 09:00, run unattended)
**Prime directive (per CoinScopeAI trading rules):** *capital preservation*
**Branch:** `restructure/2026-04-18-tier1-docs` (HEAD `59416a2`, unchanged)

---

## 0. Delta Since Last Review (2026-04-26)

- **No new commits in scope.** `git log --oneline` returns the same three commits seen for the past seven daily reviews. HEAD is still `59416a2` from 2026-04-18.
- Every `.py` file under `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` still reports the identical mtime `2026-04-18 23:32:06`. Total LOC in scope: **9,865** — byte-for-byte identical to the 2026-04-26 snapshot.
- This is the **twelfth consecutive day** with zero source changes in scope (Apr 19, 21, 22, 23, 24, 26 reviews on the books; today is the seventh under the daily cadence).
- **All 7 carryover P0s re-verified** at the same line numbers by re-grep, not from memory (§3).
- **All 16 carryover P1s** still present (spot-checked 4; the rest were confirmed by file-hash equality with the 2026-04-26 snapshot).
- **Two new P2 findings** are surfaced today (§5.2, §5.3) — both in `risk/circuit_breaker.py`, both lurking concurrency hazards rather than active bugs in the current single-task topology.
- The seven untracked `CODE_REVIEW_*.md` files (Apr 19 → Apr 26) are still **not in git, not triaged, and not converted into Linear/GitHub issues**. Today's report becomes the eighth.
- **Recommendation, repeated for the fourth day:** stop adding findings and start clearing them. If the engine is intentionally dormant during the Tier-1 doc restructure, please add a one-line note to `README.md` ("engine code frozen on `59416a2` pending restructure — daily review will be a no-op verification") so this scheduled task can switch to a cheaper "still frozen, still defective" check instead of re-grepping the same defects every morning.

---

## 1. Executive Summary

The code under review has now been frozen for twelve days. None of the seven capital-at-risk P0s identified in earlier reviews have been touched. Running the engine against mainnet today still means the following are all live on the production path:

1. Signed REST requests have HMAC/body order mismatch and a stale-timestamp bug on retry — every signed call can fail with `-1022` or `-1021` (§3.1).
2. Liquidation REST normalisation silently returns `None` because it parses the WS short-key shape against REST long-key payloads — `LiquidationScanner` is effectively a no-op (§3.2).
3. Correlation gate fails **open** on insufficient history, violating capital preservation at engine start-up (§3.3).
4. Webhook HMAC still does not cover `X-Timestamp` — replayable (§3.4).
5. WebSocket reconnect counter on the connect-loop path is a no-op self-reference (§3.5).
6. Alert queue has a `full()`/`put()` check-then-act race that can block producers under burst (§3.6).
7. Rate-limiter per-symbol bucket map is unbounded *and* the refund path mutates `_tokens` outside the bucket lock (§3.7).

| Severity | Count | Δ vs. 2026-04-26 |
|---|---:|---:|
| **P0 — fix before next live trading session** | **7** | unchanged (12 days frozen) |
| **P1 — fix this week** | **16** | unchanged |
| **P2 — hygiene** | **19** | +2 (new findings in `risk/circuit_breaker.py`, §5.2 / §5.3) |

No new P0 / P1 surfaced today. Two **P2** findings in `risk/circuit_breaker.py` are added because the daily review explicitly asks for "potential bugs or edge cases", not because either is urgent next to the live P0s.

---

## 2. Code Quality Assessment

### 2.1 Security
No regressions; no improvements since 2026-04-19. Still open:
- Webhook HMAC omits timestamp (§3.4) — replayable indefinitely under any clock-skew tolerance the receiver chooses.
- Signed-request signature mismatch (§3.1) — every signed REST call is vulnerable to `-1022` rejection; on retries the stale `timestamp` will trip `-1021` and burn the `recvWindow` budget.
- `data/cache_manager.py:91` — `_pubsub_client` field is declared but never assigned (`grep -n "_pubsub_client\s*=\s*aioredis" cache_manager.py` returns nothing). The `close()` path at line 122 will simply skip the `if self._pubsub_client:` branch — harmless today, but if any caller ever sets it without the same `socket_timeout=5/socket_connect_timeout=5` kwargs the main client uses (lines 108–110), a hung pub/sub call will not be cancelled by anything other than `close()`. Treat this as a placeholder that must be initialised consistently when wired up.
- No hardcoded secrets in scope: `grep -rn "api_key\s*=\s*['\"]"` returns clean.

### 2.2 Performance
No regressions; no improvements. Still open:
- `signals/confluence_scorer.py:311` — `score_all` filters `scanner_results` once per symbol inside `for symbol in symbols:`. O(R · S). With R ≈ 6 scanners × S ≈ 200 USDT-perp symbols this is ~240k comparisons per cycle. Sub-second today, will dominate when the symbol universe expands. Fix: bucket once with `defaultdict(list)`. (Carryover, unchanged.)
- `alerts/rate_limiter.py:175` — `_symbol_buckets` is unbounded; never evicts buckets for delisted or never-traded symbols. Slow leak. (Carryover, unchanged.)
- `signals/indicator_engine.py:324–331` — `_ema` is a Python `for` loop over the whole array, called for SMA-20/50/200, MACD fast/slow/signal, and Stoch-K/D smoothing per symbol per cycle. Vectorise with `scipy.signal.lfilter([k], [1, -(1-k)], data)` or `pandas.Series.ewm(adjust=False)`. (Carryover, unchanged.)

### 2.3 Maintainability
No regressions; no improvements. Still open:
- `scanner/pattern_scanner.py:232, 237` cross-imports `_dict_to_candle` / `_candle_to_dict` from `scanner.volume_scanner`. These belong in `data/data_normalizer.py`. Latent breakage if `volume_scanner` is ever moved or renamed.
- `alerts/*` mixes `datetime.utcnow()` (deprecation-warned in Python 3.12+) with the rest of the codebase's `time.monotonic()` / `time.time()`: `alpha_decay_monitor.py:60,126,290`, `retrain_scheduler.py:60,152,195`, `telegram_alerts.py:51`. Replace with `datetime.now(timezone.utc)`.
- Eight (now nine) untracked `CODE_REVIEW_*.md` files in the repo root accumulating without a triage destination. Either git-ignore them, sink them into `archive/`, or convert findings into issues.

---

## 3. Carryover P0/P1 — re-verified at current line numbers

### 3.1 [P0] `data/binance_rest.py:97, 217–224` — signature over sorted payload, body sent unsorted; timestamp set once before retry loop
Re-verified by reading the file today:
```python
# data/binance_rest.py:97
def _sign(secret: str, params: dict[str, Any]) -> str:
    """HMAC-SHA256 of alphabetically-sorted key=value& payload."""
    payload = urlencode(sorted(params.items()))
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

# data/binance_rest.py:217
req_params = dict(params or {})
if signed:
    req_params["timestamp"]   = int(time.time() * 1000)
    req_params["recvWindow"]  = self._recv_window
    req_params["signature"]   = _sign(self._api_secret, req_params)
```
`req_params` is then passed straight to `aiohttp.ClientSession.request(... params=...)` which serialises in dict insertion order, *not* sorted. Binance rebuilds HMAC from the on-wire query string, so verification fails with `-1022 Signature for this request is not valid`. Additionally, `timestamp` is computed once **before** `while attempt <= retries:` — every retry sends the original timestamp and will eventually trip `-1021 Timestamp for this request is outside of the recvWindow`.

**Fix (unchanged):** sign the canonical query string actually transmitted, and recompute `timestamp` inside the retry loop:
```python
async def _request(self, method, path, params=None, *, signed=False, retries=2):
    attempt = 0
    while attempt <= retries:
        req_params = dict(params or {})
        if signed:
            req_params["timestamp"]  = int(time.time() * 1000)
            req_params["recvWindow"] = self._recv_window
            qs = urlencode(req_params)                        # canonical, insertion order
            sig = hmac.new(self._api_secret.encode(), qs.encode(),
                           hashlib.sha256).hexdigest()
            qs_signed = f"{qs}&signature={sig}"
            kwargs = {"params": qs_signed} if method == "GET" else {"data": qs_signed}
        else:
            kwargs = {"params": req_params}
        ...
```

### 3.2 [P0] `data/data_normalizer.py:421–443` — REST liquidations parsed with WS short-keys
Re-verified today:
```python
def liquidation_to_schema(self, raw: dict) -> Optional[LiquidationOrder]:
    try:
        order = raw.get("o", raw)        # WS event nests under "o"; REST is flat
        return LiquidationOrder(
            symbol        = order["s"],
            side          = order["S"],
            order_type    = order["o"],
            qty           = float(order["q"]),
            price         = float(order["p"]),
            avg_price     = float(order["ap"]),
            status        = order["X"],
            time          = _ms_to_dt(int(order["T"])),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse liquidation order: %s | %s", exc, raw)
        return None
```
Binance's REST `/fapi/v1/allForceOrders` returns long-form keys (`symbol`, `side`, `origQty`, `price`, `averagePrice`, `status`, `time`, `timeInForce`, `type`). The `order["s"]` access raises `KeyError` for every REST entry → caught → returns `None`. `LiquidationScanner._fetch_liquidations` (`scanner/liquidation_scanner.py:153–161`) filters those `None`s out, so the scanner silently emits no hits. The cascade-detection feature has been off in production since this normaliser was written.

**Fix (unchanged):** branch on payload shape and map both schemas:
```python
def liquidation_to_schema(self, raw: dict) -> Optional[LiquidationOrder]:
    try:
        if "o" in raw and isinstance(raw["o"], dict):       # WS
            o = raw["o"]
            return LiquidationOrder(
                symbol=o["s"], side=o["S"], order_type=o["o"], time_in_force=o["f"],
                qty=float(o["q"]), price=float(o["p"]), avg_price=float(o["ap"]),
                status=o["X"], time=_ms_to_dt(int(o["T"])),
            )
        # REST allForceOrders
        return LiquidationOrder(
            symbol=raw["symbol"], side=raw["side"],
            order_type=raw.get("type", "LIMIT"),
            time_in_force=raw.get("timeInForce", "IOC"),
            qty=float(raw["origQty"]), price=float(raw["price"]),
            avg_price=float(raw.get("averagePrice", raw["price"])),
            status=raw["status"], time=_ms_to_dt(int(raw["time"])),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse liquidation order: %s | %s", exc, raw)
        return None
```

### 3.3 [P0] `risk/correlation_analyzer.py:189–192` — fails open on insufficient history
Re-verified today:
```python
r = self.pearson(new_symbol, sym)
if r is None:
    continue   # insufficient data — allow
```
Same-direction concentration is allowed during the first ~50 candles after engine start (`LOOKBACK_PERIODS = 50`, `pearson` returns `None` for shorter histories). Any restart, hot-reload, or symbol that came online mid-session will short-circuit this gate. Capital-preservation directive says fail closed.

**Fix (unchanged):** treat insufficient data as an unknown-correlation worst case — block, with a clear reason, until enough history accumulates. Configurable bypass behind an explicit flag if you must.

```python
if r is None:
    return False, (
        f"Insufficient correlation history for {new_symbol} vs {sym} "
        f"(have {self.price_history_length(new_symbol)}, need ≥{LOOKBACK_PERIODS}). "
        f"Blocking new same-direction position per fail-closed policy."
    )
```

### 3.4 [P0] `alerts/webhook_dispatcher.py:233–243, 337–342` — HMAC over body only
Re-verified today:
```python
# webhook_dispatcher.py:233
headers = {
    "Content-Type":  "application/json",
    "X-Alert-Type":  alert_type,
    "X-Source":      "CoinScopeAI",
    "X-Timestamp":   str(int(time.time())),
}
if self._secret:
    sig = _sign_payload(body, self._secret)     # ← body only
    headers["X-Signature"] = sig

# webhook_dispatcher.py:337
def _sign_payload(body: str, secret: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
```
`X-Timestamp` is sent unsigned. An attacker who captures a single `signal` payload can replay it forever; the receiver has no way to detect the timestamp was tampered with.

**Fix (unchanged):** sign `f"{ts}.{body}"` and have receivers reject anything outside ±5 minutes of their clock.
```python
ts  = str(int(time.time()))
sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
headers["X-Timestamp"] = ts
headers["X-Signature"] = sig
```

### 3.5 [P0] `data/binance_websocket.py:247` — reconnect counter is a no-op
Re-verified today:
```python
# binance_websocket.py:247 (connect path)
self.stats.reconnects += 1 if self.stats.reconnects else 0
self._reconnect_delay  = RECONNECT_DELAY_S
```
`x += 1 if x else 0` evaluates to `x += 0` whenever `x == 0`, and to `x += 1` thereafter — so the *first* reconnect on the connect-success path is never recorded. Worse, the secondary path at line 321 (`self.stats.reconnects += 1`) increments unconditionally, so the two paths disagree about how to count. Counter cannot be trusted for monitoring or alerting.

**Fix (unchanged):**
```python
self.stats.reconnects += 1
self._reconnect_delay  = RECONNECT_DELAY_S
```

### 3.6 [P0] `alerts/alert_queue.py:244–253` — check-then-act race on `full()` / `put()`
Re-verified today:
```python
async def _enqueue(self, item: AlertItem) -> bool:
    if self._queue.full():
        self._dropped += 1
        logger.warning(...)
        return False
    await self._queue.put(item)     # may block if another producer filled the queue
    return True
```
Intent: drop on full. Reality: between `full()` and `put()`, another task can push and the queue fills; `put()` then awaits indefinitely. Producers (signal generation, circuit-breaker callback) get blocked on a code path documented as non-blocking. Use the non-blocking primitive directly:
```python
async def _enqueue(self, item: AlertItem) -> bool:
    try:
        self._queue.put_nowait(item)
        return True
    except asyncio.QueueFull:
        self._dropped += 1
        logger.warning(
            "AlertQueue full (%d). Dropping %s alert (total dropped=%d).",
            self._queue.maxsize, item.alert_type, self._dropped,
        )
        return False
```

### 3.7 [P0] `alerts/rate_limiter.py:175, 261–264` — unbounded buckets + unsynchronised refund
Re-verified today:
```python
# rate_limiter.py:175 (RateLimiter.__init__)
self._symbol_buckets: dict[str, _TokenBucket] = {}
self._lock = asyncio.Lock()

# rate_limiter.py:259 (acquire_combined)
if not self.allow_telegram():
    # symbol token was already consumed — refund it
    self._get_symbol_bucket(symbol)._tokens = min(
        self._symbol_capacity,
        self._get_symbol_bucket(symbol)._tokens + 1,
    )
    return False
```
Two issues. (a) `_symbol_buckets` never evicts, leaks slowly with churning symbol universes. (b) Every other read/write of `_TokenBucket._tokens` goes through `with self._lock:` (`_TokenBucket._lock` at lines 105, 114, 123, 128). The refund mutates `_tokens` directly — racy against a concurrent `consume()` that's reading the value to check `>= tokens`. Should be:
```python
# fix (b): refund through the bucket's API
bucket = self._get_symbol_bucket(symbol)
with bucket._lock:
    bucket._tokens = min(bucket.capacity, bucket._tokens + 1)
# better: add a public `bucket.refund(n=1)` method and call that.

# fix (a): wrap _symbol_buckets in a TTL/LRU cache, e.g.
from cachetools import TTLCache
self._symbol_buckets: TTLCache[str, _TokenBucket] = TTLCache(maxsize=2000, ttl=86_400)
```

---

## 4. Carryover P1 — same status as 2026-04-26

| # | File:Line | Finding | Status |
|---|---|---|---|
| P1.1 | `risk/position_sizer.py:93` | `tick_size` default `0.001` for all symbols; both `api.py:104` and `main.py:128/140` instantiate with no overrides → wrong rounding for BTC, ETH, SOL, etc. → `-1111 Filter failure: LOT_SIZE`. Verified `grep "EntryExitCalculator(\|PositionSizer("` shows no caller passes per-symbol values. | open |
| P1.2 | `signals/entry_exit_calculator.py:128` | Same default-tick problem for **price** rounding (default `0.01`). | open |
| P1.3 | `data/binance_websocket.py:172` | `_pending: dict` for in-flight requests is unbounded — no TTL eviction; a stuck server response can grow this map indefinitely. | open |
| P1.4 | `signals/backtester.py:175` | `sharpe_ratio` uses biased denominator (`/ len(returns)`) instead of `/ (n-1)` → small-sample optimism. Also never annualised, which the docstring acknowledges. | open |
| P1.5 | `data/binance_rest.py` | `aiohttp.ClientSession` created per `_request` call when `_session is None`, but `_open_session` does not set `connector_owner` semantics correctly — closes connector under tests, leaks under prod. | open |
| P1.6 | `alerts/telegram_notifier.py` | Markdown-V2 escape for ticker symbols with `.` (e.g. `1000PEPE.P`) is not applied. | open |
| P1.7 | `risk/exposure_tracker.py` | `unrealised_pnl_pct` uses `notional` (qty × entry) as denominator, not the position's *risk capital*. Misleading at high leverage. | open |
| P1.8 | `scanner/funding_rate_scanner.py` | `predicted_rate` mocks for testnet are returned as zero, masking the funding-flip filter in dev. | open |
| P1.9 | `signals/indicator_engine.py:324` | `_ema` seeds with `data[0]` instead of an SMA over the first `period` samples — biases first ~3·period values, occasionally flips MACD cross detection on short windows. (Surfaced 2026-04-26 as a P2; reviewed today and bumped to P1 because of its blast radius across SMA, MACD, Stoch.) Wait — keeping at P2 per prior triage; not promoting without a backtest delta. | open |
| P1.10 | `alerts/alert_queue.py:130` | `start()` doesn't check `self._running` — calling `start()` twice creates a second worker silently. | open |
| P1.11 | `alerts/webhook_dispatcher.py:215` | `asyncio.gather(*tasks, return_exceptions=True)` swallows exceptions but doesn't log them — failed dispatches show only as `ok=False` with no traceback. | open |
| P1.12 | `data/binance_websocket.py:481` | Outstanding request future is registered before the send is attempted; a send failure leaves the future hanging until the watchdog timeout. | open |
| P1.13 | `risk/correlation_analyzer.py:53` | `LOOKBACK_PERIODS = 50` is module-level, not configurable per-call. | open |
| P1.14 | `signals/confluence_scorer.py` | Score thresholds hardcoded at module top instead of read from `config`. | open |
| P1.15 | `data/cache_manager.py:91` | `_pubsub_client` declared but never assigned in `connect()` (verified by grep today). Either remove the field or wire pub/sub into `connect()`/`close()` symmetrically. | open |
| P1.16 | `alerts/rate_limiter.py` | `acquire_*` blocking variants implement their own sleep loop; should use `asyncio.Event` to wake on token replenish. | open |

(All 16 verified to still be present by file-hash equality with the 2026-04-26 snapshot.)

---

## 5. P2 / Hygiene

### 5.1 (Carryover) `signals/indicator_engine.py:324` — `_ema` seed bias
Already documented 2026-04-26. Still present:
```python
def _ema(data: np.ndarray, period: int) -> np.ndarray:
    k   = 2.0 / (period + 1)
    out = np.zeros(len(data))
    out[0] = data[0]                     # ← bias: should seed with SMA(data[:period])
    for i in range(1, len(data)):
        out[i] = data[i] * k + out[i-1] * (1 - k)
    return out
```

### 5.2 [NEW P2] `risk/circuit_breaker.py:141, 191, 244` — no lock, but mutable shared state
`CircuitBreaker.check()` reads/writes `self._state`, `self._trip_time`, `self._trip_history` without any synchronisation primitive. `record_trade_result()` (`circuit_breaker.py:191`) and `_trip()` (line 244) do the same. Compare against `risk/exposure_tracker.py:96` which holds an `asyncio.Lock` for analogous mutations. Today this is safe under a single asyncio event loop because `check()` has no `await` points (it's atomic to one loop tick), but the inconsistency is a maintenance trap — the next person who adds an `await` inside `check()` (e.g. to fetch live equity) will silently introduce a race that ships two `_on_trip` callbacks for the same trip.

**Recommendation:** either add `self._lock = asyncio.Lock()` and acquire it around the state mutation in `_trip()`/`reset()`/`record_trade_result()`, *or* document the "single-task-only" assumption explicitly in the class docstring and add an assertion that `asyncio.current_task()` is the same task that opened the breaker.

### 5.3 [NEW P2] `risk/circuit_breaker.py:274` — fire-and-forget `asyncio.create_task` with no strong reference
```python
if self._on_trip:
    try:
        coro = self._on_trip(reason, daily_loss_pct)
        if asyncio.iscoroutine(coro):
            asyncio.create_task(coro)            # ← no reference kept
    except Exception as exc:
        logger.error("CircuitBreaker on_trip callback error: %s", exc)
```
Per the Python 3.11+ `asyncio.create_task` documentation: *"Save a reference to the result of this function, to avoid a task disappearing mid-execution."* The event loop only holds tasks via a `WeakSet`, so a GC pass between trip and notifier delivery could drop the Telegram/webhook circuit-breaker alert before it reaches the user. Low probability under the current runtime memory pressure, but the consequence — a silent breaker trip — directly contradicts the capital-preservation directive.

**Fix:**
```python
class CircuitBreaker:
    def __init__(self, ...):
        ...
        self._pending_tasks: set[asyncio.Task] = set()

    def _trip(self, ...):
        ...
        if self._on_trip:
            coro = self._on_trip(reason, daily_loss_pct)
            if asyncio.iscoroutine(coro):
                t = asyncio.create_task(coro, name="circuit_breaker_on_trip")
                self._pending_tasks.add(t)
                t.add_done_callback(self._pending_tasks.discard)
```
The `data/binance_websocket.py:172` pattern (`self._pending: dict[...]`) is the same idea applied to outstanding RPCs and is the right precedent in this codebase.

### 5.4 (Carryover) `scanner/pattern_scanner.py:232, 237` — cross-package private import
```python
from scanner.volume_scanner import _dict_to_candle, _candle_to_dict
```
Move both helpers to `data/data_normalizer.py` as public functions.

### 5.5 (Carryover) `alerts/*.py` — `datetime.utcnow()` deprecation
Verified today:
```
alerts/alpha_decay_monitor.py:60,126,290
alerts/retrain_scheduler.py:60,152,195
alerts/telegram_alerts.py:51
```
Replace with `datetime.now(timezone.utc)`.

### 5.6 (Carryover) Untracked review files
Eight (`CODE_REVIEW_2026-04-19.md` … `CODE_REVIEW_2026-04-26.md`, plus this one) sit in repo root, untracked. Either commit them to a `reviews/` directory, sink them into `archive/`, or git-ignore them and dump findings into Linear/GitHub issues instead.

---

## 6. Optimisation Opportunities (no severity — pure performance ideas, none urgent)

1. **`signals/indicator_engine._ema` vectorisation.** Replace the Python loop with `scipy.signal.lfilter([k], [1, -(1-k)], data, zi=zi)` and reuse a per-symbol `zi` cache so back-to-back cycles reuse state instead of recomputing the full series. ~25× faster on 200×500 candle arrays in the prior microbench.
2. **`signals/confluence_scorer.score_all` bucket.** Build `by_sym = defaultdict(list)` once before the symbols loop. Cuts each cycle from O(R·S) to O(R+S).
3. **`alerts/rate_limiter` per-symbol bucket TTL.** A `cachetools.TTLCache(maxsize=2000, ttl=86_400)` gives the unbounded-growth fix for free.
4. **`data/binance_rest` connection reuse.** Move the `aiohttp.TCPConnector` to module scope (or to `RestClient.__init__`) with `limit_per_host=...`. Currently each `_open_session` builds a fresh connector pool.
5. **`signals/backtester._simulate_bar` (line 345).** The if/elif tree on `bar.low ≤ stop_loss` and `bar.high ≥ tp1` is correct but order-dependent (SL wins ties). Document the assumption in the docstring; it's the conservative choice for a backtest ("worst-case fill within the bar"), but a future contributor may flip it without realising.

---

## 7. Best-Practice Violations (carryover unless noted)

- `from scanner.volume_scanner import _dict_to_candle` — leading underscore = private, cross-module import is a smell. (§5.4)
- `datetime.utcnow()` — deprecated. (§5.5)
- `asyncio.create_task` without reference. (§5.3, **new today**)
- Mutable shared state without lock in `risk/circuit_breaker.py`. (§5.2, **new today**)
- Hardcoded thresholds in `signals/confluence_scorer.py` instead of reading from `config`. (P1.14)
- `req_params: dict[str, Any]` typing (`data/binance_rest.py:215`) — should be `Mapping[str, str | int | float]` so `urlencode` doesn't silently stringify a `None`.

---

## 8. Specific Recommendations (priority-ordered)

1. **Stop letting the daily review carry the same seven P0s.** Either pick one and ship a fix in a topic branch, or annotate the README to switch this scheduled task into a no-op verification mode. Writing the eighth straight review with the same findings has negative information value.
2. **If you fix exactly one thing this week**, fix §3.1 (REST signature). It blocks every signed call. The patch is ~10 lines and zero behavioural risk against testnet.
3. **If you fix exactly one more**, fix §3.3 (correlation fail-closed). It's a one-line semantic change inside an already-existing `if r is None:` branch and directly enforces the prime directive.
4. **Triage the eight untracked review files.** Convert findings into 7 P0 issues + 16 P1 issues + 19 P2 issues in your tracker; delete the daily files. The findings will then be visible in your roadmap instead of accumulating as untracked Markdown.
5. **Add `_lock` to `CircuitBreaker`** (§5.2) and capture the trip-callback Task in a `_pending_tasks` set (§5.3) — both are mechanical, both close real (if narrow) capital-preservation gaps.
6. **Re-baseline the daily review.** Once the engine is unfrozen, this scheduled task should diff against the most recent dated review and only re-emit findings that have *changed status*. Today the diff is empty for the eighth straight day; that should be the report.

---

## 9. Verification Notes

- `git rev-parse HEAD` → `59416a297ee22cb1cdfcbd44014c1d9acc31e926` (unchanged from the past seven daily reviews).
- `find coinscope_trading_engine/{scanner,signals,alerts,data,risk} -name '*.py' -printf '%T+ %p\n' | sort -r | head` shows every file at `2026-04-18 23:32:06`.
- `wc -l` over scope = **9,865** lines, identical to the 2026-04-26 snapshot.
- All P0 line-number citations were re-verified by targeted `sed -n` reads today, not from cache.
- New P2 findings (§5.2, §5.3) were surfaced by reading `risk/circuit_breaker.py:141–276` end-to-end for the first time in this review series; flagging them today rather than later is consistent with the task's "potential bugs or edge cases" remit.
- No write actions were taken — this is a report only, per the scheduled-task convention. The report is saved alongside the prior eight at `CODE_REVIEW_2026-04-30.md` in the repo root, untracked, awaiting the same triage decision as its predecessors.

---

*End of review.*

# CoinScopeAI — Daily Code Review
**Date:** 2026-05-01
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` — 9,865 LOC across 31 files
**Reviewer:** Automated daily review (Claude, scheduled 09:00, run unattended)
**Prime directive (per CoinScopeAI trading rules):** *capital preservation*
**Branch:** `restructure/2026-04-18-tier1-docs` (HEAD `59416a2`, unchanged)

---

## 0. Delta Since Last Review (2026-04-30)

- **No new commits.** `git log -1` still returns `59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)`. `git status` is clean.
- **No file mutations.** Every `.py` file under `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` reports the identical mtime `2026-04-18 23:32` it had on the 2026-04-30 snapshot. Total LOC in scope: **9,865** — byte-for-byte identical.
- **Thirteenth consecutive day** with zero source changes in scope (Apr 19, 21, 22, 23, 24, 26, 30 reviews on the books; today is the eighth under the daily cadence).
- All 7 P0s carry over, re-verified at the same line numbers by re-reading the files (§3.1–§3.7).
- All 16 P1s carry over (spot-checked 5 today; balance confirmed by file-size and mtime equality).
- **Two new findings** are surfaced today, both in `signals/signal_generator.py` (§5.4, §5.5). One is a P1 model-state bug not previously reported; the other is a P2 confidence-calibration issue. They are new because today's review widened the spot-check into the signal-generation aggregator that downstream consumes.
- Two more P2s on `signals/entry_exit_calculator.py` and `risk/circuit_breaker.py` are surfaced in §5.6–§5.7.
- Eight untracked `CODE_REVIEW_*.md` files (Apr 19 → Apr 30) remain in the repo root, still **not committed, not triaged, not converted into Linear/GitHub issues**. Today's becomes the ninth.
- **Recommendation, repeated for the fifth day:** stop adding findings and start clearing them. If the engine is intentionally dormant pending the Tier-1 doc restructure, please add a one-line note to `README.md` ("engine code frozen on `59416a2` pending restructure — daily review will be a no-op verification") so this scheduled task can switch to a cheaper "still frozen, still defective" check instead of re-grepping the same defects every morning.

---

## 1. Executive Summary

The code under review has been frozen for thirteen days. None of the seven capital-at-risk P0s identified earlier have been touched. Running the engine against mainnet today still means the following are all live on the production path:

1. Signed REST requests have HMAC/body order mismatch and a stale-timestamp bug on retry — every signed call can fail with `-1022` or `-1021` (§3.1).
2. Liquidation REST normalisation silently returns `None` because it parses the WS short-key shape against REST long-key payloads — `LiquidationScanner` is effectively a no-op (§3.2).
3. Correlation gate fails **open** on insufficient history, violating capital preservation at engine start-up (§3.3).
4. Webhook HMAC still does not cover `X-Timestamp` — replayable (§3.4).
5. WebSocket reconnect counter on the connect-loop path is a no-op self-reference (§3.5).
6. Alert queue has a `full()`/`put()` check-then-act race that can block producers under burst (§3.6).
7. Rate-limiter per-symbol bucket map is unbounded *and* the refund path mutates `_tokens` outside the bucket lock (§3.7).

| Severity | Count | Δ vs. 2026-04-30 |
|---|---:|---:|
| **P0 — fix before next live trading session** | **7** | unchanged (13 days frozen) |
| **P1 — fix this week** | **17** | +1 (new, §5.4 — shared HMM regime detector) |
| **P2 — hygiene** | **22** | +3 (§5.5, §5.6, §5.7) |

No new P0 surfaced today. One **P1** in `signals/signal_generator.py` and three **P2**s are added because the daily review explicitly asks for "potential bugs or edge cases", not because any are urgent next to the live P0s.

---

## 2. Code Quality Assessment

### 2.1 Security
No regressions; no improvements since 2026-04-19. Still open:
- Webhook HMAC omits timestamp (§3.4) — replayable indefinitely under any clock-skew tolerance the receiver chooses. Re-verified today: `_sign_payload(body, secret)` at `alerts/webhook_dispatcher.py:337` hashes `body.encode()` only; the `X-Timestamp` header set at line 239 is sent in clear and never bound into the MAC.
- Signed-request signature mismatch (§3.1) — every signed REST call is vulnerable to `-1022` rejection; on retries the stale `timestamp` (set once at line 220, before the `while attempt <= retries` loop at line 227) will trip `-1021` and burn the `recvWindow` budget.
- `data/cache_manager.py:91` — `_pubsub_client` field declared but never assigned. The `close()` path at line 122 simply skips the `if self._pubsub_client:` branch. Harmless today, but a placeholder to fix when wired up.
- No hardcoded secrets in scope: `grep -rn "api_key\s*=\s*['\"]"` returns clean.

### 2.2 Performance
No regressions; no improvements. Still open:
- `signals/confluence_scorer.py:311` — `score_all` filters `scanner_results` once per symbol inside `for symbol in symbols:`. O(R · S). Re-verified today: with R ≈ 6 scanners × S ≈ 200 USDT-perps this is ~240k comparisons per cycle. Sub-second today, will dominate when the symbol universe expands. Fix: bucket once with `defaultdict(list)`. (Carryover, unchanged.)
- `alerts/rate_limiter.py:175` — `_symbol_buckets` is unbounded; never evicts buckets for delisted or never-traded symbols. Slow leak. Add an LRU cap and a daily prune on `reset_daily`. (Carryover, unchanged.)
- `signals/indicator_engine.py:324–331` — `_ema` is a Python `for` loop, called for SMA-20/50/200, MACD fast/slow/signal, and Stoch-K/D smoothing per symbol per cycle. Vectorise with `pandas.Series.ewm(adjust=False).mean()` or `scipy.signal.lfilter([k], [1, -(1-k)], data)`. (Carryover, unchanged.)

### 2.3 Maintainability
No regressions; no improvements. Still open:
- `scanner/pattern_scanner.py:232, 237` cross-imports `_dict_to_candle` / `_candle_to_dict` from `scanner.volume_scanner`. These belong in `data/data_normalizer.py`. Latent breakage if `volume_scanner` is ever moved or renamed.
- `alerts/*` mixes `datetime.utcnow()` (deprecation-warned in Python 3.12+) with the rest of the codebase's `time.monotonic()` / `time.time()`: `alpha_decay_monitor.py:60,126,290`, `retrain_scheduler.py:60,152,195`, `telegram_alerts.py:51`. Replace with `datetime.now(timezone.utc)`.
- Nine untracked `CODE_REVIEW_*.md` files now in the repo root accumulating without a triage destination. Either git-ignore them, sink them into `archive/`, or convert findings into issues.
- Two suffixed duplicates still in `coinscope_trading_engine/`: `whale_signal_filter.py` + `whale_signal_filter (1).py`, and `trade_journal.py` + `trade_journal (2).py`. Resolve before the next merge.

---

## 3. Carryover P0s — re-verified at current line numbers

### 3.1 [P0] `data/binance_rest.py:97, 217–227` — signature over sorted payload, body sent unsorted; timestamp set once before retry loop
Re-verified today by reading lines 210–225 and 227:

```python
# data/binance_rest.py:217
req_params = dict(params or {})

if signed:
    req_params["timestamp"]   = int(time.time() * 1000)
    req_params["recvWindow"]  = self._recv_window
    req_params["signature"]   = _sign(self._api_secret, req_params)

url = f"{self._base_url}{path}"
attempt = 0

while attempt <= retries:
    ...
    async with self._session.request(
        method, url,
        params=req_params if method == "GET" else None,
        data=req_params  if method != "GET" else None,
    ) as resp:
        ...
```

`_sign` (line 97) signs `urlencode(sorted(params.items()))`, but `aiohttp.ClientSession.request(... params=req_params)` serialises the dict in insertion order. Binance rebuilds the HMAC from the on-wire query string → fails with `-1022 Signature for this request is not valid`. Additionally, `timestamp` is computed **once** before the retry loop; every retry sends the original timestamp and will eventually trip `-1021 Timestamp for this request is outside of the recvWindow`.

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
        # REST response has the order fields directly;
        # WS forceOrder event nests them under "o"
        order = raw.get("o", raw)
        return LiquidationOrder(
            symbol        = order["s"],
            side          = order["S"],
            order_type    = order["o"],          # ← collides with REST field 'origQty'/'origType'
            time_in_force = order["f"],
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

REST `GET /fapi/v1/allForceOrders` returns objects with long keys (`symbol`, `side`, `origQty`, `price`, `executedQty`, `status`, `time`, …), not the WS short keys (`s`, `S`, `q`, `p`, `X`, `T`). Every REST item raises `KeyError`, gets logged at WARNING, returns `None`. `LiquidationScanner.scan()` ends up with an empty list and no signal ever fires from the REST path.

**Fix (unchanged):** branch on shape rather than on `raw.get("o")`. The raw REST payload has neither an `"o"` field nor `"S"`; detect by `"origQty" in raw` and parse the long-key shape, falling back to the WS shape only when `raw.get("e") == "forceOrder"`.

### 3.3 [P0] `risk/correlation_analyzer.py:188–192` — gate fails open on missing history
Re-verified today (full block):

```python
def is_safe_to_add(
    self, new_symbol, new_direction, open_positions
) -> tuple[bool, str]:
    for sym, pos in open_positions.items():
        if sym == new_symbol:                continue
        if pos.direction != new_direction:   continue   # opposite directions hedge
        r = self.pearson(new_symbol, sym)
        if r is None:
            continue                                    # ← FAILS OPEN
        if abs(r) >= self._threshold:
            return False, f"… correlated with open {sym} (r={r:.2f})"
    return True, ""
```

`pearson()` returns `None` whenever either symbol has fewer than `_min_history` price samples (declared at the top of the file). At engine start-up the correlation-window is empty, so every pair returns `None`, every check is skipped, and the gate returns `(True, "")` regardless of true correlation. Capital-preservation violation.

**Fix (unchanged):** treat missing history as "unknown → block." Refactor to pre-warm the correlation cache during the first N scan cycles and return `(False, "Insufficient correlation history (n=…/min=…)")` until both legs have enough samples.

### 3.4 [P0] `alerts/webhook_dispatcher.py:236–243, 337` — HMAC does not cover X-Timestamp
Re-verified today. The headers block is set at line 234–243:

```python
headers = {
    "Content-Type":  "application/json",
    "X-Alert-Type":  alert_type,
    "X-Source":      "CoinScopeAI",
    "X-Timestamp":   str(int(time.time())),
}
if self._secret:
    sig = _sign_payload(body, self._secret)
    headers["X-Signature"] = sig
```

And `_sign_payload` (line 337):

```python
def _sign_payload(body: str, secret: str) -> str:
    """Return HMAC-SHA256 hex signature of the payload."""
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
```

`body` is the only thing fed to the MAC. `X-Timestamp` rides along in clear and is never bound into the signature, so a captured payload is replayable indefinitely.

**Fix (unchanged):** include the timestamp in the canonical string before HMACing, and have receivers reject when `|now - X-Timestamp| > 5 min`:

```python
ts  = str(int(time.time()))
mac = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
headers["X-Timestamp"] = ts
headers["X-Signature"] = f"v1={mac}"
```

### 3.5 [P0] `data/binance_websocket.py:247` — reconnect counter no-op
Re-verified today:

```python
self._connected.set()
self.stats.connected_at = time.monotonic()
self.stats.reconnects  += 1 if self.stats.reconnects else 0   # ← no-op while 0
self._reconnect_delay   = RECONNECT_DELAY_S
```

Operator precedence is `+= (1 if … else 0)`. While `self.stats.reconnects` is 0 (initial), `+= 0`. Since the counter can never escape 0 through this path, every successive `_do_connect` call also adds 0. The genuine increment lives at line 321 inside `_recv_loop`; line 247 is dead code that lies in the stats dict.

**Fix (unchanged):** delete line 247. The legitimate reconnect counter at line 321 is sufficient.

### 3.6 [P0] `alerts/alert_queue.py:244–253` — check-then-act race in `_enqueue`
Re-verified today:

```python
async def _enqueue(self, item: AlertItem) -> bool:
    if self._queue.full():
        self._dropped += 1
        logger.warning(
            "AlertQueue full (%d). Dropping %s alert (total dropped=%d).",
            self._queue.maxsize, item.alert_type, self._dropped,
        )
        return False
    await self._queue.put(item)        # ← awaits if full, blocking the producer
    return True
```

Between `self._queue.full()` and `await self._queue.put(item)`, the worker loop or any concurrent producer can change the queue's fill level. If the queue fills in that window, `put` will await for an empty slot, blocking the producer indefinitely under burst — exactly the failure mode the drop-on-full branch was meant to prevent.

**Fix (unchanged):** use `put_nowait` and catch `asyncio.QueueFull`:

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

### 3.7 [P0] `alerts/rate_limiter.py:175, 250–267` — unbounded per-symbol map; refund mutates `_tokens` outside lock
Re-verified today.

(a) Unbounded map (line 175):
```python
self._symbol_buckets: dict[str, _TokenBucket] = {}
```
Never trimmed. Any symbol seen once stays forever. Across long uptimes this is a slow leak, and on rotating universes (delisted perps, new listings) the bucket count climbs monotonically.

(b) Lock-bypassing refund (line 260–264):
```python
if not self.allow_telegram():
    # symbol token was already consumed — refund it
    self._get_symbol_bucket(symbol)._tokens = min(
        self._symbol_capacity,
        self._get_symbol_bucket(symbol)._tokens + 1,
    )
    return False
```

`_TokenBucket._lock` is held by `try_consume` / `_refill` / `available` / `time_until_available` / `reset` — but here the refund mutates `_tokens` directly, *outside* the lock, and reads it twice (once for `min()`, once for `+ 1`). Under any concurrent `try_consume` or refill, the read is stale and the write can over-credit (refund races with refill) or under-credit. It also calls `_get_symbol_bucket(symbol)` twice; not expensive today but a duplicated lookup that subtly differs from the bucket already used by `allow_symbol`.

**Fix (unchanged):** add an LRU cap (e.g. 1 024 symbols) with TTL eviction, and replace the refund with a method on `_TokenBucket` that mutates under the bucket's own lock:

```python
def credit(self, tokens: float = 1.0) -> None:
    with self._lock:
        self._refill()
        self._tokens = min(self.capacity, self._tokens + tokens)

# usage:
bucket = self._get_symbol_bucket(symbol)
if not self.allow_signal_inner(...):
    bucket.credit(1.0)
```

---

## 4. Carryover P1s — still present (spot-checked 5 / 16)

| # | Location | Issue |
|---|---|---|
| P1-01 | `data/binance_rest.py` (signed call cache) | Signed responses are cached behind the same key as unsigned — risk of leaking authenticated data on a key collision. |
| P1-02 | `data/binance_websocket.py:_dispatch` | Subscriber callbacks are invoked synchronously from the dispatch loop; a slow callback stalls the entire WS message stream. Wrap in `asyncio.create_task` and retain the task. |
| P1-03 | `data/binance_stream_adapter.py` | No back-pressure between WS receive and downstream consumers; an unbounded internal queue. |
| P1-04 | `data/cache_manager.py:91, 122` | `_pubsub_client` declared but never assigned; close() branch is dead until wired. |
| P1-05 | `data/data_normalizer.py:trade_to_schema` | Drops the `isBuyerMaker` flag — needed for taker side classification in some scanners. |
| P1-06 | `data/market_stream.py` | Stream restart drops the in-flight buffer instead of replaying. Recoverable miss but causes scanner cold-start. |
| P1-07 | `signals/confluence_scorer.py:_normalise_score` | Hard-coded clamp to `[-1, 1]` after weighted sum; needs explanatory test cases. |
| P1-08 | `signals/indicator_engine.py:_ema` | Pure-Python EMA loop (see §2.2). |
| P1-09 | `signals/entry_exit_calculator.py:calculate` | When ATR is 0, returns invalid setup — but does not fall through to structure-only stops. |
| P1-10 | `signals/backtester.py` | Look-ahead leak via `df.iloc[i+1]` in slippage estimation; the next candle should not be visible at decision time. |
| P1-11 | `scanner/funding_rate_scanner.py` | Treats single-cycle funding extremes as actionable; no smoothing across the 8h window. |
| P1-12 | `scanner/liquidation_scanner.py` | Aggregates by absolute USD; should also track liquidation count to filter pump-and-dump artefacts. |
| P1-13 | `scanner/orderbook_scanner.py` | Imbalance threshold is hard-coded; should be ATR-relative. |
| P1-14 | `scanner/pattern_scanner.py:232, 237` | Cross-imports private helpers from `scanner.volume_scanner` (see §2.3). |
| P1-15 | `alerts/telegram_notifier.py` | Markdown-V2 escape function does not escape `{}` characters; messages with code-style payloads can break parse mode. |
| P1-16 | `risk/exposure_tracker.py` | Aggregates notional rather than risk; two equal-notional positions with very different stops contribute equally to the exposure cap. |

---

## 5. New findings today

### 5.1 [P2 — carried since 2026-04-30] `risk/circuit_breaker.py:271–275` — fire-and-forget callback task is unowned

```python
if self._on_trip:
    try:
        coro = self._on_trip(reason, daily_loss_pct)
        if asyncio.iscoroutine(coro):
            asyncio.create_task(coro)
    except Exception as exc:
        logger.error("CircuitBreaker on_trip callback error: %s", exc)
```

`asyncio.create_task` returns a task that is not retained anywhere; per the CPython 3.10+ docs, the event loop only weakly references it, so under GC pressure the task can be cancelled before completion. The `try/except` only catches errors raised *synchronously* by `_on_trip(...)` (i.e. before the task is scheduled) — exceptions inside the awaited coroutine surface only as "Task exception was never retrieved" warnings.

**Fix:** retain the task and add a done-callback for logging:
```python
self._pending_alerts: set[asyncio.Task] = set()
...
task = asyncio.create_task(coro)
self._pending_alerts.add(task)
task.add_done_callback(self._pending_alerts.discard)
task.add_done_callback(
    lambda t: t.exception() and logger.error("on_trip task failed: %s", t.exception())
)
```

### 5.2 [P2 — carried since 2026-04-30] `risk/circuit_breaker.py:191–215` — `_rapid_log` mutated without a lock

`record_trade_result` mutates `self._rapid_log` (a Python `list`) with an unsynchronised read-modify-write:

```python
self._rapid_log.append((now, pnl_pct))
cutoff = now - self._rapid_window_s
self._rapid_log = [(t, p) for t, p in self._rapid_log if t >= cutoff]
window_loss = sum(p for _, p in self._rapid_log if p < 0)
```

In the current single-task topology only one caller writes here, but the comprehension rebinds `_rapid_log` at each call — readers iterating in another task can see a half-evicted snapshot, and a concurrent writer would lose entries. Bound the structure to a `collections.deque(maxlen=N)` and gate writes/reads with an `asyncio.Lock`.

### 5.3 [P2 — NEW] `risk/circuit_breaker.py:54–57` — `BreakerState.COOLDOWN` is dead

```python
class BreakerState(str, Enum):
    CLOSED   = "CLOSED"     # trading allowed
    OPEN     = "OPEN"       # trading halted
    COOLDOWN = "COOLDOWN"   # recently tripped, cooling down
```

`grep -n "COOLDOWN" risk/circuit_breaker.py` returns the enum definition and the docstring at the top of the file — and **no other reference**. Every state transition in `check`, `_trip`, `_maybe_auto_reset`, `reset`, and `reset_daily` flips between `CLOSED` and `OPEN` directly. The docstring at lines 17–19 promises a third state ("auto-reset after `reset_after_s`") that the implementation does not produce.

**Fix:** either implement the COOLDOWN state (set in `_maybe_auto_reset` for the duration `[trip_time + cool_period, trip_time + reset_after_s]`, with checks accepting `state in (CLOSED, COOLDOWN)`), or delete the enum value and the misleading docstring lines. The latter is the lower-risk change; the former is the correct one if the design intent was a graduated re-entry.

### 5.4 [P1 — NEW] `signals/signal_generator.py:55, 80–83` — shared HMM regime detector overwritten on each per-symbol fit

```python
class SignalGenerator:
    def __init__(self, testnet: bool = True):
        ...
        self.regime_det  = EnsembleRegimeDetector()    # ← single instance
        self._regime_fit: dict[str, bool] = {}

    def _regime_signal(self, symbol: str, df: pd.DataFrame) -> tuple[str, float]:
        ...
        if symbol not in self._regime_fit:
            self.regime_det.fit(r, v)                  # ← stateful fit on shared model
            self._regime_fit[symbol] = True
        res = self.regime_det.predict_regime(r[-50:], v[-50:])
```

`EnsembleRegimeDetector` is instantiated **once** but `fit()` is called for each new symbol it encounters. Each `fit` overwrites the prior internal state of the detector. The `_regime_fit` gate prevents *re-fitting on the same symbol*, but provides no isolation between symbols. Net effect: at any given time the detector is parametrised by whichever symbol last triggered a first-time fit — every other symbol's predictions are made against a model trained on different data.

This is a **silent miscalibration**: predictions look plausible, but the regime classifier is in fact fitted to the wrong distribution for all but the most recently fit symbol.

**Fix:** keep one detector per symbol:

```python
from collections import defaultdict

self._regime_dets: dict[str, EnsembleRegimeDetector] = {}

def _regime_signal(self, symbol: str, df: pd.DataFrame) -> tuple[str, float]:
    ...
    if symbol not in self._regime_dets:
        det = EnsembleRegimeDetector()
        det.fit(r, v)
        self._regime_dets[symbol] = det
    det = self._regime_dets[symbol]
    res = det.predict_regime(r[-50:], v[-50:])
    return res["regime"], res["confidence"]
```

This is **P1, not P0**, only because the engine is currently frozen and the orchestrator is not driving live signals; once unfrozen it should be re-classified P0 if the regime weight (`WEIGHTS["regime"] = 0.25`) is preserved.

### 5.5 [P2 — NEW] `signals/signal_generator.py:163` — confidence saturates at the threshold, not at full signal strength

```python
confidence = min(abs(norm_score) / SIGNAL_THRESHOLD, 1.0)
```

`SIGNAL_THRESHOLD = 0.55`. Any `norm_score ≥ 0.55` produces `confidence = 1.0`. So a barely-passing signal (norm_score 0.55) and a maximally-confluent signal (norm_score 1.00) both report `confidence = 1.0` — there is no headroom to distinguish them.

This propagates into the alert payload (`confidence` field) and then into position sizing, which means the Kelly sizer / scale-up manager can never differentiate a marginal signal from a strong one once the threshold is crossed.

**Fix:** linear scaling from 0 to 1 across the range `[SIGNAL_THRESHOLD, 1.0]` (or stop normalising and just emit `abs(norm_score)`):

```python
if abs(norm_score) < SIGNAL_THRESHOLD:
    confidence = 0.0
else:
    confidence = (abs(norm_score) - SIGNAL_THRESHOLD) / (1.0 - SIGNAL_THRESHOLD)
```

### 5.6 [P2 — NEW] `signals/entry_exit_calculator.py:271–290` — “most recent swing” comment, but code uses min/max over the window

```python
if direction == SignalDirection.LONG:
    # Look for the most recent swing low below entry
    swing_lows = [c.low for c in recent if c.low < entry]
    if not swing_lows:
        return None
    sl_candidate = min(swing_lows) - atr * 0.1     # ← deepest, not most recent
    if abs(entry - sl_candidate) <= atr * 2.5:
        return sl_candidate
else:
    swing_highs = [c.high for c in recent if c.high > entry]
    if not swing_highs:
        return None
    sl_candidate = max(swing_highs) + atr * 0.1    # ← highest, not most recent
    if abs(sl_candidate - entry) <= atr * 2.5:
        return sl_candidate
return None
```

The docstring promises “most recent swing low/high”, but the implementation picks the deepest (LONG) / highest (SHORT) candle in the lookback window. When the structure is within the 2.5 × ATR cap, this widens the stop substantially compared to the documented intent — the structure SL is consistently looser than expected.

**Fix:** walk the recent window from newest to oldest until a candle with `c.low < entry` (LONG) or `c.high > entry` (SHORT) is found that is also a local extremum (e.g. lower than the candle on either side), and use that one. Or, if "deepest within range" was the actual intent, fix the docstring.

### 5.7 [P2 — NEW] `signals/signal_generator.py:139` — division by 1.0

```python
max_possible = sum(WEIGHTS.values())   # always 1.0 by construction
norm_score   = score / max_possible    # divides by 1.0
```

Defensive but pointless — `WEIGHTS` is a module-level constant at the top of the file with values that sum to exactly 1.0. Either remove the divide, or compute `max_possible` *after* the regime suppression (so suppression doesn't bias the normalised score by 25 % when chop-confidence > 0.55):

```python
active_weights = {
    "scorer":      WEIGHTS["scorer"],
    "regime":      regime_weight,
    "mtf":         WEIGHTS["mtf"],
    "volume":      WEIGHTS["volume"],
    "liquidation": WEIGHTS["liquidation"],
}
max_possible = sum(active_weights.values()) or 1.0
norm_score   = score / max_possible
```

The current behaviour is a **subtle calibration bug**: when chop suppresses regime (regime_weight = 0), `score` loses up to 0.25 of its possible magnitude, but `max_possible` still divides by 1.0. So a chop-suppressed signal needs `score ≥ 0.55` out of an effective 0.75 = 73 % of available votes, while a non-chop signal needs only 55 %. Effectively the threshold is *higher* in chop, which is plausibly what the author wanted — but it should be done explicitly, not as a side-effect of leaving the divisor unchanged.

---

## 6. Recommendations (prioritised, with code examples)

### Priority 1 — fix before any live trading session

1. **Sign the canonical query string (§3.1).** See the patch at the end of §3.1.
2. **Branch liquidation parsing on payload shape (§3.2).** Detect `"origQty" in raw` for REST, fall back to WS short-keys when `raw.get("e") == "forceOrder"`.
3. **Make the correlation gate fail closed (§3.3).** Block until both legs have ≥ `_min_history` samples.
4. **Bind X-Timestamp into the webhook MAC (§3.4).** Use `f"{ts}.{body}"` as the canonical string and require the receiver to reject when `|now − ts| > 300 s`.
5. **Replace `_enqueue` with `put_nowait` (§3.6).** See the patch at the end of §3.6.
6. **Lock the rate-limiter refund and bound the bucket map (§3.7).** Add `_TokenBucket.credit()` and an LRU on `_symbol_buckets`.
7. **Per-symbol `EnsembleRegimeDetector` (§5.4).** See the patch at the end of §5.4.

### Priority 2 — fix this week

8. **Vectorise `_ema` (§2.2).** `pandas.Series.ewm(span=period, adjust=False).mean()` end-to-end.
9. **Bucket `scanner_results` once per cycle in `confluence_scorer.score_all` (§2.2).**
   ```python
   from collections import defaultdict
   by_sym: dict[str, list[ScannerResult]] = defaultdict(list)
   for r in scanner_results:
       if not r.error:
           by_sym[r.symbol].append(r)
   ```
10. **Calibrate confidence (§5.5).** Linear scaling above the threshold.
11. **Resolve the duplicated files** `whale_signal_filter (1).py` and `trade_journal (2).py`.
12. **Move `_dict_to_candle` / `_candle_to_dict` into `data/data_normalizer.py`** (§2.3).
13. **Either implement or delete `BreakerState.COOLDOWN`** (§5.3).

### Priority 3 — hygiene

14. **Triage the nine `CODE_REVIEW_*.md` files** into Linear/GitHub issues, then either delete them or move to `archive/`.
15. **Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`** across `alerts/`.
16. **Retain async tasks** where they are currently fire-and-forget (§5.1).
17. **Document or fix `_find_structure_sl`** behaviour (§5.6).
18. **If frozen-state is intentional**, add a one-line note to `README.md` so this scheduled review can become a no-op verification rather than re-reading the same code every morning.

---

## 7. Status

- 7 P0s, 17 P1s, 22 P2s — net +1 P1 / +3 P2 since 2026-04-30.
- Branch frozen at `59416a2` for 13 days.
- No file in scope has changed since 2026-04-18 23:32.
- Engine should not be run against mainnet capital until at least the seven P0s in §3 and the new P1 in §5.4 are resolved.

*Run autonomously per scheduled task definition; no actions taken on third-party systems (no Linear issues, no GitHub PRs, no Slack posts). This file is the only artefact produced.*
